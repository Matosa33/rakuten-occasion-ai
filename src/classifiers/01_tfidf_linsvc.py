"""tfidf-svm — TF-IDF + LinearSVC + Platt calibration (Cycle 3.2 / C13).

Baseline texte brut, ne nécessite pas les embeddings du Cycle 2.

Objectif
--------
Mesurer la performance de classification de catégorie (4 cat D-011)
avec un pipeline TF-IDF classique calibré, comme **baseline texte** à
laquelle comparer les modèles sur embeddings (les modèles sur embeddings) et la fusion (fusion).

Pipeline
--------
1. TfidfVectorizer (max_features=50_000, ngram_range=(1,2), sublinear_tf=True)
2. LinearSVC (C=1.0, class_weight='balanced' pour mitigation B1)
3. CalibratedClassifierCV (Platt scaling, cv=3) pour avoir des probabilités

R3 anti-leakage strict :
- fit(X_train) puis transform(X_val), transform(X_test)
- jamais fit sur val ou test

Sortie :
- `data/models/tfidf-svm_v1.joblib`
- `reports/04_classifiers_bench/m5_tfidf_linsvc.json` (métriques)

Lance ce script depuis la racine :

    python -m src.classifiers.01_tfidf_linsvc
"""

from __future__ import annotations

import json
import logging
import time

import joblib
import numpy as np
import polars as pl
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from src.classifiers.metrics import (
    compute_calibration_ece,
    compute_classification_metrics,
    compute_per_class_f1,
)
from src.config import (
    CATEGORIES,
    DATA_MODELS,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_CLASSIFIERS,
    SEED,
)
from src.mlops.mlflow_utils import log_training_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "tfidf-svm_v1"
MAX_FEATURES = 50_000
NGRAM_RANGE = (1, 2)
C_PARAM = 1.0
CALIBRATION_CV = 3

OUT_MODEL = DATA_MODELS / f"{MODEL_NAME}.joblib"
OUT_METRICS = REPORTS_CLASSIFIERS / f"{MODEL_NAME}.json"


def _load_split(split_name: str) -> tuple[list[str], np.ndarray]:
    """Load (texts, labels) d'un split products."""
    df = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet",
        columns=["title", "description", "_source_category"],
    )
    texts = [
        " ".join(filter(None, [t, d]))
        for t, d in zip(df["title"].fill_null(""), df["description"].fill_null(""), strict=False)
    ]
    labels = df["_source_category"].to_numpy()
    return texts, labels


def main() -> None:
    log.info("=== tfidf-svm TF-IDF + LinearSVC + Platt (Cycle 3.2 / C13) ===")
    log.info("Périmètre : %d catégories (D-011)", len(CATEGORIES))

    DATA_MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS_CLASSIFIERS.mkdir(parents=True, exist_ok=True)

    if OUT_MODEL.exists():
        log.info("→ %s déjà présent, skip (supprimer pour re-train)", OUT_MODEL.name)
        return

    # Lecture splits
    log.info("Lecture splits…")
    t0 = time.time()
    X_train, y_train = _load_split("train")
    X_val, y_val = _load_split("val")
    X_test, y_test = _load_split("test")
    log.info(
        "  train=%s, val=%s, test=%s (lecture %.1fs)",
        f"{len(X_train):_}",
        f"{len(X_val):_}",
        f"{len(X_test):_}",
        time.time() - t0,
    )

    # Pipeline : TF-IDF → LinearSVC calibré
    log.info(
        "Pipeline : TF-IDF(max_features=%d, ngram=%s) → LinearSVC(C=%g, balanced) → Platt CV=%d",
        MAX_FEATURES,
        NGRAM_RANGE,
        C_PARAM,
        CALIBRATION_CV,
    )
    pipe = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=MAX_FEATURES,
                    ngram_range=NGRAM_RANGE,
                    sublinear_tf=True,
                    min_df=2,
                ),
            ),
            (
                "calibrated_svc",
                CalibratedClassifierCV(
                    estimator=LinearSVC(
                        C=C_PARAM,
                        class_weight="balanced",  # mitigation B1
                        random_state=SEED,
                        max_iter=2000,
                    ),
                    cv=CALIBRATION_CV,
                    method="sigmoid",  # Platt
                ),
            ),
        ]
    )

    # Train
    log.info("Train sur %s items…", f"{len(X_train):_}")
    t_train = time.time()
    pipe.fit(X_train, y_train)
    duration_train = time.time() - t_train
    log.info("  Train terminé en %.1f sec (%.1f min)", duration_train, duration_train / 60)

    # Eval val + test
    results = {}
    for split_name, X_eval, y_eval in [("val", X_val, y_val), ("test", X_test, y_test)]:
        log.info("Eval sur %s (%s items)…", split_name, f"{len(X_eval):_}")
        t_eval = time.time()
        y_pred = pipe.predict(X_eval)
        y_proba = pipe.predict_proba(X_eval)
        duration_eval = time.time() - t_eval

        labels_sorted = sorted(set(y_train))
        # Convert labels (str cat) to indices for top_k_accuracy_score
        y_eval_idx = np.array([labels_sorted.index(y) for y in y_eval])

        metrics = compute_classification_metrics(
            y_true=y_eval_idx,
            y_pred=np.array([labels_sorted.index(y) for y in y_pred]),
            y_proba=y_proba,
            top_k=(1, 3),  # 4 cat seulement, top-5 sans intérêt
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

    # Sauvegarde modèle + métriques
    joblib.dump(pipe, OUT_MODEL)
    size_mb = OUT_MODEL.stat().st_size / 1_048_576
    log.info("→ %s (%.1f MB)", OUT_MODEL.name, size_mb)

    full_metrics = {
        "model": MODEL_NAME,
        "type": "TF-IDF + LinearSVC + Platt",
        "perimeter": list(CATEGORIES),
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test),
        "hyperparams": {
            "max_features": MAX_FEATURES,
            "ngram_range": list(NGRAM_RANGE),
            "C": C_PARAM,
            "class_weight": "balanced",
            "calibration_cv": CALIBRATION_CV,
            "calibration_method": "sigmoid",
            "seed": SEED,
        },
        "duration_train_sec": round(duration_train, 1),
        "results": results,
    }
    OUT_METRICS.write_text(json.dumps(full_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s", OUT_METRICS.name)

    # MLflow LIVE (R5) : run loggé au moment du train + signature + @Production (D-020)
    log_training_run(
        MODEL_NAME,
        model=pipe,
        hyperparams=full_metrics["hyperparams"],
        results=results,
        x_example=X_val[:2],
        sklearn=True,
        n_train=len(X_train),
        duration_train_sec=duration_train,
        cycle="3",
        register=True,
        promote_production=True,
    )

    log.info("\nM5 TF-IDF baseline OK.")


if __name__ == "__main__":
    main()
