"""DAG `rakuten_drift_check` - boucle fermée MLOps (Cycle 12.3, D-024).

Quotidien. Calcule la dérive (Evidently) entre `train` (référence) et un échantillon
courant. Si la part de features driftées dépasse le seuil → **déclenche
`rakuten_retrain`** via TriggerDagRunOperator. Sinon : skip (rien à faire).

Le pattern *closed-loop SOTA* est délibérément en **deux DAGs séparés** : le drift
check (léger, fréquent, lecture seule) et le retrain (lourd, conditionnel). Cf.
`src.monitoring.drift_detection` et `infra/airflow/dags/rakuten_retrain_dag.py`.
"""

from __future__ import annotations

import logging
from datetime import datetime

from airflow.models.dag import DAG
from airflow.operators.python import ShortCircuitOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

log = logging.getLogger(__name__)


def detect_drift_callable() -> bool:
    """Calcule la dérive ; renvoie True → suite du DAG ; False → skip (ShortCircuit)."""
    from src.monitoring.drift_detection import detect_drift

    result = detect_drift()
    log.info(
        "Drift = %s (share=%.2f, drifted_cols=%s)",
        result["drift_detected"],
        result["drift_share"],
        result["drifted_columns_count"],
    )
    # Push des métriques batch vers le Pushgateway (dashboard Grafana "drift"),
    # que le drift soit détecté ou non. Best-effort : jamais bloquant (R15).
    try:
        from src.monitoring.push_metrics import push_drift_metrics

        push_drift_metrics(result)
    except Exception as e:  # noqa: BLE001 - observabilité best-effort
        log.warning("push_drift_metrics KO (non bloquant) : %s", e)
    return bool(result["drift_detected"])


with DAG(
    dag_id="rakuten_drift_check",
    description="Détection drift Evidently → trigger rakuten_retrain si dérive (D-024)",
    start_date=datetime(2026, 5, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["rakuten", "mlops", "drift"],
    doc_md=__doc__,
) as dag:
    t_detect = ShortCircuitOperator(
        task_id="detect_drift",
        python_callable=detect_drift_callable,
    )

    t_trigger = TriggerDagRunOperator(
        task_id="trigger_retrain",
        trigger_dag_id="rakuten_retrain",
        wait_for_completion=False,
        reset_dag_run=False,
    )

    t_detect >> t_trigger
