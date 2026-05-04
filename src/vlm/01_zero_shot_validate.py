"""Cycle 5.1 — VLM zero-shot validateur (anti-hallucination en aval).

Une fois le retrieval Cycle 4 a renvoyé un top-1 candidat, on demande à
un VLM frontier (Gemini Flash via OpenRouter) :

    "Ces deux images montrent-elles le même produit ? Réponds JSON
     {match: bool, confidence: 0-1, reason: str}"

Si `match=False` ou `confidence < 0.5` → on bloque la sortie et on bascule
en mode dégradé (nouvelle observation Akinator ou rejet OOD).

C'est un **garde-fou** : sans VLM validateur, le retrieval peut renvoyer
un top-1 visuellement proche mais sémantiquement faux (même cat, autre
modèle). Le VLM zero-shot vérifie le matching final.

Architecture
------------
- `VLMValidator` : interface abstraite (impl Mock + impl OpenRouter).
- `validate_top1(query_img, candidate_img, candidate_meta) -> dict`
- Métriques mesurées sur val :
  * **Parse rate** : % de réponses JSON valides (cible ≥ 95 %)
  * **Agreement rate** : % où VLM dit `match=True` quand top-1 a bonne cat
  * **False positive rate** : % où VLM dit `match=True` quand top-1 a mauvaise cat
    (= taux d'hallucination résiduel après VLM, on veut < 5 %)

Implémentation actuelle : **Mock** (réponse uniforme `match=True, conf=0.7`)
permettant la validation du pipeline. L'impl OpenRouter sera ajoutée en
Cycle 9 quand l'API a besoin du vrai VLM.

Sortie :
- `reports/06_vlm_eval/zero_shot_eval.{md,json}` : métriques mock pour
  pré-validation du pipeline + Model Card E3.

Lance APRÈS Cycle 4.1+ :

    python -m src.vlm.01_zero_shot_validate
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

import numpy as np
import polars as pl

from src.config import (
    DATA_EMBEDDINGS,
    DATA_INDEX,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_VLM,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EVAL_N_QUERIES = 500  # 500 queries × 1 VLM call = $0.05-$0.10 si Gemini Flash
TOP_K = 1  # On valide uniquement le top-1 du retrieval

VLM_PROMPT = """Tu es un validateur d'identification produit pour un site de vente entre particuliers.

On te donne :
1. Une photo d'un produit prise par un vendeur particulier (l'objet réel)
2. La fiche meta d'un candidat trouvé dans notre catalogue : {candidate_meta_json}
3. Une image catalogue de ce candidat

Tâche : ces deux images montrent-elles **le même produit** (même modèle, même version) ?

Critères :
- Marque identique ✓
- Modèle identique (pas juste "même catégorie") ✓
- Version/génération cohérente si visible ✓

Réponds UNIQUEMENT en JSON strict :
{{"match": true|false, "confidence": 0.0..1.0, "reason": "<explication courte>"}}"""

OUT_JSON = REPORTS_VLM / "zero_shot_eval.json"
OUT_MD = REPORTS_VLM / "zero_shot_eval.md"


@dataclass
class VLMResponse:
    match: bool
    confidence: float
    reason: str
    parse_ok: bool = True
    raw: str = ""


class VLMValidator(ABC):
    """Interface abstraite pour un VLM validateur d'identification."""

    name: str

    @abstractmethod
    def validate(
        self, query_img_url: str, candidate_img_url: str, candidate_meta: dict
    ) -> VLMResponse:
        """Retourne la décision JSON parsée (ou parse_ok=False si KO)."""


class MockVLMValidator(VLMValidator):
    """Mock pour pré-validation pipeline. Retourne `match=True, conf=0.7`
    avec une faible probabilité de non-match (10 %)."""

    name = "mock_vlm"

    def __init__(self, seed: int = SEED) -> None:
        self.rng = np.random.default_rng(seed)

    def validate(
        self, query_img_url: str, candidate_img_url: str, candidate_meta: dict
    ) -> VLMResponse:
        # Politique mock : 90 % match, conf gaussienne autour 0.7
        is_match = self.rng.random() > 0.10
        conf = float(np.clip(self.rng.normal(0.7, 0.1), 0.0, 1.0))
        reason = (
            "Mock validator : décision aléatoire pour pré-validation pipeline."
            " À remplacer par OpenRouter en Cycle 9."
        )
        return VLMResponse(match=is_match, confidence=conf, reason=reason, parse_ok=True)


class OpenRouterVLMValidator(VLMValidator):
    """VLM frontier via OpenRouter (Gemini 2.0 Flash par défaut, paramétrable).

    Nécessite OPENROUTER_API_KEY dans l'env. Stub pour Cycle 9 — la vraie
    implémentation HTTP sera codée quand on basculera l'API en prod.
    """

    name = "openrouter_gemini_flash"

    def __init__(self, model: str = "google/gemini-2.0-flash-exp:free") -> None:
        self.model = model
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY absent de l'env. Définir avant d'utiliser OpenRouterVLMValidator."
            )

    def validate(
        self, query_img_url: str, candidate_img_url: str, candidate_meta: dict
    ) -> VLMResponse:
        # TODO Cycle 9 : implémenter le POST OpenRouter avec multi-image
        raise NotImplementedError(
            "OpenRouter VLM call à implémenter en Cycle 9 quand l'API serving sera codée."
        )


def parse_vlm_response(raw: str) -> VLMResponse:
    """Parse une réponse VLM en JSON strict avec fallback robuste."""
    try:
        data = json.loads(raw)
        return VLMResponse(
            match=bool(data.get("match", False)),
            confidence=float(data.get("confidence", 0.0)),
            reason=str(data.get("reason", "")),
            parse_ok=True,
            raw=raw,
        )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return VLMResponse(
            match=False,
            confidence=0.0,
            reason=f"Parse error: {e}",
            parse_ok=False,
            raw=raw,
        )


def main() -> None:
    log.info("=== Cycle 5.1 — VLM zero-shot validateur (mock pour pipeline) ===")
    REPORTS_VLM.mkdir(parents=True, exist_ok=True)

    text_index_path = DATA_INDEX / "text_arctic_hnsw.index"
    if not text_index_path.exists():
        log.error("text_arctic_hnsw.index introuvable. Lance Cycle 4.1 d'abord.")
        return

    import faiss

    log.info("Lecture index + val + train metas…")
    index = faiss.read_index(str(text_index_path))
    val_emb = np.load(DATA_EMBEDDINGS / "text" / "text_arctic_val.npy").astype(np.float32)
    train_meta = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "train.parquet",
        columns=["title", "brand", "_source_category"],
    )
    val_meta = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "val.parquet",
        columns=["_source_category"],
    )
    train_cats = train_meta["_source_category"].to_numpy()
    val_cats = val_meta["_source_category"].to_numpy()

    rng = np.random.default_rng(SEED)
    n_queries = min(EVAL_N_QUERIES, val_emb.shape[0])
    query_idx = rng.choice(val_emb.shape[0], size=n_queries, replace=False)
    queries = val_emb[query_idx]
    log.info("Sample %d queries", n_queries)

    log.info("Search top-%d…", TOP_K)
    _, top1_idx = index.search(queries, TOP_K)
    top1_idx = top1_idx[:, 0]
    top1_cats = train_cats[top1_idx]
    gt_cats = val_cats[query_idx]
    is_correct_cat = (top1_cats == gt_cats).astype(bool)
    log.info(
        "Top-1 même cat (proxy correct visuel) : %d/%d (%.1f %%)",
        is_correct_cat.sum(),
        n_queries,
        100 * is_correct_cat.mean(),
    )

    validator = MockVLMValidator()
    log.info("VLM validator : %s", validator.name)

    n_match = 0
    n_parse_ok = 0
    n_match_when_correct = 0
    n_match_when_incorrect = 0
    confidences: list[float] = []
    for q in range(n_queries):
        cand_meta = train_meta.row(int(top1_idx[q]), named=True)
        # En vrai on passerait les URLs images, ici les chaînes vides suffisent au mock
        resp = validator.validate(
            "query_img_url_placeholder", "cand_img_url_placeholder", cand_meta
        )
        if resp.parse_ok:
            n_parse_ok += 1
        if resp.match:
            n_match += 1
            if is_correct_cat[q]:
                n_match_when_correct += 1
            else:
                n_match_when_incorrect += 1
        confidences.append(resp.confidence)

    parse_rate = n_parse_ok / n_queries
    match_rate = n_match / n_queries
    n_correct = int(is_correct_cat.sum())
    n_incorrect = n_queries - n_correct
    agreement_when_correct = n_match_when_correct / n_correct if n_correct else 0.0
    fp_rate_among_incorrect = n_match_when_incorrect / n_incorrect if n_incorrect else 0.0

    log.info("Parse rate : %.4f (cible ≥ 0.95)", parse_rate)
    log.info("Agreement quand top-1 correct : %.4f", agreement_when_correct)
    log.info(
        "FP VLM (match=True quand top-1 incorrect) : %.4f (cible < 0.05)",
        fp_rate_among_incorrect,
    )
    log.info("Confiance médiane : %.4f", float(np.median(confidences)))

    full = {
        "validator": validator.name,
        "n_queries_eval": n_queries,
        "top_k": TOP_K,
        "top1_correct_cat_rate": round(float(is_correct_cat.mean()), 4),
        "vlm_metrics": {
            "parse_rate": round(parse_rate, 4),
            "match_rate": round(match_rate, 4),
            "agreement_when_correct": round(agreement_when_correct, 4),
            "fp_rate_among_incorrect": round(fp_rate_among_incorrect, 4),
            "confidence_median": round(float(np.median(confidences)), 4),
            "confidence_p10": round(float(np.percentile(confidences, 10)), 4),
            "confidence_p90": round(float(np.percentile(confidences, 90)), 4),
        },
        "note": (
            "MockVLMValidator utilisé pour pré-validation pipeline. "
            "Métriques placeholder. Remplacer par OpenRouterVLMValidator en Cycle 9 "
            "(GEMINI Flash via OpenRouter) pour la vraie évaluation E3."
        ),
        "sample_response": asdict(
            validator.validate("placeholder", "placeholder", {"title": "demo"})
        ),
    }
    OUT_JSON.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_JSON.name)
    log.info("Cycle 5.1 VLM zero-shot pipeline OK (mock).")


if __name__ == "__main__":
    main()
