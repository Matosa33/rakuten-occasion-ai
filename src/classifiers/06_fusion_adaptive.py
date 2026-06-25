"""fusion — Fusion adaptive multimodale (Cycle 3.4 / C15).

Méta-modèle qui combine les sorties des classifieurs les modèles de base pour produire
une prédiction finale plus robuste qu'un seul modèle.

Stratégie : fusion par moyenne pondérée des probabilités, avec α appris
par grid search sur le val set. Pour chaque cat séparément (fusion par cat
pour absorber B1).

Score final = α_text_arctic × P_M2_svm + α_text_tfidf × P_M5_tfidf
              + α_knn × P_M1_knn + α_mlp × P_M4_mlp + α_rf × P_M3_rf

(Toutes calibrées Platt → probas comparables.)

Si vision indexée disponible (Cycle 2.2 SigLIP) : ajouter une branche
classifieur visuel (à activer en post-MVP).

Sortie :
- `data/models/fusion_v1.joblib` (poids α + références aux modèles)
- `reports/04_classifiers_bench/m6_fusion.json`

Lance APRÈS les modèles de base :

    python -m src.classifiers.06_fusion_adaptive
"""

from __future__ import annotations

import json
import logging
import time
from itertools import product

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
    DATA_MODELS,
    DATA_PROCESSED_PRODUCTS,
    REPORTS_CLASSIFIERS,
    SEED,
)
from src.mlops.mlflow_utils import log_training_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "fusion_v1"
ALPHA_GRID = (0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0)

OUT_MODEL = DATA_MODELS / f"{MODEL_NAME}.joblib"
OUT_METRICS = REPORTS_CLASSIFIERS / f"{MODEL_NAME}.json"


def _load_split_emb_text(split_name: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load embeddings text + texts bruts + labels."""
    emb_path = DATA_EMBEDDINGS / "text" / f"text_arctic_{split_name}.npy"
    X_emb = np.load(emb_path).astype(np.float32)
    df = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet",
        columns=["title", "description", "_source_category"],
    )
    texts = [
        " ".join(filter(None, [t, d]))
        for t, d in zip(df["title"].fill_null(""), df["description"].fill_null(""), strict=False)
    ]
    y = df["_source_category"].to_numpy()
    return X_emb, y, texts


def _get_proba_or_skip(model_name: str, X_input, fallback_shape) -> np.ndarray | None:
    """Tente de charger un modèle et de prédire. Retourne None si modèle absent."""
    path = DATA_MODELS / f"{model_name}.joblib"
    if not path.exists():
        log.warning("  ⚠️ %s introuvable, skip dans la fusion", path.name)
        return None
    model = joblib.load(path)
    if not hasattr(model, "predict_proba"):
        log.warning("  ⚠️ %s n'a pas predict_proba (probable placeholder), skip", path.name)
        return None
    return model.predict_proba(X_input)


def main() -> None:
    log.info("=== fusion Fusion adaptive multimodale (Cycle 3.4 / C15) ===")
    log.info("Cherche grid α sur (knn-faiss, svm-embed, rf-embed, mlp-embed, tfidf-svm) prob fusion par moyenne pondérée")

    DATA_MODELS.mkdir(parents=True, exist_ok=True)
    REPORTS_CLASSIFIERS.mkdir(parents=True, exist_ok=True)

    if OUT_MODEL.exists():
        log.info("→ %s déjà présent, skip", OUT_MODEL.name)
        return

    log.info("Lecture splits + embeddings…")
    t0 = time.time()
    X_train_emb, y_train, train_texts = _load_split_emb_text("train")
    X_val_emb, y_val, val_texts = _load_split_emb_text("val")
    X_test_emb, y_test, test_texts = _load_split_emb_text("test")
    log.info(
        "  train=%s, val=%s, test=%s, dim=%d (%.1fs)",
        f"{X_train_emb.shape[0]:_}",
        f"{X_val_emb.shape[0]:_}",
        f"{X_test_emb.shape[0]:_}",
        X_train_emb.shape[1],
        time.time() - t0,
    )

    log.info("Collecte des probas les modèles de base sur val + test…")
    # knn-faiss (k-NN) skipped — placeholder ne charge pas
    # tfidf-svm (TF-IDF) prend texte brut
    probas_val = {}
    probas_test = {}
    for model_name, X_val_input, X_test_input in [
        ("svm-embed_v1", X_val_emb, X_test_emb),
        ("rf-embed_v1", X_val_emb, X_test_emb),
        ("mlp-embed_v1", X_val_emb, X_test_emb),
        ("tfidf-svm_v1", val_texts, test_texts),
    ]:
        log.info("  %s …", model_name)
        p_val = _get_proba_or_skip(model_name, X_val_input, (len(y_val), len(set(y_train))))
        p_test = _get_proba_or_skip(model_name, X_test_input, (len(y_test), len(set(y_train))))
        if p_val is not None and p_test is not None:
            probas_val[model_name] = p_val
            probas_test[model_name] = p_test

    if len(probas_val) < 2:
        log.error("Moins de 2 modèles dispo, fusion sans intérêt. Sortie.")
        return

    model_names = list(probas_val.keys())
    n_models = len(model_names)
    log.info("Fusion sur %d modèles : %s", n_models, model_names)

    # Grid search α uniformément distribué (poids sommant à 1)
    # Pour 4 modèles, grid 7^3 = 343 combinaisons (le 4e est 1 - sum) ~ rapide
    log.info("Grid search α sur %d combinaisons…", len(ALPHA_GRID) ** (n_models - 1))
    labels_sorted = sorted(set(y_train))
    y_val_idx = np.array([labels_sorted.index(y) for y in y_val])

    best_alphas = None
    best_f1 = -1.0
    n_combos_tested = 0

    if n_models == 4:
        for a1, a2, a3 in product(ALPHA_GRID, repeat=3):
            a4 = 1.0 - a1 - a2 - a3
            if a4 < 0 or a4 > 1:
                continue
            alphas = [a1, a2, a3, a4]
            fused = sum(a * probas_val[m] for a, m in zip(alphas, model_names, strict=False))
            y_fused = fused.argmax(axis=1)
            f1 = float(
                np.mean([(y_fused == y_val_idx).mean()])
            )  # accuracy proxy ; on calculera F1 weighted ensuite sur best
            n_combos_tested += 1
            if f1 > best_f1:
                best_f1 = f1
                best_alphas = alphas

    if best_alphas is None:
        # Fallback : moyenne uniforme
        log.warning("Grid search vide, fallback moyenne uniforme")
        best_alphas = [1.0 / n_models] * n_models

    log.info(
        "Meilleure combinaison α : %s (F1 val approx %.4f)",
        dict(zip(model_names, best_alphas, strict=False)),
        best_f1,
    )

    # Évaluation finale val + test avec best_alphas
    results = {}
    for split_name, probas_split, y_split in [
        ("val", probas_val, y_val),
        ("test", probas_test, y_test),
    ]:
        fused_proba = sum(
            a * probas_split[m] for a, m in zip(best_alphas, model_names, strict=False)
        )
        y_pred_idx = fused_proba.argmax(axis=1)
        y_pred = np.array([labels_sorted[i] for i in y_pred_idx])
        y_split_idx = np.array([labels_sorted.index(y) for y in y_split])

        metrics = compute_classification_metrics(
            y_true=y_split_idx,
            y_pred=y_pred_idx,
            y_proba=fused_proba,
            top_k=(1, 3),
            labels=list(range(len(labels_sorted))),
        )
        ece = compute_calibration_ece(y_split_idx, fused_proba)
        per_class_f1 = compute_per_class_f1(y_split, y_pred, labels=labels_sorted)
        log.info(
            "  %s fusion : F1_w=%.4f, F1_m=%.4f, acc=%.4f, ECE=%.4f",
            split_name,
            metrics["f1_weighted"],
            metrics["f1_macro"],
            metrics["accuracy"],
            ece,
        )
        results[split_name] = {
            **metrics,
            "ece": round(ece, 4),
            "per_class_f1": {k: round(v, 4) for k, v in per_class_f1.items()},
        }

    fusion_artifact = {
        "model_type": "Fusion adaptive (weighted average of probas)",
        "model_names": model_names,
        "alphas": best_alphas,
        "labels_sorted": labels_sorted,
        "seed": SEED,
    }
    joblib.dump(fusion_artifact, OUT_MODEL)

    full_metrics = {
        "model": MODEL_NAME,
        "type": "Fusion adaptive",
        "perimeter": list(CATEGORIES),
        "fusion_models": model_names,
        "alphas_optimal": dict(zip(model_names, best_alphas, strict=False)),
        "n_combos_tested": n_combos_tested,
        "best_f1_val_acc_proxy": round(best_f1, 4),
        "results": results,
    }
    OUT_METRICS.write_text(json.dumps(full_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("→ %s + %s", OUT_MODEL.name, OUT_METRICS.name)

    # MLflow LIVE (R5) : tracking params (α optimaux) + metrics. Méta-modèle = dict
    # de poids référençant les modèles de base → sklearn=False, non registré (cf. D-020).
    log_training_run(
        MODEL_NAME,
        model=None,
        hyperparams={"alphas": dict(zip(model_names, best_alphas, strict=False)), "seed": SEED},
        results=results,
        sklearn=False,
        cycle="3",
    )

    log.info("\nM6 Fusion adaptive OK.")


if __name__ == "__main__":
    main()
