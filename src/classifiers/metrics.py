"""Module métriques d'évaluation pour classifieurs (Cycle 3.3 / C14).

Module **importable** (pas de main()). Centralise toutes les métriques
utilisées par les 6 modèles pour comparaison équitable.

Métriques disponibles
---------------------
- compute_classification_metrics : F1 weighted/macro, accuracy, top-K accuracy
- compute_calibration_ece        : Expected Calibration Error (10 bins)
- compute_per_class_f1           : F1 par classe (utile pour identifier
                                   cat sous-performantes — anti-B1)
- format_classification_report   : DataFrame polars synthèse pour rapport markdown

Toutes les fonctions sont **stateless** (R3 anti-leakage).
"""

from __future__ import annotations

import contextlib
from typing import Any

import numpy as np
import polars as pl
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    top_k_accuracy_score,
)


def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray | None = None,
    top_k: tuple[int, ...] = (1, 3, 5),
    labels: list[str] | None = None,
) -> dict[str, float]:
    """Calcule F1 weighted/macro, accuracy, top-K accuracy.

    Args:
        y_true: shape (N,) — labels vrais
        y_pred: shape (N,) — labels prédits (top-1)
        y_proba: shape (N, C) — probabilités par classe (pour top-K)
        top_k: tuple des K à mesurer
        labels: liste des labels possibles (sinon inféré)

    Returns:
        Dict avec clés {"f1_weighted", "f1_macro", "accuracy", "top_K_accuracy"}.
    """
    metrics = {
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
    }
    if y_proba is not None:
        for k in top_k:
            if k <= y_proba.shape[1]:
                with contextlib.suppress(ValueError):
                    metrics[f"top_{k}_accuracy"] = float(
                        top_k_accuracy_score(y_true, y_proba, k=k, labels=labels)
                    )
    return metrics


def compute_calibration_ece(y_true: np.ndarray, y_proba: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (ECE).

    Mesure l'écart entre probabilités prédites et fréquence empirique.
    Cible : < 0,05 pour svm-embed (LinearSVC + Platt) et tfidf-svm (TF-IDF + Platt).

    Args:
        y_true: shape (N,) — labels vrais (ou indices)
        y_proba: shape (N, C) — probabilités par classe
        n_bins: nombre de bins pour le binning des probas

    Returns:
        ECE ∈ [0, 1] (0 = parfaitement calibré).
    """
    confidences = y_proba.max(axis=1)
    predictions = y_proba.argmax(axis=1)
    accuracies = (predictions == y_true).astype(float)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (confidences >= bin_boundaries[i]) & (confidences < bin_boundaries[i + 1])
        if in_bin.sum() > 0:
            avg_conf = confidences[in_bin].mean()
            avg_acc = accuracies[in_bin].mean()
            ece += in_bin.mean() * abs(avg_conf - avg_acc)
    return float(ece)


def compute_per_class_f1(
    y_true: np.ndarray, y_pred: np.ndarray, labels: list[str] | None = None
) -> dict[str, float]:
    """F1 par classe — utile pour identifier les cat sous-performantes.

    Returns dict {label: f1_score}.
    """
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    if labels is None:
        labels = sorted(set(y_true) | set(y_pred))
    return {str(label): float(f) for label, f in zip(labels, f1, strict=False)}


def compute_confusion_matrix_normalized(
    y_true: np.ndarray, y_pred: np.ndarray, labels: list[str] | None = None
) -> np.ndarray:
    """Confusion matrix normalisée par ligne (ratio par true class).

    Returns matrix shape (C, C). cm[i, j] = ratio de samples de class i prédits class j.
    """
    cm = confusion_matrix(y_true, y_pred, labels=labels, normalize="true")
    return cm


def format_classification_report(
    metrics: dict[str, Any],
    model_name: str,
    n_train: int,
    n_eval: int,
    duration_train_sec: float,
    duration_eval_sec: float,
) -> pl.DataFrame:
    """Format un rapport synthétique en DataFrame polars (1 ligne par modèle).

    Utilisé en Cycle 3.3 pour comparaison tabulaire les 6 modèles.
    """
    return pl.DataFrame(
        {
            "model": [model_name],
            "n_train": [n_train],
            "n_eval": [n_eval],
            "f1_weighted": [round(metrics.get("f1_weighted", 0), 4)],
            "f1_macro": [round(metrics.get("f1_macro", 0), 4)],
            "accuracy": [round(metrics.get("accuracy", 0), 4)],
            "top_3_accuracy": [round(metrics.get("top_3_accuracy", 0), 4)],
            "top_5_accuracy": [round(metrics.get("top_5_accuracy", 0), 4)],
            "ece": [round(metrics.get("ece", 0), 4)],
            "train_sec": [round(duration_train_sec, 1)],
            "eval_sec": [round(duration_eval_sec, 2)],
        }
    )
