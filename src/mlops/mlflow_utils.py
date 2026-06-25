"""Helpers MLflow partagés — instrumentation LIVE des entraînements (Cycle 11, R5).

Pattern idéal (vs logging rétroactif) : chaque script d'entraînement (M1-M6)
ouvre un run MLflow et logge **au moment de l'entraînement** ses params, metrics,
le modèle (avec signature + input_example pour validation au serving), la lignée
de données (`log_input`) et des tags de traçabilité (git commit, cycle).

Backend SQLite (`mlflow.db`), artefacts `mlartifacts/` (déprécié file store, cf. fix C11).

Usage dans un script d'entraînement :

    from src.mlops.mlflow_utils import setup_mlflow, log_training_run
    setup_mlflow()
    ... entraînement ...
    log_training_run(
        model_id="svm-embed_v1", model=clf, hyperparams={...}, results={...},
        x_example=X_val[:2], sklearn=True, n_train=..., register=True,
    )
"""

from __future__ import annotations

import logging
import os
import subprocess

import mlflow
import mlflow.sklearn
import numpy as np

from src.config import REPO_ROOT

log = logging.getLogger(__name__)

EXPERIMENT_NAME = "rakuten-mvp"
# MLflow tracking URI : env var `MLFLOW_TRACKING_URI` prioritaire (D-027 :
# http://mlflow-server:5000 en Compose), fallback sqlite local pour dev hôte
# sans Docker (rétrocompat workflow C11). Idem pour artifact_location.
_DEFAULT_TRACKING_URI = f"sqlite:///{(REPO_ROOT / 'mlflow.db').as_posix()}"
TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", _DEFAULT_TRACKING_URI)
# Si le tracking est un serveur HTTP, ne PAS forcer un artifact_location local :
# c'est le serveur (cf. --default-artifact-root s3://...) qui décide. Pour le
# fallback sqlite local, on garde l'ancien dossier mlartifacts/ hôte.
_HTTP_BACKEND = TRACKING_URI.startswith(("http://", "https://"))
ARTIFACTS_URI = None if _HTTP_BACKEND else (REPO_ROOT / "mlartifacts").as_uri()
REGISTERED_MODEL = "rakuten-classifier"

_SETUP_DONE = False


def setup_mlflow() -> None:
    """Configure tracking + expérience (idempotent).

    Tracking : `MLFLOW_TRACKING_URI` env var (D-027) ou sqlite local par défaut.
    artifact_location : transmis seulement en backend local (le serveur HTTP
    décide via `--default-artifact-root`).
    """
    global _SETUP_DONE
    mlflow.set_tracking_uri(TRACKING_URI)
    if not _SETUP_DONE and mlflow.get_experiment_by_name(EXPERIMENT_NAME) is None:
        mlflow.create_experiment(EXPERIMENT_NAME, artifact_location=ARTIFACTS_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    _SETUP_DONE = True


def git_commit() -> str:
    """SHA court du commit courant (tag de traçabilité), ou 'unknown'."""
    try:
        # noqa S607 : binaire `git` du PATH voulu (un chemin absolu ne serait pas portable).
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _flatten_metrics(results: dict) -> dict[str, float]:
    """Aplati results.{val,test}.{f1_weighted,...} → {test_f1_weighted: ...}."""
    out: dict[str, float] = {}
    for split in ("val", "test"):
        res = results.get(split, {})
        for k, v in res.items():
            if isinstance(v, int | float):
                out[f"{split}_{k}"] = float(v)
    return out


def log_training_run(
    model_id: str,
    *,
    model: object | None,
    hyperparams: dict,
    results: dict,
    x_example: np.ndarray | list | None = None,
    sklearn: bool = False,
    n_train: int | None = None,
    duration_train_sec: float | None = None,
    cycle: str = "3",
    register: bool = False,
    promote_production: bool = False,
) -> str:
    """Ouvre un run MLflow et logge params + metrics + modèle (signature) + tags.

    Args:
        model: l'estimateur (sklearn → logged_model registrable ; sinon artefact).
        x_example: échantillon d'entrée pour inférer la signature + input_example.
        sklearn: True → mlflow.sklearn.log_model (signature). False → pas de model log.
        register: enregistre au Model Registry (REGISTERED_MODEL).
        promote_production: pose l'alias @Production sur cette version.

    Returns:
        run_id.
    """
    setup_mlflow()
    with mlflow.start_run(run_name=model_id) as run:
        mlflow.set_tags({"model_id": model_id, "cycle": cycle, "git_commit": git_commit()})
        mlflow.log_params({k: str(v) for k, v in hyperparams.items()})
        if n_train is not None:
            mlflow.log_param("n_train", n_train)
        for name, val in _flatten_metrics(results).items():
            mlflow.log_metric(name, val)
        if duration_train_sec is not None:
            mlflow.log_metric("duration_train_sec", float(duration_train_sec))

        registered_version: str | None = None
        if sklearn and model is not None:
            from mlflow.models.signature import infer_signature

            signature = None
            input_example = None
            if x_example is not None:
                try:
                    preds = model.predict(x_example)
                    signature = infer_signature(x_example, preds)
                    # input_example seulement pour entrée numérique (ndarray) : pour un
                    # pipeline texte (liste de str), la validation serving MLflow casse
                    # ('int has no attribute lower') → on garde la signature seule.
                    if isinstance(x_example, np.ndarray):
                        input_example = x_example
                except Exception as e:  # noqa: BLE001
                    log.warning("signature infer échouée pour %s : %s", model_id, e)
            try:
                info = mlflow.sklearn.log_model(
                    model,
                    name="model",
                    signature=signature,
                    input_example=input_example,
                    registered_model_name=REGISTERED_MODEL if register else None,
                )
                # version créée PAR CET appel (ordre-indépendant, vs "max version")
                registered_version = getattr(info, "registered_model_version", None)
            except Exception as e:  # noqa: BLE001
                # Dégradation propre : params/metrics restent loggés (SQLite), mais le
                # push d'artefact échoue si le store n'est pas inscriptible — ex. retrain
                # in-container, dont le chemin d'artefact absolu de l'hôte est invisible
                # (cf. D-023). Portabilité réelle = MLflow server + MinIO au Cycle 13.4.
                log.warning(
                    "log_model artefact/registry échoué pour %s (run gardé, métriques OK) : %s",
                    model_id,
                    e,
                )
                mlflow.set_tag("artifact_logging", "deferred")

        if promote_production and registered_version is not None:
            from mlflow.tracking import MlflowClient

            MlflowClient().set_registered_model_alias(
                REGISTERED_MODEL, "Production", registered_version
            )
            log.info("  → %s v%s promu @Production", model_id, registered_version)

        return run.info.run_id
