"""Cycle 9.3a — Pipeline orchestrator RAG-grounded (serving).

Câble les briques locales (text-only MVP, cf. D-014) en services
consommés par les endpoints FastAPI :

- `IdentificationService` : encode la requête texte (Arctic) → FAISS HNSW
  search → vote k-NN cat (= M1) → garde-fou OOD (seuil D-012=0.600) →
  Akinator si ambiguïté (gap top1-top2 < seuil).
- `PricingService` : cascade M8 L1-L4 transparente.

R19 grounded-avant-génératif : l'identification est retrieval-first.
R7 assertions dims : Arctic = 1024, vérifié au runtime.

Les modèles génératifs (VLM validateur, LLM rédacteur) restent hors de ce
module — ils interviennent en aval (Cycle 9.3b /describe via OpenRouter).
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field

import numpy as np
import polars as pl

from src.config import (
    DATA_INDEX,
    DATA_MODELS,
    DATA_PROCESSED_PRODUCTS,
)

log = logging.getLogger(__name__)

ARCTIC_MODEL_NAME = "Snowflake/snowflake-arctic-embed-l-v2.0"
ARCTIC_EMBED_DIM = 1024
ARCTIC_QUERY_PROMPT = "query"  # Arctic Embed v2 prompt key pour les requêtes

HNSW_EF_SEARCH = 64
TOP_K_RETRIEVAL = 30  # candidats retournés, triés par similarité (scroll UI)

# Seuils de confiance — 3 niveaux (D-017).
# Le seuil F0.5=0.600 (D-012) était calibré sur item↔item (texte complet). En usage
# réel, la requête vendeur est courte → cosine systématiquement plus bas. On passe
# donc à 3 niveaux et on montre TOUJOURS les candidats (humain = validateur, R19).
IDENTIFIED_THRESHOLD = 0.60  # >= : produit identifié avec confiance
CONFIRM_THRESHOLD = 0.45  # [0.45, 0.60[ : à confirmer par le vendeur ; < : incertain
AMBIGUITY_GAP_THRESHOLD = 0.05  # gap top1-top2 → désambiguation Akinator

# Akinator backend (import dynamique : module préfixé par un chiffre)
_akinator = importlib.import_module("src.retrieval.04_akinator_backend")
_pricing = importlib.import_module("src.pricing.01_algorithmique")
_prompts = importlib.import_module("src.llm.01_prompt_templates")
_rag = importlib.import_module("src.llm.02_rag_grounded_writer")


@dataclass
class Candidate:
    parent_asin: str
    title: str
    store: str  # boutique Amazon (souvent revendeur, ex "Amazon Renewed")
    category: str  # _source_category (L1 macro : Electronics, …)
    score: float
    image_url: str = ""
    price: float | None = None  # prix catalogue (USD) du produit, pour le pricing F4
    category_fine: str = ""  # catégorie feuille du breadcrumb (L2/L3, ex: "Graphics Cards")
    brand: str = ""  # vraie marque fabricant (details['Brand'], fallback store)
    attributes: dict[str, str] = field(default_factory=dict)  # facettes Akinator (color, capacity…)


@dataclass
class IdentificationResult:
    status: str  # "identified" | "to_confirm" | "uncertain"
    candidates: list[Candidate]
    next_observation: object | None  # ObservationRequest | None
    explanation: str


class IdentificationService:
    """Service d'identification retrieval-first (text-only MVP).

    Charge en mémoire : index FAISS HNSW, métadonnées train (pour afficher
    les candidats), labels train (pour vote cat), et lazy l'encodeur Arctic.
    """

    def __init__(self) -> None:
        self._index = None
        self._train_meta: pl.DataFrame | None = None
        self._train_labels: np.ndarray | None = None
        self._train_prices: np.ndarray | None = None
        self._image_lookup: dict[str, str] = {}
        self._category_lookup: dict[str, str] = {}
        self._brand_lookup: dict[str, str] = {}
        self._facets_lookup: dict[str, dict[str, str]] = {}
        self._encoder = None
        self._loaded = False

    def load(self) -> None:
        """Charge index FAISS + métadonnées train + lookup vignettes. Encodeur lazy."""
        import faiss

        index_path = DATA_INDEX / "text_arctic_hnsw.index"
        if not index_path.exists():
            raise FileNotFoundError(
                f"{index_path} introuvable. Lance Cycle 2.4 (build indices) d'abord."
            )
        log.info("Loading FAISS HNSW index…")
        self._index = faiss.read_index(str(index_path))
        self._index.hnsw.efSearch = HNSW_EF_SEARCH

        log.info("Loading train metadata (parent_asin, title, store, category, price)…")
        self._train_meta = pl.read_parquet(
            DATA_PROCESSED_PRODUCTS / "train.parquet",
            columns=["parent_asin", "title", "store", "_source_category", "price_num"],
        )
        self._train_labels = self._train_meta["_source_category"].to_numpy()
        self._train_prices = self._train_meta["price_num"].to_numpy()  # prix catalogue (F4)

        # Lookup produit : vignette + catégorie fine (graceful si absent, cf. 06_build_product_lookup)
        lookup_path = DATA_PROCESSED_PRODUCTS / "product_lookup.parquet"
        if lookup_path.exists():
            lk = pl.read_parquet(lookup_path)
            asins = lk["parent_asin"].to_list()
            self._image_lookup = {
                a: u
                for a, u in zip(asins, lk["image_url"].to_list(), strict=False)
                if u is not None
            }
            self._category_lookup = {
                a: c
                for a, c in zip(asins, lk["category_leaf"].to_list(), strict=False)
                if c is not None
            }
            self._brand_lookup = (
                {a: b for a, b in zip(asins, lk["brand"].to_list(), strict=False) if b is not None}
                if "brand" in lk.columns
                else {}
            )
            if "facets_json" in lk.columns:
                import json as _json

                self._facets_lookup = {
                    a: _json.loads(f)
                    for a, f in zip(asins, lk["facets_json"].to_list(), strict=False)
                    if f
                }
            log.info(
                "  Lookup produit : %s vignettes, %s cat fines, %s marques, %s avec facettes",
                f"{len(self._image_lookup):_}",
                f"{len(self._category_lookup):_}",
                f"{len(self._brand_lookup):_}",
                f"{len(self._facets_lookup):_}",
            )
        else:
            log.warning(
                "  product_lookup.parquet absent → vignettes/cat fines vides "
                "(lance 06_build_product_lookup)"
            )

        self._loaded = True
        log.info("IdentificationService ready : %s vecteurs indexés", f"{self._index.ntotal:_}")

    def _ensure_encoder(self) -> None:
        """Charge l'encodeur Arctic à la première requête (lazy)."""
        if self._encoder is not None:
            return
        from sentence_transformers import SentenceTransformer

        log.info("Loading Arctic Embed encoder (lazy)…")
        self._encoder = SentenceTransformer(ARCTIC_MODEL_NAME)

    @property
    def ready(self) -> bool:
        return self._loaded

    def encode_query(self, text: str) -> np.ndarray:
        """Encode une requête texte en embedding Arctic L2-normalisé."""
        self._ensure_encoder()
        emb = self._encoder.encode(
            [text],
            prompt_name=ARCTIC_QUERY_PROMPT,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)
        assert (
            emb.shape[-1] == ARCTIC_EMBED_DIM
        ), f"Expected {ARCTIC_EMBED_DIM} dim, got {emb.shape[-1]}"
        return emb

    def _maybe_translate(self, text_query: str) -> str:
        """Traduit FR→EN via OpenRouter pour aligner sur le catalogue anglais.

        Décalage cross-lingue mesuré : une requête FR score ~0.08 plus bas qu'EN
        (catalogue Amazon US). Fallback gracieux sur la requête brute si pas de clé
        ou si l'appel échoue — l'identification reste fonctionnelle (Arctic est
        multilingue, juste un peu moins précis sans traduction).
        """
        openrouter = importlib.import_module("src.llm.openrouter_client")
        if not openrouter.is_available():
            return text_query
        try:
            translated = openrouter.translate_to_english(text_query)
            log.info("Requête traduite FR→EN : %r → %r", text_query, translated)
            return translated or text_query
        except Exception as e:  # noqa: BLE001 — la traduction ne doit jamais casser l'identification
            log.warning("Traduction échouée (fallback requête brute) : %s", e)
            return text_query

    def identify(
        self, text_query: str, already_observed: dict[str, str] | None = None
    ) -> IdentificationResult:
        """Pipeline complet : (traduire) → encode → search → OOD → Akinator si ambigu."""
        if not self._loaded:
            raise RuntimeError("IdentificationService non chargé. Appelle load() au lifespan.")

        search_query = self._maybe_translate(text_query)
        query_emb = self.encode_query(search_query)
        scores, indices = self._index.search(query_emb, TOP_K_RETRIEVAL)
        scores, indices = scores[0], indices[0]

        candidates = []
        for s, i in zip(scores, indices, strict=False):
            if i < 0:
                continue
            asin = str(self._train_meta["parent_asin"][int(i)])
            raw_price = self._train_prices[int(i)]
            price = (
                float(raw_price)
                if raw_price is not None and not np.isnan(raw_price) and raw_price > 0
                else None
            )
            store = str(self._train_meta["store"][int(i)] or "")
            brand = self._brand_lookup.get(asin, "") or store
            category_fine = self._category_lookup.get(asin, "")
            # Attributs facetables pour l'Akinator (entropie côté front) : facettes
            # curées + marque + catégorie fine, uniquement les non-vides.
            attributes = dict(self._facets_lookup.get(asin, {}))
            if brand:
                attributes["brand"] = brand
            if category_fine:
                attributes["category"] = category_fine
            candidates.append(
                Candidate(
                    parent_asin=asin,
                    title=str(self._train_meta["title"][int(i)] or ""),
                    store=store,
                    category=str(self._train_labels[int(i)]),
                    score=float(s),
                    image_url=self._image_lookup.get(asin, ""),
                    price=price,
                    category_fine=category_fine,
                    brand=brand,
                    attributes=attributes,
                )
            )

        if not candidates:
            return IdentificationResult(
                "uncertain", [], None, "Aucun candidat trouvé — saisie manuelle."
            )

        top1 = candidates[0]
        top2_score = candidates[1].score if len(candidates) > 1 else 0.0

        # Désambiguation Akinator si top1/top2 trop proches (variantes du même produit)
        next_observation = None
        is_ambiguous = _akinator.is_ambiguous(top1.score, top2_score, AMBIGUITY_GAP_THRESHOLD)
        if is_ambiguous:
            cand_meta = [
                {"title": c.title, "store": c.store, "main_category": c.category}
                for c in candidates
            ]
            next_observation = _akinator.select_next_observation(
                cand_meta, already_asked_attributes=set((already_observed or {}).keys())
            )

        # 3 niveaux de confiance sur le score absolu top-1. Candidats TOUJOURS montrés.
        if top1.score >= IDENTIFIED_THRESHOLD:
            status = "identified"
            base = f"Produit identifié (score {top1.score:.3f})."
        elif top1.score >= CONFIRM_THRESHOLD:
            status = "to_confirm"
            base = f"Est-ce l'un de ces produits ? (score {top1.score:.3f}, à confirmer)"
        else:
            status = "uncertain"
            base = (
                f"Correspondance incertaine (score {top1.score:.3f}). "
                "Vérifiez ou saisissez manuellement."
            )

        explanation = base
        if is_ambiguous:
            explanation += (
                f" Variantes proches (écart top1-top2 {top1.score - top2_score:.3f})"
                " — une observation peut préciser."
            )

        return IdentificationResult(
            status=status,
            candidates=candidates,
            next_observation=next_observation,
            explanation=explanation,
        )


class PricingService:
    """Service de pricing transparent cascade M8 L1-L4."""

    def __init__(self) -> None:
        self._config: dict | None = None

    def load(self) -> None:
        import joblib

        path = DATA_MODELS / "m8_pricing_v1.joblib"
        if not path.exists():
            raise FileNotFoundError(f"{path} introuvable. Lance Cycle 7.1 d'abord.")
        self._config = joblib.load(path)
        log.info("PricingService ready : médianes %s", self._config.get("category_medians_usd"))

    @property
    def ready(self) -> bool:
        return self._config is not None

    def suggest(
        self,
        category: str,
        condition: str = "bon_etat",
        age_years: float = 2.0,
        catalog_price: float | None = None,
        knn_neighbors_prices: list[float] | None = None,
    ):
        """Délègue à la cascade M8 avec la médiane catégorie chargée."""
        if self._config is None:
            raise RuntimeError("PricingService non chargé.")
        cat_median = self._config.get("category_medians_usd", {}).get(category)
        return _pricing.suggest_price(
            catalog_price=catalog_price,
            knn_neighbors_prices=knn_neighbors_prices,
            category_median_price=cat_median,
            condition=condition,
            age_years=age_years,
            category=category,
        )


@dataclass
class DescribeResult:
    title: str
    description: str
    grounding_sentences_count: int
    grounding_sentences_preview: list[str]
    parse_ok: bool


class DescribeService:
    """Service de rédaction grounded RAG (E4).

    Charge les métadonnées produit (train), récupère les phrases grounding
    (TODO Cycle 6.2 prep : reviews_index n'a pas la colonne `text`, lazy
    join raw à faire), puis génère titre + description via OpenRouter si
    `OPENROUTER_API_KEY` présent, sinon MockLLMWriter (D-013).
    """

    def __init__(self) -> None:
        self._train_meta: pl.DataFrame | None = None
        self._loaded = False

    def load(self) -> None:
        log.info("Loading train metadata for DescribeService (+ description grounding)…")
        self._train_meta = pl.read_parquet(
            DATA_PROCESSED_PRODUCTS / "train.parquet",
            columns=["parent_asin", "title", "store", "_source_category", "description"],
        )
        self._loaded = True

    @property
    def ready(self) -> bool:
        return self._loaded

    def _get_writer(self):
        """OpenRouter si clé dispo (E4 réel), sinon Mock (D-013)."""
        openrouter = importlib.import_module("src.llm.openrouter_client")
        if openrouter.is_available():

            class OpenRouterWriter(_rag.LLMWriter):
                name = "openrouter_gemini_flash"

                def generate(self, prompt: str) -> str:
                    return openrouter.chat_completion(prompt)

            return OpenRouterWriter()
        return _rag.MockLLMWriter()

    @staticmethod
    def _description_to_grounding(description: object) -> pl.DataFrame:
        """Convertit la description produit (liste de paragraphes stringifiée) en
        DataFrame `text` consommable par le RAG (extract_useful_sentences)."""
        import ast

        paragraphs: list[str] = []
        if isinstance(description, str) and description.strip():
            try:
                parsed = ast.literal_eval(description)
                if isinstance(parsed, list):
                    paragraphs = [str(p) for p in parsed if p and str(p).strip()]
                else:
                    paragraphs = [description]
            except (ValueError, SyntaxError):
                paragraphs = [description]
        if not paragraphs:
            return pl.DataFrame(schema={"text": pl.Utf8})
        return pl.DataFrame({"text": paragraphs})

    def describe(self, parent_asin: str, condition: str = "bon état") -> DescribeResult:
        if not self._loaded:
            raise RuntimeError("DescribeService non chargé.")
        row = self._train_meta.filter(pl.col("parent_asin") == parent_asin)
        if row.is_empty():
            raise ValueError(f"parent_asin {parent_asin} introuvable dans le catalogue.")
        product_meta = row.row(0, named=True)

        # Grounding F3 : on ancre la génération sur la DESCRIPTION réelle du produit
        # (paragraphes catalogue), pas seulement le titre ni la mémoire du LLM.
        # La description est une liste de paragraphes stringifiée ('[...]').
        grounding_df = self._description_to_grounding(product_meta.get("description"))
        writer = self._get_writer()
        listing = _rag.generate_listing(
            product_meta, grounding_df, writer, seller_condition=condition
        )
        return DescribeResult(
            title=listing.title,
            description=listing.description,
            grounding_sentences_count=len(listing.grounding_sentences_used),
            grounding_sentences_preview=listing.grounding_sentences_used[:3],
            parse_ok=listing.parse_ok,
        )
