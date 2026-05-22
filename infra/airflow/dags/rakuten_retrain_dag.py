"""DAG `rakuten_retrain` — boucle de ré-entraînement orchestrée (Cycle 12.1, D-022).

L'orchestrateur orchestre, il ne calcule PAS le GPU (anti-pattern). Graphe :

    check_new_data  →  train_classifiers  →  evaluate_gate

- **check_new_data** : l'étape d'encodage GPU est une tâche AMONT ISOLÉE. En prod
  elle encode le *delta* (nouveaux items) sur un worker GPU ; en démo (VM sans GPU),
  elle est idempotente : no-op si les embeddings sont déjà matérialisés (cache/DVC).
- **train_classifiers** : ré-entraîne les têtes CPU M5/M2/M4 sur les embeddings en
  cache → log MLflow live + register `rakuten-classifier` + alias `@Production` (M5)
  via l'instrumentation du Cycle 11 (D-021).
- **evaluate_gate** : garde-fou qualité — lit le rapport du challenger et échoue le
  DAG si F1 < seuil (empêche de propager un modèle dégradé). Le *gate* explicite
  champion/challenger (promote conditionnel) = sous-todo 12.3 (boucle fermée).

Les tâches tournent dans le conteneur Airflow avec le repo monté sur /opt/rakuten
(code + data + mlflow.db live). Cf. infra/compose/docker-compose.airflow.yml.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

REPO_ROOT = Path("/opt/rakuten")
EMBEDDINGS_DIR = REPO_ROOT / "data" / "embeddings" / "text"
BENCH_DIR = REPO_ROOT / "reports" / "04_classifiers_bench"
MODELS_DIR = REPO_ROOT / "data" / "models"

# Têtes CPU ré-entraînées (M1 FAISS / M6 fusion hors boucle planifiée — cf. D-022).
RETRAIN_MODULES = [
    "src.classifiers.01_tfidf_linsvc",  # M5 (→ @Production)
    "src.classifiers.03_svm",  # M2
    "src.classifiers.05_mlp",  # M4
]
PRODUCTION_REPORT = BENCH_DIR / "m5_tfidf_linsvc_v1.json"
F1_GATE = 0.85  # garde-fou : sous ce seuil, le DAG échoue (R15 : pas de régression silencieuse)


def check_new_data() -> str:
    """Étape encode (GPU isolé) : no-op si embeddings déjà présents (démo/cache)."""
    if EMBEDDINGS_DIR.exists() and any(EMBEDDINGS_DIR.glob("*.npy")):
        log.info("Embeddings présents (%s) → encode_delta no-op (cache).", EMBEDDINGS_DIR)
        return "cached"
    # En prod : déclencher l'encodage GPU du delta sur un worker dédié.
    raise FileNotFoundError(
        f"Aucun embedding dans {EMBEDDINGS_DIR}. En prod, encoder le delta sur worker GPU "
        "(src.encoders.01_text_arctic) ; en démo, matérialiser les embeddings d'abord."
    )


def evaluate_gate() -> dict:
    """Lit le rapport du challenger M5 et applique le garde-fou qualité (F1_GATE)."""
    if not PRODUCTION_REPORT.exists():
        raise FileNotFoundError(f"Rapport introuvable : {PRODUCTION_REPORT}")
    data = json.loads(PRODUCTION_REPORT.read_text(encoding="utf-8"))
    f1 = float(data.get("results", {}).get("test", {}).get("f1_weighted", 0.0))
    log.info("Challenger M5 : test_f1_weighted=%.4f (seuil %.2f)", f1, F1_GATE)
    if f1 < F1_GATE:
        raise ValueError(f"F1 {f1:.4f} < seuil {F1_GATE} → modèle dégradé, DAG en échec.")
    log.info("Garde-fou OK : modèle ré-entraîné conforme.")
    return {"test_f1_weighted": f1, "gate_passed": True}


with DAG(
    dag_id="rakuten_retrain",
    description="Boucle de ré-entraînement CPU (encode-delta → train → eval → register) — D-022",
    start_date=datetime(2026, 5, 1),
    schedule="@weekly",
    catchup=False,
    max_active_runs=1,  # un seul retrain à la fois (évite la course sur joblibs + mlflow.db)
    tags=["rakuten", "mlops", "retrain"],
    doc_md=__doc__,
) as dag:
    t_check = PythonOperator(
        task_id="check_new_data",
        python_callable=check_new_data,
    )

    # Force le re-train (les scripts skippent si le .joblib existe) puis log MLflow live.
    t_train = BashOperator(
        task_id="train_classifiers",
        cwd="/opt/rakuten",
        bash_command=(
            "set -e; "
            "rm -f data/models/m5_tfidf_linsvc_v1.joblib "
            "data/models/m2_svm_v1.joblib data/models/m4_mlp_v1.joblib; "
            + " && ".join(f"python -m {m}" for m in RETRAIN_MODULES)
        ),
    )

    t_gate = PythonOperator(
        task_id="evaluate_gate",
        python_callable=evaluate_gate,
    )

    t_check >> t_train >> t_gate
