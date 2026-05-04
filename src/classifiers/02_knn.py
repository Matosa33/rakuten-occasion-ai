"""M1 — k-NN sur embeddings text via FAISS HNSW (Cycle 3.1 / C12).

Baseline non-paramétrique : pour chaque produit du val/test, trouver ses
k plus proches voisins dans le train (par cosine sim sur embeddings text
Arctic), puis voter pour la catégorie pondérée par similarité.

**Implémentation** : FAISS HNSW (déjà bâti par Cycle 4.1) au lieu de
`sklearn.neighbors.KNeighborsClassifier(algorithm='brute')` — gain 1000×+
en latence. Les embeddings Arctic sont déjà L2-normalized donc IP = cosine.

Donne un upper bound de la qualité retrieval pour la classification :
si k-NN sur embeddings est mauvais, c'est que les embeddings ne capturent
pas la frontière catégorielle → repenser les encoders.

Sortie :
- `data/models/m1_knn_v1.joblib` (placeholder : index FAISS référencé via path)
- `reports/04_classifiers_bench/m1_knn_v1.json`

Lance APRÈS Cycle 2.4 (FAISS HNSW bâti) :

    python -m src.classifiers.02_knn
"""

from __future__ import annotations

import json
import logging
import time

import joblib
import numpy as np
import polars as pl

from src.classifiers.metrics import (
    compute_calibration_ece,
    compute_classification_metrics,
    compute_per_class_f1,
)
from src.config import (
    CATEGORIES,
    DATA_EMBEDDINGS,
    DATA_INDEX,
    DATA_MODELS,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_CLASSIFIERS,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "m1_knn_v1"
K_NEIGHBORS = 5
HNSW_EF_SEARCH = 64

OUT_MODEL = DATA_MODELS / f"{MODEL_NAME}.joblib"
OUT_METRICS = REPORTS_CLASSIFIERS / f"{MODEL_NAME}.json"


def _load_embeddings(split_name: str) -> np.ndarray:
    """Load embeddings text Arctic d'un split."""
    emb_path = DATA_EMBEDDINGS / "text" / f"text_arctic_{split_name}.npy"
    if not emb_path.exists():
        raise FileNotFoundError(
            f"{emb_path} introuvable. Lance d'abord src.encoders.01_text_arctic."
        )
    return np.load(emb_path).astype(np.float32)


def _load_labels(split_name: str) -> np.ndarray:
    df = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet", columns=["_source_category"]
    )
    return df["_source_category"].to_numpy()


def _knn_predict_proba(
    distances: np.ndarray,
    indices: np.ndarray,
    train_labels: np.ndarray,
    labels_sorted: list,
) -> tuple[np.ndarray, np.ndarray]:
    """Vote pondéré par similarité (IP = cosine sur normalisé) → proba softmax-like.

    Args:
        distances: shape (n_queries, k), inner product (cosine) si embeddings normalisés
        indices: shape (n_queries, k), indices dans train
        train_labels: shape (n_train,), catégorie de chaque item train
        labels_sorted: liste ordonnée des labels uniques

    Returns:
        y_pred: shape (n_queries,), label prédit (string)
        y_proba: shape (n_queries, n_classes), proba normalisée par voisin
    """
    n_queries = indices.shape[0]
    n_classes = len(labels_sorted)
    label_to_idx = {lbl: i for i, lbl in enumerate(labels_sorted)}

    y_proba = np.zeros((n_queries, n_classes), dtype=np.float32)
    # IP cosine ∈ [-1, 1] : transformer en poids positifs via shift+max
    weights = np.maximum(distances, 0.0) + 1e-6

    for q in range(n_queries):
        for k_idx in range(indices.shape[1]):
            train_i = int(indices[q, k_idx])
            if train_i < 0:  # padding FAISS
                continue
            cls_i = label_to_idx[train_labels[train_i]]
            y_proba[q, cls_i] += weights[q, k_idx]

    # Normalize proba sum=1
    row_sums = y_proba.sum(axis=1, keepdims=True)
    y_proba = np.where(row_sums > 0, y_proba / row_sums, 1.0 / n_classes)

    y_pred_idx = y_proba.argmax(axis=1)
    y_pred = np.array([labels_sorted[i] for i in y_pred_idx])
    return y_pred, y_proba


def main() -> None:
    log.info("=== M1 k-NN sur embeddings text Arctic via FAISS HNSW (Cycle 3.1 / C12) ===")
    log.info(
        "k=%d, métrique=cosine (IP sur L2-normalisé), efSearch=%d", K_NEIGHBORS, HNSW_EF_SEARCH
    )

    DATA_MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS_CLASSIFIERS.mkdir(parents=True, exist_ok=True)

    if OUT_MODEL.exists():
        log.info("→ %s déjà présent, skip", OUT_MODEL.name)
        return

    text_index_path = DATA_INDEX / "text_arctic_hnsw.index"
    if not text_index_path.exists():
        log.error("text_arctic_hnsw.index introuvable. Lance Cycle 4.1 d'abord.")
        return

    import faiss

    log.info("Lecture FAISS HNSW + labels train…")
    t0 = time.time()
    index = faiss.read_index(str(text_index_path))
    index.hnsw.efSearch = HNSW_EF_SEARCH
    train_labels = _load_labels("train")
    log.info(
        "  HNSW : %s vecteurs, train labels : %s (%.1fs)",
        f"{index.ntotal:_}",
        f"{len(train_labels):_}",
        time.time() - t0,
    )

    labels_sorted = sorted(set(train_labels))
    log.info("Labels : %s", labels_sorted)

    # Load val + test embeddings (queries)
    log.info("Lecture val + test embeddings…")
    t1 = time.time()
    X_val = _load_embeddings("val")
    X_test = _load_embeddings("test")
    y_val = _load_labels("val")
    y_test = _load_labels("test")
    log.info(
        "  val=%s, test=%s, dim=%d (%.1fs)",
        f"{X_val.shape[0]:_}",
        f"{X_test.shape[0]:_}",
        X_val.shape[1],
        time.time() - t1,
    )

    results = {}
    for split_name, X_eval, y_eval in [("val", X_val, y_val), ("test", X_test, y_test)]:
        log.info(
            "FAISS search top-%d sur %s (%s items)…", K_NEIGHBORS, split_name, f"{len(y_eval):_}"
        )
        t_eval = time.time()
        distances, indices = index.search(X_eval, K_NEIGHBORS)
        y_pred, y_proba = _knn_predict_proba(distances, indices, train_labels, labels_sorted)
        duration_eval = time.time() - t_eval

        y_eval_idx = np.array([labels_sorted.index(y) for y in y_eval])
        y_pred_idx = np.array([labels_sorted.index(y) for y in y_pred])

        metrics = compute_classification_metrics(
            y_true=y_eval_idx,
            y_pred=y_pred_idx,
            y_proba=y_proba,
            top_k=(1, 3),
            labels=list(range(len(labels_sorted))),
        )
        ece = compute_calibration_ece(y_eval_idx, y_proba)
        per_class_f1 = compute_per_class_f1(y_eval, y_pred, labels=labels_sorted)

        log.info(
            "  %s : F1_w=%.4f, F1_m=%.4f, acc=%.4f, top3=%.4f, ECE=%.4f (%.1fs, %.2f ms/query)",
            split_name,
            metrics["f1_weighted"],
            metrics["f1_macro"],
            metrics["accuracy"],
            metrics.get("top_3_accuracy", 0),
            ece,
            duration_eval,
            duration_eval * 1000 / len(y_eval),
        )

        results[split_name] = {
            **metrics,
            "ece": round(ece, 4),
            "per_class_f1": {k: round(v, 4) for k, v in per_class_f1.items()},
            "duration_eval_sec": round(duration_eval, 2),
        }

    # Placeholder artifact (le vrai "modèle" est l'index FAISS)
    placeholder = {
        "model_type": "k-NN via FAISS HNSW",
        "k": K_NEIGHBORS,
        "ef_search": HNSW_EF_SEARCH,
        "index_path": str(text_index_path),
        "labels_sorted": labels_sorted,
        "note": "Predict via FAISS index search — refer to data/index/text_arctic_hnsw.index",
    }
    joblib.dump(placeholder, OUT_MODEL)

    full_metrics = {
        "model": MODEL_NAME,
        "type": "k-NN via FAISS HNSW (cosine, weighted by similarity)",
        "perimeter": list(CATEGORIES),
        "n_train": int(index.ntotal),
        "n_val": int(X_val.shape[0]),
        "n_test": int(X_test.shape[0]),
        "embed_dim": int(X_val.shape[1]),
        "embed_source": "text/text_arctic_*.npy",
        "hyperparams": {
            "k": K_NEIGHBORS,
            "metric": "cosine (IP on L2-normalized)",
            "weights": "similarity (max(IP, 0))",
            "index": "HNSW (M=32, efSearch=64)",
            "seed": SEED,
        },
        "results": results,
    }
    OUT_METRICS.write_text(json.dumps(full_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s + %s", OUT_MODEL.name, OUT_METRICS.name)
    log.info("M1 k-NN via FAISS OK.")


if __name__ == "__main__":
    main()
