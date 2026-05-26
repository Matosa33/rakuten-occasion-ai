"""Tests du promote gate champion/challenger (Cycle 12.3, D-024)."""

from __future__ import annotations

import mlflow
import pytest
from mlflow.tracking import MlflowClient
from sklearn.dummy import DummyClassifier

from src.mlops import mlflow_utils, promote_gate

REG = mlflow_utils.REGISTERED_MODEL


@pytest.fixture
def tmp_tracking(tmp_path, monkeypatch):
    """MLflow temporaire isolé + setup_mlflow patché dans les deux modules."""
    uri = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    art = (tmp_path / "art").as_uri()

    def fake_setup() -> None:
        mlflow.set_tracking_uri(uri)
        if mlflow.get_experiment_by_name("t") is None:
            mlflow.create_experiment("t", artifact_location=art)
        mlflow.set_experiment("t")

    monkeypatch.setattr(mlflow_utils, "setup_mlflow", fake_setup)
    monkeypatch.setattr(promote_gate, "setup_mlflow", fake_setup)
    fake_setup()
    return MlflowClient(tracking_uri=uri)


def _log_version(f1: float) -> str:
    """Crée un run + version registry avec la métrique demandée. Retourne la version."""
    dummy = DummyClassifier(strategy="most_frequent").fit([[0], [1]], [0, 1])
    with mlflow.start_run():
        mlflow.log_metric("test_f1_weighted", f1)
        info = mlflow.sklearn.log_model(dummy, name="model", registered_model_name=REG)
    return info.registered_model_version


def test_promote_si_challenger_meilleur(tmp_tracking):
    """Challenger ≥ champion + ε → alias @Production bouge."""
    client = tmp_tracking
    v1 = _log_version(0.90)
    client.set_registered_model_alias(REG, "Production", v1)
    v2 = _log_version(0.95)

    result = promote_gate.decide_and_promote()

    assert result["decision"] == "promoted"
    assert result["promoted"] is True
    assert result["version"] == v2
    assert client.get_model_version_by_alias(REG, "Production").version == v2


def test_kept_si_challenger_inferieur(tmp_tracking):
    """Challenger < champion → champion conservé, alias inchangé, tag kept."""
    client = tmp_tracking
    v1 = _log_version(0.95)
    client.set_registered_model_alias(REG, "Production", v1)
    v2 = _log_version(0.90)

    result = promote_gate.decide_and_promote()

    assert result["decision"] == "kept"
    assert result["promoted"] is False
    assert client.get_model_version_by_alias(REG, "Production").version == v1
    assert client.get_model_version(REG, v2).tags.get("promote_decision") == "kept"


def test_skipped_si_aucun_challenger(tmp_tracking):
    """D-023 : pas de nouvelle version créée (latest == @Production) → skip honnête."""
    client = tmp_tracking
    v1 = _log_version(0.90)
    client.set_registered_model_alias(REG, "Production", v1)

    result = promote_gate.decide_and_promote()

    assert result["decision"] == "skipped_no_challenger"
    assert result["promoted"] is False
    assert client.get_model_version_by_alias(REG, "Production").version == v1
