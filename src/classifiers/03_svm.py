"""svm-embed - LinearSVC + Platt sur embeddings text (Cycle 3.1 / C12).

LinearSVC sur les embeddings text Arctic (1024 dim) avec calibration Platt
pour avoir des probabilités. Comparable à tfidf-svm (TF-IDF + LinearSVC) mais
sur un input dense sémantique au lieu d'un input sparse lexical.

Sortie :
- `data/models/svm-embed_v1.joblib`
- `reports/04_classifiers_bench/m2_svm.json`

Lance :

    python -m src.classifiers.03_svm
"""

from __future__ import annotations

import json
import logging
import time

import joblib
import numpy as np
import polars as pl
from sklearn.calibration import CalibratedClassifierCV
from sklearn.svm import LinearSVC

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
from src.mlops.mlflow_utils import log_training_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "svm-embed_v1"
C_PARAM = 1.0
CALIBRATION_CV = 3

# Sample stratifié train pour speed (LinearSVC sur 3M × 1024 + Platt CV3 = 2-3h)
# 500k items × 1024 dim = ~30-60 min. Anti-leakage préservé : sample côté train uniquement,
# val + test évalués entiers (676k chacun).
TRAIN_SAMPLE_SIZE = 500_000

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
    log.info("=== svm-embed LinearSVC + Platt sur embeddings text Arctic ===")
    DATA_MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS_CLASSIFIERS.mkdir(parents=True, exist_ok=True)

    if OUT_MODEL.exists():
        log.info("→ %s déjà présent, skip", OUT_MODEL.name)
        return

    log.info("Lecture embeddings…")
    t0 = time.time()
    X_train_full, y_train_full = _load_split("train")
    X_val, y_val = _load_split("val")
    X_test, y_test = _load_split("test")
    log.info(
        "  train_full=%s, val=%s, test=%s, dim=%d (%.1fs)",
        f"{X_train_full.shape[0]:_}",
        f"{X_val.shape[0]:_}",
        f"{X_test.shape[0]:_}",
        X_train_full.shape[1],
        time.time() - t0,
    )

    # Sample stratifié train (R3 anti-leakage : sample côté train UNIQUEMENT)
    if X_train_full.shape[0] > TRAIN_SAMPLE_SIZE:
        from sklearn.model_selection import train_test_split

        log.info(
            "Sample stratifié train %s → %s", f"{X_train_full.shape[0]:_}", f"{TRAIN_SAMPLE_SIZE:_}"
        )
        X_train, _, y_train, _ = train_test_split(
            X_train_full,
            y_train_full,
            train_size=TRAIN_SAMPLE_SIZE,
            stratify=y_train_full,
            random_state=SEED,
        )
        del X_train_full, y_train_full
    else:
        X_train, y_train = X_train_full, y_train_full

    log.info("Train LinearSVC C=%g balanced + Platt CV=%d…", C_PARAM, CALIBRATION_CV)
    t_train = time.time()
    clf = CalibratedClassifierCV(
        estimator=LinearSVC(
            C=C_PARAM,
            class_weight="balanced",
            random_state=SEED,
            max_iter=2000,
            dual="auto",
        ),
        cv=CALIBRATION_CV,
        method="sigmoid",
        # Plis de calibration en parallèle (résultats identiques : mêmes plis, même seed ;
        # joblib memmappe X → pas de duplication mémoire du gros tableau d'embeddings).
        n_jobs=CALIBRATION_CV,
    )
    clf.fit(X_train, y_train)
    duration_train = time.time() - t_train
    log.info("  Train OK en %.1fs", duration_train)

    results = {}
    for split_name, X_eval, y_eval in [("val", X_val, y_val), ("test", X_test, y_test)]:
        log.info("Eval sur %s…", split_name)
        t_eval = time.time()
        y_pred = clf.predict(X_eval)
        y_proba = clf.predict_proba(X_eval)
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

    joblib.dump(clf, OUT_MODEL)
    full_metrics = {
        "model": MODEL_NAME,
        "type": "LinearSVC + Platt sur embeddings text Arctic",
        "perimeter": list(CATEGORIES),
        "n_train": X_train.shape[0],
        "n_train_sample_size": TRAIN_SAMPLE_SIZE,
        "n_val": X_val.shape[0],
        "n_test": X_test.shape[0],
        "embed_dim": X_train.shape[1],
        "hyperparams": {
            "C": C_PARAM,
            "class_weight": "balanced",
            "calibration_cv": CALIBRATION_CV,
            "train_sample_size": TRAIN_SAMPLE_SIZE,
            "seed": SEED,
        },
        "duration_train_sec": round(duration_train, 1),
        "results": results,
    }
    OUT_METRICS.write_text(json.dumps(full_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s + %s", OUT_MODEL.name, OUT_METRICS.name)

    # MLflow LIVE (R5) : run loggé au moment du train + signature + Registry
    log_training_run(
        MODEL_NAME,
        model=clf,
        hyperparams=full_metrics["hyperparams"],
        results=results,
        x_example=X_val[:2],
        sklearn=True,
        n_train=int(X_train.shape[0]),
        duration_train_sec=duration_train,
        cycle="3",
        # Tracé dans MLflow (métriques + commit) mais HORS registre : seul le challenger
        # officiel (tfidf-svm) y est versionné - un « latest » déterministe pour la gate.
        register=False,
    )

    log.info("\nM2 LinearSVC OK.")


if __name__ == "__main__":
    main()
