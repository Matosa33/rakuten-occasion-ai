"""Tests statiques du DAG `rakuten_drift_check` (Cycle 12.3, D-024)."""

from __future__ import annotations

from pathlib import Path

DAG_PATH = (
    Path(__file__).resolve().parents[1]
    / "infra"
    / "airflow"
    / "dags"
    / "rakuten_drift_check_dag.py"
)


def test_drift_dag_compile():
    src = DAG_PATH.read_text(encoding="utf-8")
    compile(src, str(DAG_PATH), "exec")


def test_drift_dag_structure():
    """Le DAG drift expose detect_drift + trigger_retrain et appelle drift_detection."""
    src = DAG_PATH.read_text(encoding="utf-8")
    assert 'dag_id="rakuten_drift_check"' in src
    assert 'task_id="detect_drift"' in src
    assert 'task_id="trigger_retrain"' in src
    assert 'trigger_dag_id="rakuten_retrain"' in src
    # ShortCircuit : si pas de drift → skip trigger
    assert "ShortCircuitOperator" in src
    # appel au detector
    assert "src.monitoring.drift_detection" in src
