"""M1 — k-NN sur embeddings text (Cycle 3.1 / C12).

Baseline non-paramétrique : pour chaque produit du val/test, trouver ses
k plus proches voisins dans le train (par cosine sim sur embeddings text
Arctic), puis voter pour la catégorie.

Donne un upper bound de la qualité retrieval pour la classification :
si k-NN sur embeddings est mauvais, c'est que les embeddings ne capturent
pas la frontière catégorielle → repenser les encoders.

Sortie :
- `data/models/m1_knn_v1.joblib`
- `reports/04_classifiers_bench/m1_knn.json`

Lance ce script depuis la racine :

    python -m src.classifiers.02_knn
"""

from __future__ import annotations

import json
import logging
import time

import joblib
import numpy as np
import polars as pl
from sklearn.neighbors import KNeighborsClassifier

from src.classifiers.metrics import (
    compute_calibration_ece,
    compute_classification_metrics,
    compute_per_class_f1,
)
from src.config import (
    CATEGORIES,
    DATA_EMBEDDINGS,
    DATA_MODELS,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_CLASSIFIERS,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "m1_knn_v1"
K_NEIGHBORS = 5

OUT_MODEL = DATA_MODELS / f"{MODEL_NAME}.joblib"
OUT_METRICS = REPORTS_CLASSIFIERS / f"{MODEL_NAME}.json"


def _load_embeddings_and_labels(split_name: str) -> tuple[np.ndarray, np.ndarray]:
    """Load embeddings text + labels du split."""
    emb_path = DATA_EMBEDDINGS / "text" / f"text_arctic_{split_name}.npy"
    if not emb_path.exists():
        raise FileNotFoundError(
            f"{emb_path} introuvable. Lance d'abord src.encoders.01_text_arctic."
        )
    X = np.load(emb_path).astype(np.float32)  # FP16 → FP32 pour sklearn

    df = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet",
        columns=["_source_category"],
    )
    y = df["_source_category"].to_numpy()
    assert len(y) == X.shape[0], f"Shape mismatch : {X.shape[0]} embeddings vs {len(y)} labels"
    return X, y


def main() -> None:
    log.info("=== M1 k-NN sur embeddings text Arctic (Cycle 3.1 / C12) ===")
    log.info("k=%d, métrique=cosine (équivalente IP sur normalisés L2)", K_NEIGHBORS)

    DATA_MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS_CLASSIFIERS.mkdir(parents=True, exist_ok=True)

    if OUT_MODEL.exists():
        log.info("→ %s déjà présent, skip", OUT_MODEL.name)
        return

    log.info("Lecture embeddings + labels…")
    t0 = time.time()
    X_train, y_train = _load_embeddings_and_labels("train")
    X_val, y_val = _load_embeddings_and_labels("val")
    X_test, y_test = _load_embeddings_and_labels("test")
    log.info(
        "  train=%s, val=%s, test=%s, dim=%d (%.1fs)",
        f"{X_train.shape[0]:_}",
        f"{X_val.shape[0]:_}",
        f"{X_test.shape[0]:_}",
        X_train.shape[1],
        time.time() - t0,
    )

    # k-NN avec algo brute (cosine sur ~3M vecteurs en mémoire = lent au query
    # mais pas besoin de FAISS au Cycle 3, on accepte ~secondes de latence en eval)
    # Note : sklearn n'a pas 'cosine' natif — on passe "metric='cosine'" qui calcule
    # 1 - cos_sim. weights='distance' pondère par 1/distance.
    log.info("Train k-NN (algo brute, metric=cosine)…")
    t_train = time.time()
    knn = KNeighborsClassifier(
        n_neighbors=K_NEIGHBORS,
        algorithm="brute",
        metric="cosine",
        weights="distance",
        n_jobs=-1,
    )
    knn.fit(X_train, y_train)
    duration_train = time.time() - t_train
    log.info("  Train OK en %.1fs (k-NN = mémorisation, peu de calcul ici)", duration_train)

    # Eval
    results = {}
    for split_name, X_eval, y_eval in [("val", X_val, y_val), ("test", X_test, y_test)]:
        log.info(
            "Eval sur %s (%s items, ça peut prendre ~minutes en brute)…",
            split_name,
            f"{len(y_eval):_}",
        )
        t_eval = time.time()
        y_pred = knn.predict(X_eval)
        y_proba = knn.predict_proba(X_eval)
        duration_eval = time.time() - t_eval

        labels_sorted = sorted(set(y_train))
        y_eval_idx = np.array([labels_sorted.index(y) for y in y_eval])

        metrics = compute_classification_metrics(
            y_true=y_eval_idx,
            y_pred=np.array([labels_sorted.index(y) for y in y_pred]),
            y_proba=y_proba,
            top_k=(1, 3),
            labels=list(range(len(labels_sorted))),
        )
        ece = compute_calibration_ece(y_eval_idx, y_proba)
        per_class_f1 = compute_per_class_f1(y_eval, y_pred, labels=labels_sorted)

        log.info(
            "  %s : F1_w=%.4f, F1_m=%.4f, acc=%.4f, top3=%.4f, ECE=%.4f (eval %.1fs)",
            split_name,
            metrics["f1_weighted"],
            metrics["f1_macro"],
            metrics["accuracy"],
            metrics.get("top_3_accuracy", 0),
            ece,
            duration_eval,
        )
        log.info(
            "  %s F1 par cat : %s", split_name, {k: round(v, 3) for k, v in per_class_f1.items()}
        )

        results[split_name] = {
            **metrics,
            "ece": round(ece, 4),
            "per_class_f1": {k: round(v, 4) for k, v in per_class_f1.items()},
            "duration_eval_sec": round(duration_eval, 2),
        }

    # NB : on ne sauve PAS knn.fit (énorme : 3M vecteurs × 1024 dim = 12GB joblib).
    # En pratique, k-NN est re-fit à la demande sur les embeddings train.
    # On sauve juste un placeholder pour cohérence.
    placeholder = {
        "model_type": "KNeighborsClassifier",
        "k": K_NEIGHBORS,
        "note": "Refit at runtime from data/embeddings/text_arctic_train.npy",
    }
    joblib.dump(placeholder, OUT_MODEL)

    full_metrics = {
        "model": MODEL_NAME,
        "type": "k-NN (cosine, weighted by distance)",
        "perimeter": list(CATEGORIES),
        "n_train": X_train.shape[0],
        "n_val": X_val.shape[0],
        "n_test": X_test.shape[0],
        "embed_dim": X_train.shape[1],
        "embed_source": "text/text_arctic_*.npy",
        "hyperparams": {
            "k": K_NEIGHBORS,
            "metric": "cosine",
            "weights": "distance",
            "algorithm": "brute",
            "seed": SEED,
        },
        "duration_train_sec": round(duration_train, 1),
        "results": results,
    }
    OUT_METRICS.write_text(json.dumps(full_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_METRICS.name)
    log.info("\nM1 k-NN OK.")


if __name__ == "__main__":
    main()
