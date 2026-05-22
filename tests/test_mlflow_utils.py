"""Tests du helper MLflow `log_training_run` (Cycle 11/12, D-021/D-023)."""

from __future__ import annotations

import mlflow
import numpy as np
from mlflow.tracking import MlflowClient

from src.mlops import mlflow_utils


class _DummyModel:
    """Estimateur minimal (predict) pour inférer une signature."""

    classes_ = np.array(["a", "b"])

    def predict(self, x):
        return np.zeros(len(x))


def test_log_training_run_degrade_si_artefact_echoue(tmp_path, monkeypatch):
    """D-023 : si le push d'artefact échoue, le run garde params/metrics + tag deferred."""
    uri = f"sqlite:///{(tmp_path / 't.db').as_posix()}"

    def fake_setup() -> None:
        mlflow.set_tracking_uri(uri)
        if mlflow.get_experiment_by_name("t_exp") is None:
            mlflow.create_experiment("t_exp", artifact_location=(tmp_path / "art").as_uri())
        mlflow.set_experiment("t_exp")

    monkeypatch.setattr(mlflow_utils, "setup_mlflow", fake_setup)

    def boom(*_args, **_kwargs):
        raise RuntimeError("artifact store not writable (simulate conteneur, D-023)")

    monkeypatch.setattr(mlflow.sklearn, "log_model", boom)

    run_id = mlflow_utils.log_training_run(
        "test_m",
        model=_DummyModel(),
        hyperparams={"k": 1},
        results={"test": {"f1_weighted": 0.9}},
        x_example=np.array([[1.0], [2.0]]),
        sklearn=True,
        register=True,
    )

    assert run_id, "le run doit être créé malgré l'échec d'artefact"
    run = MlflowClient(tracking_uri=uri).get_run(run_id)
    assert run.data.metrics["test_f1_weighted"] == 0.9  # métriques bien loggées (SQLite)
    assert run.data.tags.get("artifact_logging") == "deferred"  # dégradation tracée
