"""Cycle 11.1 + 11.2 — MLflow tracking + Model Registry (rembourse R5).

R5 (golden_rules) : chaque run d'entraînement DOIT être tracké MLflow (params,
metrics, artifacts) ; les modèles servis sont registered avec alias `@Production`.

Les modèles M1-M8 ont été entraînés aux Cycles 3/4/7 AVANT que MLflow soit câblé
(dette R5 assumée, cf. state.md). Ce script **logge rétroactivement** chaque modèle
depuis ses rapports JSON (`reports/**/*.json`) : un run MLflow par modèle avec ses
params + metrics + artefacts, puis enregistrement au Model Registry et promotion du
vainqueur (M1, F1_w=0.954) en alias `@Production`.

Tracking store : local file (`mlruns/`, gitignored). Pas de serveur requis pour la démo.

Lance :

    python -m src.mlops.01_mlflow_log_runs
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from src.config import (
    DATA_MODELS,
    REPO_ROOT,
    REPORTS_CLASSIFIERS,
    REPORTS_PRICING,
    REPORTS_RETRIEVAL,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

EXPERIMENT_NAME = "rakuten-mvp"
REGISTERED_MODEL = "rakuten-classifier"
# @Production = M5 (TF-IDF) : meilleur classifieur PORTABLE (rechargeable sans l'index
# FAISS 13 GB), F1_w=0.9503. M1 (FAISS k-NN, 0.954) est le vainqueur bench mais couplé
# à l'index (servi comme M7 retrieval) → tracké, pas promu comme modèle portable. Cf. D-020.
PRODUCTION_MODEL_ID = "m5_tfidf_linsvc_v1"

# Modèles classifieurs (rapport JSON homogène results.{val,test})
CLASSIFIER_REPORTS = [
    "m1_knn_v1",
    "m2_svm_v1",
    "m4_mlp_v1",
    "m5_tfidf_linsvc_v1",
    "m6_fusion_v1",
]
# Modèles sklearn portables (registrables via mlflow.sklearn) vs artefacts bruts
SKLEARN_PORTABLE = {"m2_svm_v1", "m4_mlp_v1", "m5_tfidf_linsvc_v1"}


def _log_classifier(model_id: str) -> str | None:
    """Logge un classifieur depuis son JSON. Retourne le run_id ou None si absent."""
    path = REPORTS_CLASSIFIERS / f"{model_id}.json"
    if not path.exists():
        log.warning("  %s absent, skip", path.name)
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    test = data.get("results", {}).get("test", {})
    val = data.get("results", {}).get("val", {})

    with mlflow.start_run(run_name=model_id) as run:
        mlflow.set_tags(
            {
                "model_id": model_id,
                "type": data.get("type", "?"),
                "cycle": "3",
                "perimeter": ",".join(data.get("perimeter", [])),
            }
        )
        hp = data.get("hyperparams", {})
        mlflow.log_params({k: str(v) for k, v in hp.items()})
        for split, res in (("test", test), ("val", val)):
            for metric in ("f1_weighted", "f1_macro", "accuracy", "top_3_accuracy", "ece"):
                if metric in res and isinstance(res[metric], int | float):
                    mlflow.log_metric(f"{split}_{metric}", float(res[metric]))
        if "duration_train_sec" in data:
            mlflow.log_metric("duration_train_sec", float(data["duration_train_sec"]))
        mlflow.log_artifact(str(path), artifact_path="report")
        joblib_path = DATA_MODELS / f"{model_id}.joblib"
        logged_model = False
        if joblib_path.exists():
            if model_id in SKLEARN_PORTABLE:
                # Modèle sklearn portable → logged_model MLflow (registrable)
                import joblib

                model = joblib.load(joblib_path)
                mlflow.sklearn.log_model(model, name="model")
                logged_model = True
            else:
                # M1 (FAISS placeholder) / M6 (dict fusion) → artefact brut
                mlflow.log_artifact(str(joblib_path), artifact_path="model_artifact")
        log.info("  %s logué (test_f1_w=%.4f)", model_id, test.get("f1_weighted", 0))
        return run.info.run_id if logged_model else None


def _log_simple(name: str, report_path: Path, cycle: str, metrics: dict[str, float]) -> None:
    """Logge un run générique (M7 retrieval, M8 pricing) avec métriques fournies."""
    if not report_path.exists():
        log.warning("  %s absent, skip", report_path.name)
        return
    with mlflow.start_run(run_name=name):
        mlflow.set_tags({"model_id": name, "cycle": cycle})
        for k, v in metrics.items():
            mlflow.log_metric(k, v)
        mlflow.log_artifact(str(report_path), artifact_path="report")
        log.info("  %s logué", name)


def main() -> None:
    log.info("=== Cycle 11.1+11.2 — MLflow tracking + Registry (R5) ===")
    mlflow.set_tracking_uri(f"file:{(REPO_ROOT / 'mlruns').as_posix()}")
    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()

    # 1. Log classifieurs M1-M6
    log.info("--- Classifieurs M1-M6 ---")
    run_ids: dict[str, str] = {}
    for model_id in CLASSIFIER_REPORTS:
        rid = _log_classifier(model_id)
        if rid:
            run_ids[model_id] = rid

    # 2. Log M7 (FAISS retrieval) + M8 (pricing) depuis leurs JSON
    log.info("--- M7 retrieval + M8 pricing ---")
    faiss_path = REPORTS_RETRIEVAL / "faiss_bench.json"
    if faiss_path.exists():
        fb = json.loads(faiss_path.read_text(encoding="utf-8"))
        hnsw = fb.get("results", {}).get("hnsw", {})
        _log_simple(
            "m7_faiss_hnsw_v1",
            faiss_path,
            "4",
            {
                "recall_at_1": hnsw.get("recall_at_1", 0),
                "recall_at_10": hnsw.get("recall_at_10", 0),
                "latency_ms": hnsw.get("latency_ms_per_query", 0),
            },
        )
    _log_simple("m8_pricing_v1", REPORTS_PRICING / "pricing_v1.json", "7", {})

    # 3. Registry : enregistrer les classifieurs + promouvoir M1 @Production
    log.info("--- Model Registry + alias @Production ---")
    import contextlib

    with contextlib.suppress(Exception):  # déjà existant
        client.create_registered_model(REGISTERED_MODEL)

    prod_version = None
    for model_id, rid in run_ids.items():
        model_uri = f"runs:/{rid}/model"
        try:
            mv = mlflow.register_model(model_uri, REGISTERED_MODEL, tags={"model_id": model_id})
            if model_id == PRODUCTION_MODEL_ID:
                prod_version = mv.version
        except Exception as e:  # noqa: BLE001 — artefact model absent (placeholder)
            log.warning("  register %s échoué : %s", model_id, e)

    if prod_version:
        client.set_registered_model_alias(REGISTERED_MODEL, "Production", prod_version)
        log.info("  → %s v%s promu @Production", PRODUCTION_MODEL_ID, prod_version)
    else:
        log.warning("  Vainqueur %s non enregistré (artefact model absent)", PRODUCTION_MODEL_ID)

    log.info("MLflow tracking OK. UI : `mlflow ui --backend-store-uri file:./mlruns`")


if __name__ == "__main__":
    main()
