"""Cycle 4.2 — Multi-view retrieval avec RRF (Reciprocal Rank Fusion).

Fusionne les top-K de plusieurs indices (text Arctic + vision SigLIP si
dispo) via RRF de Cormack 2009 :

    score_RRF(d) = Σ_i 1 / (k + rank_i(d))

où k=60 (constante Cormack), rank_i(d) = rang du doc d dans la i-ème vue.
Items absents d'une vue : score 0 pour cette vue.

Avantages RRF vs moyenne pondérée des scores :
- Robuste aux échelles de scores différentes (cosine vs distance)
- Pas de tuning de poids α (à la différence de la fusion adaptive fusion)
- Théoriquement optimal pour combiner rankings sans alignement de scores

Sortie :
- `reports/05_retrieval/multiview_rrf_eval.{md,json}` :
  comparaison Recall@k single-view vs RRF multi-view sur val.

Lance APRÈS Cycle 4.1 (faiss indices construits) :

    python -m src.retrieval.02_multiview_rrf
"""

from __future__ import annotations

import json
import logging
import time

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

# Cormack 2009 : k=60 par convention (insensible aux scores, sensible aux ranks)
RRF_K = 60
EVAL_N_QUERIES = 1000
TOP_K_RETRIEVAL = 50  # on retrieve K=50 par vue pour avoir matière à fusion

OUT_JSON = REPORTS_RETRIEVAL / "multiview_rrf_eval.json"
OUT_MD = REPORTS_RETRIEVAL / "multiview_rrf_eval.md"


def _rrf_fusion(rankings_per_view: list[np.ndarray], k: int = RRF_K) -> np.ndarray:
    """Fusion RRF de N rankings.

    Args:
        rankings_per_view: liste de N arrays shape (n_queries, top_k_per_view)
            contenant les indices retrieved par vue.
        k: constante RRF (60 = Cormack 2009).

    Returns:
        Array shape (n_queries, top_k_global) trié par score RRF décroissant.
        top_k_global = max nb d'items uniques sur toutes les vues.
    """
    n_queries = rankings_per_view[0].shape[0]
    top_k_per_view = rankings_per_view[0].shape[1]
    fused_top_k = []

    for q in range(n_queries):
        scores: dict[int, float] = {}
        for view_rankings in rankings_per_view:
            for rank, doc_id in enumerate(view_rankings[q]):
                scores[int(doc_id)] = scores.get(int(doc_id), 0.0) + 1.0 / (k + rank + 1)
        # Tri décroissant par score, garde top_k_per_view items
        sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
        top = [doc_id for doc_id, _ in sorted_docs[:top_k_per_view]]
        # Padding si pas assez de candidats
        if len(top) < top_k_per_view:
            top.extend([-1] * (top_k_per_view - len(top)))
        fused_top_k.append(top)

    return np.array(fused_top_k, dtype=np.int64)


def _compute_recall_per_query(
    retrieved: np.ndarray, ground_truth_labels: np.ndarray, train_labels: np.ndarray, k: int
) -> float:
    """Recall@k sémantique : ratio de queries où ≥1 voisin top-k a la même catégorie.

    Pour la classification de catégorie via retrieval, on mesure si
    parmi les k voisins, au moins un a la même catégorie que la query.
    """
    n_queries = retrieved.shape[0]
    n_correct = 0
    for q in range(n_queries):
        true_label = ground_truth_labels[q]
        retrieved_labels = train_labels[retrieved[q, :k]]
        if true_label in retrieved_labels:
            n_correct += 1
    return n_correct / n_queries


def main() -> None:
    log.info("=== Cycle 4.2 — Multi-view RRF ===")

    REPORTS_RETRIEVAL.mkdir(parents=True, exist_ok=True)

    text_index_path = DATA_INDEX / "text_arctic_hnsw.index"
    if not text_index_path.exists():
        log.error("text_arctic_hnsw.index introuvable. Lance Cycle 4.1 d'abord.")
        return

    import faiss

    log.info("Lecture indices…")
    text_index = faiss.read_index(str(text_index_path))
    text_index.hnsw.efSearch = 64
    log.info("  text HNSW : %s vecteurs", f"{text_index.ntotal:_}")

    has_vision = (DATA_INDEX / "vision_siglip_hnsw.index").exists()
    if has_vision:
        vision_index = faiss.read_index(str(DATA_INDEX / "vision_siglip_hnsw.index"))
        vision_index.hnsw.efSearch = 64
        log.info("  vision HNSW : %s vecteurs", f"{vision_index.ntotal:_}")
    else:
        log.warning("vision_siglip_hnsw.index absent → bench mono-view (text seul)")

    # Chargement queries val + ground truth labels
    log.info("Lecture val embeddings + labels…")
    val_text = np.load(DATA_EMBEDDINGS / "text" / "text_arctic_val.npy").astype(np.float32)
    train_labels = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "train.parquet", columns=["_source_category"]
    )["_source_category"].to_numpy()
    val_labels = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "val.parquet", columns=["_source_category"]
    )["_source_category"].to_numpy()

    # Sample queries
    rng = np.random.default_rng(SEED)
    query_idx = rng.choice(
        val_text.shape[0], size=min(EVAL_N_QUERIES, val_text.shape[0]), replace=False
    )
    queries_text = val_text[query_idx]
    gt_labels = val_labels[query_idx]
    log.info("Sample %d queries", len(queries_text))

    # Search text
    log.info("Search text…")
    t0 = time.time()
    _, text_top_k = text_index.search(queries_text, TOP_K_RETRIEVAL)
    log.info("  text search : %.2f ms/query", (time.time() - t0) * 1000 / len(queries_text))

    rankings = [text_top_k]
    view_names = ["text"]

    # Search vision si dispo
    if has_vision:
        # Note : pour vision on aurait besoin des embeddings vision val,
        # mais comme on encode pas tous les val items en vision (sample),
        # on se contente ici du text-only quand vision pas dispo.
        # Cycle 4.4 (FAISS multi-view production) gérera la jointure correcte
        # quand Cycle 2.2 SigLIP aura tourné.
        log.warning(
            "Vision search non implémenté ici (vision queries absentes)."
            " Multi-view à activer en Cycle 4.4 quand vision val embeddings dispos."
        )

    # Eval text seul
    results = {}
    log.info("\n=== Recall@k text-only ===")
    for k in (1, 5, 10, 20):
        if k > TOP_K_RETRIEVAL:
            continue
        recall = _compute_recall_per_query(text_top_k, gt_labels, train_labels, k=k)
        log.info("  recall@%d (text seul, ≥1 voisin = même cat) = %.4f", k, recall)
        results.setdefault("text_only", {})[f"recall_at_{k}"] = round(recall, 4)

    # Eval RRF si multi-view
    if len(rankings) > 1:
        log.info("\n=== RRF fusion (k=%d) ===", RRF_K)
        rrf_top = _rrf_fusion(rankings, k=RRF_K)
        for k in (1, 5, 10, 20):
            if k > TOP_K_RETRIEVAL:
                continue
            recall = _compute_recall_per_query(rrf_top, gt_labels, train_labels, k=k)
            log.info("  recall@%d (RRF %s) = %.4f", k, "+".join(view_names), recall)
            results.setdefault("rrf_multiview", {})[f"recall_at_{k}"] = round(recall, 4)

    full = {
        "n_queries_eval": int(len(queries_text)),
        "top_k_retrieval": TOP_K_RETRIEVAL,
        "rrf_k": RRF_K,
        "views": view_names,
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_JSON.name)
    log.info("Cycle 4.2 multi-view RRF OK.")


if __name__ == "__main__":
    main()
