"""Cycle 4.3 - Garde-fous OOD (Out-Of-Distribution).

Pour chaque query, déterminer si le top-1 retrieval est suffisamment
confiant pour accepter l'identification, ou si on doit basculer en mode
dégradé "produit non identifié, saisie assistée".

Heuristiques OOD
----------------
1. **Seuil absolu sur top-1 score** : si cosine(query, top-1) < S_min,
   le query est trop loin de tout produit catalogue → OOD probable.
2. **Gap top-1 vs top-2** : si top-1 et top-2 ont des scores quasi-
   égaux, ambiguïté → ne pas affirmer le top-1, déclencher Akinator.
3. **Consensus multi-view** : si vision et texte renvoient des top-1
   différents, signal contradictoire → OOD ou besoin observation.

Sortie : module **importable** + script de calibration des seuils.

Mesure de calibration sur val :
- Pour chaque query, on a la vraie catégorie. Si top-1 même cat → vrai positif.
- On construit la courbe (seuil S → précision/rappel).
- On choisit S au meilleur F0.5 (privilégier précision sur rappel
  car coût d'une fausse identification > coût d'un OOD raté).

Lance APRÈS Cycle 4.1 (faiss indices construits) :

    python -m src.retrieval.03_ood_guardrails
"""

from __future__ import annotations

import json
import logging

import numpy as np
import polars as pl

from src.config import (
    DATA_EMBEDDINGS,
    DATA_INDEX,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_RETRIEVAL,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EVAL_N_QUERIES = 5000
TOP_K = 10

OUT_JSON = REPORTS_RETRIEVAL / "ood_calibration.json"
OUT_MD = REPORTS_RETRIEVAL / "ood_calibration.md"


def is_ood_top1(top1_score: float, threshold: float) -> bool:
    """Test seuil absolu : True si OOD probable."""
    return top1_score < threshold


def is_ambiguous_top12(top1_score: float, top2_score: float, gap_threshold: float = 0.05) -> bool:
    """Test ambiguïté : True si top-1 et top-2 trop proches."""
    return (top1_score - top2_score) < gap_threshold


def main() -> None:
    log.info("=== Cycle 4.3 - Calibration OOD seuils ===")
    REPORTS_RETRIEVAL.mkdir(parents=True, exist_ok=True)

    text_index_path = DATA_INDEX / "text_arctic_hnsw.index"
    if not text_index_path.exists():
        log.error("text_arctic_hnsw.index introuvable. Lance Cycle 4.1 d'abord.")
        return

    import faiss

    log.info("Lecture index + val embeddings…")
    index = faiss.read_index(str(text_index_path))
    val_emb = np.load(DATA_EMBEDDINGS / "text" / "text_arctic_val.npy").astype(np.float32)
    train_labels = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "train.parquet", columns=["_source_category"]
    )["_source_category"].to_numpy()
    val_labels = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "val.parquet", columns=["_source_category"]
    )["_source_category"].to_numpy()

    # Sample queries
    rng = np.random.default_rng(SEED)
    n_queries = min(EVAL_N_QUERIES, val_emb.shape[0])
    query_idx = rng.choice(val_emb.shape[0], size=n_queries, replace=False)
    queries = val_emb[query_idx]
    gt_labels = val_labels[query_idx]
    log.info("Sample %d queries", n_queries)

    log.info("Search top-%d…", TOP_K)
    distances, indices = index.search(queries, TOP_K)
    top1_scores = distances[:, 0]
    top2_scores = distances[:, 1]
    top1_labels = train_labels[indices[:, 0]]

    # Vérité terrain : True si top-1 même cat que ground truth
    is_correct = top1_labels == gt_labels
    n_correct = is_correct.sum()
    log.info(
        "Top-1 correct (même cat) : %d/%d (%.1f %%)",
        n_correct,
        n_queries,
        100 * n_correct / n_queries,
    )

    # Distribution des scores top-1 sur correct vs incorrect
    correct_scores = top1_scores[is_correct]
    incorrect_scores = top1_scores[~is_correct]
    log.info(
        "Top-1 score correct : médiane=%.4f, p10=%.4f",
        float(np.median(correct_scores)) if len(correct_scores) else 0,
        float(np.percentile(correct_scores, 10)) if len(correct_scores) else 0,
    )
    log.info(
        "Top-1 score incorrect : médiane=%.4f, p90=%.4f",
        float(np.median(incorrect_scores)) if len(incorrect_scores) else 0,
        float(np.percentile(incorrect_scores, 90)) if len(incorrect_scores) else 0,
    )

    # Calibration : pour chaque seuil, mesurer précision (= taux correct
    # parmi accepted) et rappel (= taux accepted parmi tous correct).
    thresholds = np.linspace(0.0, 1.0, 21)
    calibration = []
    for s in thresholds:
        accepted = top1_scores >= s
        n_accepted = accepted.sum()
        n_correct_accepted = (accepted & is_correct).sum()
        precision = n_correct_accepted / n_accepted if n_accepted > 0 else 0.0
        recall = n_correct_accepted / n_correct if n_correct > 0 else 0.0
        f0_5 = (
            (1 + 0.5**2) * precision * recall / (0.5**2 * precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        calibration.append(
            {
                "threshold": round(float(s), 3),
                "n_accepted": int(n_accepted),
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "f0.5": round(float(f0_5), 4),
            }
        )

    # Meilleur F0.5
    best = max(calibration, key=lambda c: c["f0.5"])
    log.info(
        "Meilleur seuil OOD (F0.5 max) : %.3f → P=%.4f, R=%.4f, F0.5=%.4f",
        best["threshold"],
        best["precision"],
        best["recall"],
        best["f0.5"],
    )

    # Ambiguïté : distribution gap top1-top2 sur correct vs incorrect
    gaps = top1_scores - top2_scores
    correct_gaps = gaps[is_correct]
    incorrect_gaps = gaps[~is_correct]

    full = {
        "n_queries_eval": int(n_queries),
        "n_top1_correct": int(n_correct),
        "score_distribution": {
            "correct_median": float(np.median(correct_scores)) if len(correct_scores) else 0.0,
            "correct_p10": float(np.percentile(correct_scores, 10)) if len(correct_scores) else 0.0,
            "incorrect_median": float(np.median(incorrect_scores))
            if len(incorrect_scores)
            else 0.0,
            "incorrect_p90": float(np.percentile(incorrect_scores, 90))
            if len(incorrect_scores)
            else 0.0,
        },
        "gap_top1_top2": {
            "correct_median": float(np.median(correct_gaps)) if len(correct_gaps) else 0.0,
            "incorrect_median": float(np.median(incorrect_gaps)) if len(incorrect_gaps) else 0.0,
        },
        "calibration_thresholds": calibration,
        "recommended_threshold": best,
    }
    OUT_JSON.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_JSON.name)
    log.info("Cycle 4.3 OOD calibration OK.")
    log.info(
        "\nUtilisation en production : `is_ood_top1(score, threshold=%.3f)`", best["threshold"]
    )


if __name__ == "__main__":
    main()
