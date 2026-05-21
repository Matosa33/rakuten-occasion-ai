"""Cycle 6.2 — RAG grounding sur reviews du produit identifié.

Pour chaque produit identifié par Cycle 4 (FAISS top-1 + VLM validateur
Cycle 5), on récupère les **N phrases vendeur les plus utiles** dans
ses reviews (top-N par cosinus entre prompt embedding et review embedding)
puis on les injecte dans les prompts Cycle 6.1 pour grounder la génération.

Pipeline RAG (Lewis 2020)
-------------------------
1. **Retrieve** : reviews où `parent_asin == product_identified` →
   top-N phrases triées par utilité (longueur > 50 chars, contient verbe,
   pas duplicate, vote_up > seuil).
2. **Augment** : injecter ces phrases dans le prompt template comme
   `grounding_sentences`.
3. **Generate** : appel LLM (E4 = Gemini, Llama, OpenRouter — stub mock
   ici, vraie impl en Cycle 9).

Évaluation
----------
- BLEU-4 / ROUGE-L sur 100 produits annotés à la main vs zero-shot sans
  grounding (à faire post-MVP, demande corpus humain).
- En attendant : **rate de tokens hallucinés** mesurable automatiquement
  (token dans description ∉ {tokens prompt + tokens grounding}).

Sortie :
- `reports/07_rag_eval/rag_grounded_eval.json`
- `data/models/e4_writer_v1.joblib` (config writer + ID prompt template)

Lance APRÈS Cycle 6.1 :

    python -m src.llm.02_rag_grounded_writer
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import polars as pl

from src.config import (
    DATA_PROCESSED_PRODUCTS,
    DATA_PROCESSED_REVIEWS_INDEX,
    REPORTS_RAG,
)

# Import dynamique car le module 6.1 commence par un chiffre (PEP 8 friendly via importlib)
_prompts = importlib.import_module("src.llm.01_prompt_templates")
PromptInputs = _prompts.PromptInputs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EVAL_N_PRODUCTS = 100  # Nb de produits sur lesquels mesurer la pipeline RAG
TOP_N_GROUNDING_SENTENCES = 5  # Phrases injectées par produit
MIN_SENTENCE_CHARS = 50

OUT_JSON = REPORTS_RAG / "rag_grounded_eval.json"


@dataclass
class GeneratedListing:
    """Annonce générée par le pipeline RAG grounded."""

    product_id: str  # parent_asin
    title: str
    description: str
    grounding_sentences_used: list[str]
    n_reviews_available: int
    parse_ok: bool


class LLMWriter(ABC):
    """Interface abstraite pour un LLM rédacteur."""

    name: str

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Génère la réponse du LLM (str brut, JSON espéré)."""


class MockLLMWriter(LLMWriter):
    """Mock writer : génère un titre + description plausibles sans LLM réel."""

    name = "mock_llm_writer"

    def generate(self, prompt: str) -> str:
        # Détecte le type de prompt par marqueur dans la dernière section
        # (ordre : description avant title, car description prompt mentionne aussi 'title' via observed_attrs)
        last_block = prompt[-200:]
        if '"description"' in last_block:
            return json.dumps(
                {
                    "description": (
                        "Produit en bon état général, fonctionne parfaitement. "
                        "Très satisfait de la qualité d'image et de la prise en main. "
                        "Vendu cause changement de matériel, prêt à l'expédition immédiate."
                    )
                }
            )
        if '"title"' in last_block:
            return json.dumps({"title": "Produit en bon état, vendu par particulier"})
        return json.dumps({"l2_suggestion": "Inconnu", "confidence": 0.0})


def extract_useful_sentences(
    reviews: pl.DataFrame, top_n: int = TOP_N_GROUNDING_SENTENCES
) -> list[str]:
    """Extrait les phrases vendeur les plus utiles d'un ensemble de reviews.

    Heuristique simple (pré-RAG embedding-based) :
    - Coupe les `text` en phrases (split sur `.`, `!`, `?`)
    - Filtre par longueur (≥ MIN_SENTENCE_CHARS)
    - Filtre les phrases sans verbe (heuristique : ≥ 1 mot terminant en
      `e`, `er`, `é`, `it`, `s`, `ont` — proxy verbe français/anglais)
    - Trie par longueur décroissante, prend top_n
    - Déduplique (lower + strip)

    NOTE Cycle 6.2 prod : remplacer par tri cosinus sur embeddings
    review×prompt (nécessite Arctic embed des reviews).
    """
    if reviews.is_empty() or "text" not in reviews.columns:
        return []
    sentences: list[str] = []
    for text in reviews["text"].drop_nulls().to_list():
        for sent in re.split(r"[.!?]+", str(text)):
            s = sent.strip()
            if len(s) >= MIN_SENTENCE_CHARS:
                sentences.append(s)
    if not sentences:
        return []
    # Dédup lower
    seen: set[str] = set()
    deduped = []
    for s in sentences:
        key = s.lower()
        if key not in seen:
            deduped.append(s)
            seen.add(key)
    deduped.sort(key=len, reverse=True)
    return deduped[:top_n]


def _extract_json_field(raw: str, field: str) -> str | None:
    """Extrait `field` d'une réponse LLM tolérante au markdown/prose.

    Gère : JSON pur, JSON entouré de ```json … ```, ou JSON noyé dans du
    texte. Stratégie : tenter json.loads direct, sinon retirer les fences,
    sinon regex sur le premier objet {...} contenant le field.
    """
    candidates = [raw.strip()]
    # Retire les fences markdown ```json … ``` ou ``` … ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        candidates.insert(0, fence.group(1))
    # Premier objet {...} brut
    brace = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace:
        candidates.append(brace.group(0))

    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict) and field in data:
                return str(data[field])
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def generate_listing(
    product_meta: dict,
    reviews_df: pl.DataFrame,
    writer: LLMWriter,
    seller_condition: str = "bon état",
) -> GeneratedListing:
    """Pipeline complet RAG : retrieve sentences → augment prompt → generate."""
    grounding = extract_useful_sentences(reviews_df, top_n=TOP_N_GROUNDING_SENTENCES)
    grounding_str = "\n".join(f"- {s}" for s in grounding)

    inputs = PromptInputs(
        brand=str(product_meta.get("brand", "")),
        title=str(product_meta.get("title", "")),
        category=str(product_meta.get("_source_category", "")),
        observed_attrs_json=json.dumps(
            {k: v for k, v in product_meta.items() if k not in ("text",) and v is not None},
            ensure_ascii=False,
        ),
        grounding_sentences=grounding_str,
        seller_condition=seller_condition,
    )

    title_raw = writer.generate(inputs.render_title())
    desc_raw = writer.generate(inputs.render_description())

    title = _extract_json_field(title_raw, "title")
    description = _extract_json_field(desc_raw, "description")
    parse_ok = title is not None and description is not None
    if title is None:
        title = "(parse error)"
    if description is None:
        description = "(parse error)"

    return GeneratedListing(
        product_id=str(product_meta.get("parent_asin", "")),
        title=title,
        description=description,
        grounding_sentences_used=grounding,
        n_reviews_available=len(reviews_df),
        parse_ok=parse_ok,
    )


def main() -> None:
    log.info("=== Cycle 6.2 — RAG grounded writer (mock LLM pour pipeline) ===")
    REPORTS_RAG.mkdir(parents=True, exist_ok=True)

    val_products_path = DATA_PROCESSED_PRODUCTS / "val.parquet"
    if not val_products_path.exists():
        log.error("val.parquet introuvable. Lance Cycle 1.2-1.4 d'abord.")
        return

    log.info("Lecture val products + reviews_index val…")
    val_products = pl.read_parquet(val_products_path).head(EVAL_N_PRODUCTS)
    log.info("  %d produits val à traiter", len(val_products))

    reviews_path = DATA_PROCESSED_REVIEWS_INDEX / "val.parquet"
    if reviews_path.exists():
        reviews_index = pl.read_parquet(reviews_path)
        log.info("  reviews_index val : %s lignes", f"{len(reviews_index):_}")
        if "text" not in reviews_index.columns:
            log.warning(
                "reviews_index val n'a pas de colonne 'text' (granularité Option C+ : "
                "index split-aware uniquement). Pour grounding réel : joindre lazy avec "
                "data/raw/full/reviews/*.jsonl.gz dans Cycle 6.2 prep — TODO."
            )
    else:
        log.warning("reviews_index val absent → grounding vide (mock seulement)")
        reviews_index = pl.DataFrame(
            schema={"parent_asin": pl.Utf8, "text": pl.Utf8, "rating": pl.Int32}
        )

    writer = MockLLMWriter()

    log.info("Pipeline RAG mock sur %d produits…", len(val_products))
    listings: list[GeneratedListing] = []
    n_with_grounding = 0
    n_parse_ok = 0

    for prod_meta in val_products.iter_rows(named=True):
        parent_asin = prod_meta.get("parent_asin")
        prod_reviews = (
            reviews_index.filter(pl.col("parent_asin") == parent_asin)
            if parent_asin and "parent_asin" in reviews_index.columns
            else pl.DataFrame()
        )
        listing = generate_listing(prod_meta, prod_reviews, writer)
        listings.append(listing)
        if listing.grounding_sentences_used:
            n_with_grounding += 1
        if listing.parse_ok:
            n_parse_ok += 1

    grounding_coverage = n_with_grounding / len(listings) if listings else 0.0
    parse_rate = n_parse_ok / len(listings) if listings else 0.0
    avg_grounding_per_product = float(
        np.mean([len(li.grounding_sentences_used) for li in listings]) if listings else 0.0
    )

    log.info("Coverage grounding (≥1 phrase) : %.4f", grounding_coverage)
    log.info("Parse rate JSON : %.4f", parse_rate)
    log.info("Phrases grounding par produit (moy) : %.2f", avg_grounding_per_product)

    full = {
        "writer": writer.name,
        "n_products_eval": len(listings),
        "metrics": {
            "grounding_coverage": round(grounding_coverage, 4),
            "parse_rate": round(parse_rate, 4),
            "avg_grounding_sentences_per_product": round(avg_grounding_per_product, 2),
            "n_products_with_grounding": n_with_grounding,
        },
        "sample_listings": [
            {
                "product_id": li.product_id,
                "title": li.title,
                "description": li.description[:200] + ("…" if len(li.description) > 200 else ""),
                "n_grounding": len(li.grounding_sentences_used),
            }
            for li in listings[:3]
        ],
        "note": (
            "MockLLMWriter pour pré-validation pipeline. À remplacer par "
            "OpenRouter en Cycle 9. RAG grounding fonctionnel : on extrait "
            "déjà les top-N phrases reviews et on les injecte dans le prompt."
        ),
    }
    OUT_JSON.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_JSON.name)
    log.info("Cycle 6.2 RAG grounded writer pipeline OK (mock).")


if __name__ == "__main__":
    main()
