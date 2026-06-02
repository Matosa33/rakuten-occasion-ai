"""DAG `rakuten_retrain` — boucle de ré-entraînement fermée (C12.1+12.3, D-022/D-024).

L'orchestrateur orchestre, il ne calcule PAS le GPU. Graphe :

    check_new_data → train_classifiers → evaluate_gate → promote_gate → reimport_bento

- **check_new_data** : encode GPU = tâche amont isolée ; no-op si embeddings en cache.
- **train_classifiers** : ré-entraîne M5/M2/M4 sur embeddings, logge MLflow live (D-021,
  push d'artefact dégradé en conteneur cf. D-023 → C13.4).
- **evaluate_gate** : garde-fou qualité (F1 ≥ seuil) — échoue le DAG sous le seuil.
- **promote_gate** (12.3, D-024) : compare le challenger au champion `@Production` ;
  bouge l'alias **seulement si meilleur + ε**. Honnête si pas de nouvelle version
  (D-023 in-container) → `skipped_no_challenger`.
- **reimport_bento** (12.3) : si promote a eu lieu, re-importe `@Production` dans le
  store BentoML pour rafraîchir le service. Tolérant (bentoml absent du conteneur OK).

Les tâches tournent dans le conteneur Airflow avec le repo monté sur /opt/rakuten.
Cf. docker-compose.yml à la racine (D-025).
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


def promote_gate_callable() -> dict:
    """Champion/challenger : bouge `@Production` seulement si meilleur (D-024)."""
    from src.mlops.promote_gate import decide_and_promote

    result = decide_and_promote()
    log.info("Promote gate : %s", result)
    return result


def reimport_bento_callable(**context) -> str:
    """Si promote a eu lieu, re-importe `@Production` dans le store BentoML.

    Tolérant : bentoml absent du conteneur (image lean) ou artefact non téléchargeable
    (D-023, hôte↔conteneur) → warning + skip sans casser le DAG. La vraie portabilité
    inter-environnements arrive avec MinIO + MLflow server au Cycle 13.4.
    """
    prev = context["ti"].xcom_pull(task_ids="promote_gate")
    if not (prev and prev.get("promoted")):
        log.info("Pas de promote (%s) → reimport skippé.", (prev or {}).get("decision", "?"))
        return "skipped_no_promote"
    try:
        from src.serving.import_model import main as do_import

        do_import()
        return "reimported"
    except ModuleNotFoundError as e:
        log.warning("bentoml absent (image lean) → reimport host-callable. (%s)", e)
        return "skipped_no_bentoml"
    except Exception as e:  # noqa: BLE001 — D-023 in-container, voir C13.4
        log.warning("reimport échoué (cf. D-023 → C13.4) : %s", e)
        return "skipped_artifact_unreachable"


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

    t_promote = PythonOperator(
        task_id="promote_gate",
        python_callable=promote_gate_callable,
    )

    t_reimport = PythonOperator(
        task_id="reimport_bento",
        python_callable=reimport_bento_callable,
    )

    t_check >> t_train >> t_gate >> t_promote >> t_reimport
