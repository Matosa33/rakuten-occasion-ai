"""M3 — RandomForest sur embeddings text (Cycle 3.1 / C12).

RandomForest est non-linéaire interprétable. Avantages :
- Capture des interactions non-linéaires entre dimensions d'embeddings
- SHAP TreeExplainer (Cycle 8) → explainability native
- class_weight balanced absorbe B1

Inconvénients :
- Lent à train sur 3M × 1024 dim (n_estimators × profondeur × N samples)
- Mémoire : ~quelques GB par estimator profond
- Sortie joblib lourde (~hundreds of MB)

Hyperparams choisis pour tenir RAM et temps :
- n_estimators=300 (compromis variance vs durée)
- max_depth=20 (évite l'overfit massif sur 1024 dim)
- max_features='sqrt' (32 dim par split — réduction nécessaire en haute dim)

Sortie :
- `data/models/m3_rf_v1.joblib`
- `reports/04_classifiers_bench/m3_rf.json`

Lance :

    python -m src.classifiers.04_rf
"""

from __future__ import annotations

import json
import logging
import time

import joblib
import numpy as np
import polars as pl
from sklearn.ensemble import RandomForestClassifier

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

MODEL_NAME = "m3_rf_v1"
N_ESTIMATORS = 300
MAX_DEPTH = 20
MAX_FEATURES = "sqrt"

OUT_MODEL = DATA_MODELS / f"{MODEL_NAME}.joblib"
OUT_METRICS = REPORTS_CLASSIFIERS / f"{MODEL_NAME}.json"


def _load_split(split_name: str) -> tuple[np.ndarray, np.ndarray]:
    emb_path = DATA_EMBEDDINGS / "text" / f"text_arctic_{split_name}.npy"
    if not emb_path.exists():
        raise FileNotFoundError(f"{emb_path} introuvable.")
    X = np.load(emb_path).astype(np.float32)
    df = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet", columns=["_source_category"]
    )
    y = df["_source_category"].to_numpy()
    return X, y


def main() -> None:
    log.info("=== M3 RandomForest sur embeddings text Arctic ===")
    DATA_MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS_CLASSIFIERS.mkdir(parents=True, exist_ok=True)

    if OUT_MODEL.exists():
        log.info("→ %s déjà présent, skip", OUT_MODEL.name)
        return

    log.info("Lecture embeddings…")
    t0 = time.time()
    X_train, y_train = _load_split("train")
    X_val, y_val = _load_split("val")
    X_test, y_test = _load_split("test")
    log.info(
        "  train=%s, val=%s, test=%s, dim=%d (%.1fs)",
        f"{X_train.shape[0]:_}",
        f"{X_val.shape[0]:_}",
        f"{X_test.shape[0]:_}",
        X_train.shape[1],
        time.time() - t0,
    )

    log.info(
        "Train RF n_estimators=%d max_depth=%d max_features=%s n_jobs=-1 balanced…",
        N_ESTIMATORS,
        MAX_DEPTH,
        MAX_FEATURES,
    )
    t_train = time.time()
    rf = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        max_features=MAX_FEATURES,
        class_weight="balanced",
        random_state=SEED,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    duration_train = time.time() - t_train
    log.info("  Train OK en %.1fs (%.1f min)", duration_train, duration_train / 60)

    results = {}
    for split_name, X_eval, y_eval in [("val", X_val, y_val), ("test", X_test, y_test)]:
        log.info("Eval sur %s…", split_name)
        t_eval = time.time()
        y_pred = rf.predict(X_eval)
        y_proba = rf.predict_proba(X_eval)
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
            "  %s : F1_w=%.4f, F1_m=%.4f, acc=%.4f, ECE=%.4f (%.1fs)",
            split_name,
            metrics["f1_weighted"],
            metrics["f1_macro"],
            metrics["accuracy"],
            ece,
            duration_eval,
        )
        results[split_name] = {
            **metrics,
            "ece": round(ece, 4),
            "per_class_f1": {k: round(v, 4) for k, v in per_class_f1.items()},
            "duration_eval_sec": round(duration_eval, 2),
        }

    # Pour SHAP Cycle 8 : feature importances disponibles via rf.feature_importances_
    log.info(
        "Top-10 feature importances : %s",
        [round(v, 4) for v in sorted(rf.feature_importances_, reverse=True)[:10]],
    )

    joblib.dump(rf, OUT_MODEL)
    full_metrics = {
        "model": MODEL_NAME,
        "type": "RandomForest",
        "perimeter": list(CATEGORIES),
        "n_train": X_train.shape[0],
        "n_val": X_val.shape[0],
        "n_test": X_test.shape[0],
        "embed_dim": X_train.shape[1],
        "hyperparams": {
            "n_estimators": N_ESTIMATORS,
            "max_depth": MAX_DEPTH,
            "max_features": MAX_FEATURES,
            "class_weight": "balanced",
            "n_jobs": -1,
            "seed": SEED,
        },
        "duration_train_sec": round(duration_train, 1),
        "top_10_feature_importances": [
            round(v, 4) for v in sorted(rf.feature_importances_, reverse=True)[:10]
        ],
        "results": results,
    }
    OUT_METRICS.write_text(json.dumps(full_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s + %s", OUT_MODEL.name, OUT_METRICS.name)
    log.info("\nM3 RandomForest OK.")


if __name__ == "__main__":
    main()
