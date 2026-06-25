"""M4 — MLP head sur embeddings text (Cycle 3.1 / C12).

MLP simple (2 couches) sur les embeddings text Arctic 1024 dim. Cible :
F1 ≥ 0,90 (meilleur attendu de M1-M4 sur embeddings denses).

Architecture : 1024 → 512 → 256 → 4 classes (softmax)
Activation : ReLU + dropout 0.2
Optimizer : Adam, early stopping sur val loss

Plus rapide que RF (M3) sur grand volume car GPU-friendly via PyTorch.
Mais on utilise sklearn MLPClassifier ici par simplicité (CPU mais plus
simple qu'une boucle PyTorch custom — Cycle 3 = baselines, pas SOTA).

Sortie :
- `data/models/mlp-embed_v1.joblib`
- `reports/04_classifiers_bench/m4_mlp.json`

Lance :

    python -m src.classifiers.05_mlp
"""

from __future__ import annotations

import json
import logging
import time

import joblib
import numpy as np
import polars as pl
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder

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

MODEL_NAME = "mlp-embed_v1"
HIDDEN_LAYERS = (512, 256)
BATCH_SIZE = 256
MAX_ITER = 30  # peut s'arrêter avant via early stopping

# Sample stratifié train pour speed (MLP sur 3M × 1024 × 30 epochs = 2-4h)
# 500k items × 1024 × 30 epochs sur CPU = ~30-60 min.
# Anti-leakage préservé : sample côté train uniquement, val + test entiers.
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
    log.info("=== M4 MLP sur embeddings text Arctic ===")
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

    log.info(
        "Train MLP hidden=%s batch=%d max_iter=%d early_stopping…",
        HIDDEN_LAYERS,
        BATCH_SIZE,
        MAX_ITER,
    )
    t_train = time.time()
    mlp = MLPClassifier(
        hidden_layer_sizes=HIDDEN_LAYERS,
        activation="relu",
        solver="adam",
        batch_size=BATCH_SIZE,
        max_iter=MAX_ITER,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=3,
        random_state=SEED,
        verbose=True,
    )
    # sklearn ≥1.6 : early_stopping fait np.isnan(y_pred) en interne → crash si y est
    # du texte. On encode les labels en entiers (LabelEncoder, classes triées =
    # même ordre que `sorted(set(y))`) puis on redécode les prédictions à l'éval.
    label_encoder = LabelEncoder()
    y_train_enc = label_encoder.fit_transform(y_train)
    mlp.fit(X_train, y_train_enc)
    duration_train = time.time() - t_train
    log.info(
        "  Train OK en %.1fs (%.1f min), n_iter=%d",
        duration_train,
        duration_train / 60,
        mlp.n_iter_,
    )

    results = {}
    for split_name, X_eval, y_eval in [("val", X_val, y_val), ("test", X_test, y_test)]:
        log.info("Eval sur %s…", split_name)
        t_eval = time.time()
        # mlp prédit des entiers (cf. LabelEncoder) → on redécode en labels texte ;
        # predict_proba garde l'ordre des colonnes = label_encoder.classes_ (trié).
        y_pred = label_encoder.inverse_transform(mlp.predict(X_eval))
        y_proba = mlp.predict_proba(X_eval)
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

    joblib.dump(mlp, OUT_MODEL)
    full_metrics = {
        "model": MODEL_NAME,
        "type": "MLP head 1024→512→256→C",
        "perimeter": list(CATEGORIES),
        "n_train": X_train.shape[0],
        "n_val": X_val.shape[0],
        "n_test": X_test.shape[0],
        "embed_dim": X_train.shape[1],
        "hyperparams": {
            "hidden_layer_sizes": list(HIDDEN_LAYERS),
            "batch_size": BATCH_SIZE,
            "max_iter": MAX_ITER,
            "early_stopping": True,
            "train_sample_size": TRAIN_SAMPLE_SIZE,
            "seed": SEED,
        },
        "duration_train_sec": round(duration_train, 1),
        "n_iter_actual": mlp.n_iter_,
        # mlp prédit des entiers ; mapping index→catégorie (ordre predict_proba)
        "label_classes": label_encoder.classes_.tolist(),
        "results": results,
    }
    OUT_METRICS.write_text(json.dumps(full_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s + %s", OUT_MODEL.name, OUT_METRICS.name)

    # MLflow LIVE (R5) : run loggé au moment du train + signature + Registry
    log_training_run(
        MODEL_NAME,
        model=mlp,
        hyperparams=full_metrics["hyperparams"],
        results=results,
        x_example=X_val[:2],
        sklearn=True,
        n_train=int(X_train.shape[0]),
        duration_train_sec=duration_train,
        cycle="3",
        register=True,
    )

    log.info("\nM4 MLP OK.")


if __name__ == "__main__":
    main()
