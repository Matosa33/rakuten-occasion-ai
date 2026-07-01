"""DAG `rakuten_retrain` - boucle de ré-entraînement fermée (C12.1+12.3, D-022/D-024).

L'orchestrateur orchestre, il ne calcule PAS le GPU. Graphe :

    check_new_data → [train_tfidf_svm ∥ train_svm_embed ∥ train_mlp_embed]
                   → evaluate_gate → promote_gate → reimport_bento

- **check_new_data** : encode GPU = tâche amont isolée ; no-op si embeddings en cache.
- **train_*** : les 3 têtes CPU s'entraînent EN PARALLÈLE (LocalExecutor) - le temps du
  retrain = le max des trois, pas la somme. Chacune logge son run MLflow (métriques,
  commit git). Seul le challenger officiel (tfidf-svm) est versionné au Model Registry :
  des enregistrements parallèles rendraient le « latest » non déterministe pour la gate.
- **evaluate_gate** : garde-fou qualité (F1 ≥ seuil) - échoue le DAG sous le seuil.
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

from airflow.datasets import Dataset
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

REPO_ROOT = Path("/opt/rakuten")
EMBEDDINGS_DIR = REPO_ROOT / "data" / "embeddings" / "text"
BENCH_DIR = REPO_ROOT / "reports" / "04_classifiers_bench"
MODELS_DIR = REPO_ROOT / "data" / "models"

# Lignage déclaré (onglet Datasets d'Airflow) : chaque tâche dit ce qu'elle PRODUIT.
# Pure métadonnée (aucun effet sur l'exécution) - trace « qui a mis à jour quoi, quand ».
DS_MODELS = Dataset("file://opt/rakuten/data/models")
DS_BENCH = Dataset("file://opt/rakuten/reports/04_classifiers_bench")
DS_PRODUCTION = Dataset("mlflow://rakuten-category-classifier@Production")

# Rapport écrit par 01_tfidf_linsvc (OUT_METRICS = "<MODEL_NAME>.json").
PRODUCTION_REPORT = BENCH_DIR / "tfidf-svm_v1.json"
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
    """Lit le rapport du challenger tfidf-svm et applique le garde-fou qualité (F1_GATE)."""
    if not PRODUCTION_REPORT.exists():
        raise FileNotFoundError(f"Rapport introuvable : {PRODUCTION_REPORT}")
    data = json.loads(PRODUCTION_REPORT.read_text(encoding="utf-8"))
    f1 = float(data.get("results", {}).get("test", {}).get("f1_weighted", 0.0))
    log.info("Challenger tfidf-svm : test_f1_weighted=%.4f (seuil %.2f)", f1, F1_GATE)
    if f1 < F1_GATE:
        raise ValueError(f"F1 {f1:.4f} < seuil {F1_GATE} → modèle dégradé, DAG en échec.")
    log.info("Garde-fou OK : modèle ré-entraîné conforme.")
    return {"test_f1_weighted": f1, "gate_passed": True}


def promote_gate_callable() -> dict:
    """Champion/challenger : bouge `@Production` seulement si meilleur (D-024)."""
    from src.mlops.promote_gate import decide_and_promote

    result = decide_and_promote()
    log.info("Promote gate : %s", result)
    # Push des métriques batch vers le Pushgateway (dashboard Grafana "promote").
    # Best-effort : un échec d'observabilité ne casse jamais la décision (R15).
    try:
        from src.monitoring.push_metrics import push_promote_metrics

        push_promote_metrics(result)
    except Exception as e:  # noqa: BLE001 - observabilité best-effort
        log.warning("push_promote_metrics KO (non bloquant) : %s", e)
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
    except Exception as e:  # noqa: BLE001 - D-023 in-container, voir C13.4
        log.warning("reimport échoué (cf. D-023 → C13.4) : %s", e)
        return "skipped_artifact_unreachable"


with DAG(
    dag_id="rakuten_retrain",
    description="Boucle de ré-entraînement CPU (encode-delta → train → eval → register) - D-022",
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
    # Les 3 têtes sont STRUCTURELLEMENT parallèles ; la concurrence effective est gouvernée
    # par le pool Airflow `cpu_training` : 1 slot en démo locale (le partage de fichiers
    # Windows→Docker ne supporte pas plusieurs lectures multi-Go concurrentes), N slots sur
    # un vrai nœud Linux de prod → parallélisme réel sans changer le DAG.
    t_train_tfidf = BashOperator(
        task_id="train_tfidf_svm",
        cwd="/opt/rakuten",
        pool="cpu_training",
        outlets=[DS_MODELS, DS_BENCH],
        bash_command=(
            "set -e; rm -f data/models/tfidf-svm_v1.joblib; "
            "python -m src.classifiers.01_tfidf_linsvc"
        ),
    )
    t_train_svm = BashOperator(
        task_id="train_svm_embed",
        cwd="/opt/rakuten",
        pool="cpu_training",
        outlets=[DS_MODELS, DS_BENCH],
        bash_command=(
            "set -e; rm -f data/models/svm-embed_v1.joblib; python -m src.classifiers.03_svm"
        ),
    )
    t_train_mlp = BashOperator(
        task_id="train_mlp_embed",
        cwd="/opt/rakuten",
        pool="cpu_training",
        outlets=[DS_MODELS, DS_BENCH],
        bash_command=(
            "set -e; rm -f data/models/mlp-embed_v1.joblib; python -m src.classifiers.05_mlp"
        ),
    )

    t_gate = PythonOperator(
        task_id="evaluate_gate",
        python_callable=evaluate_gate,
    )

    t_promote = PythonOperator(
        task_id="promote_gate",
        python_callable=promote_gate_callable,
        outlets=[DS_PRODUCTION],
    )

    t_reimport = PythonOperator(
        task_id="reimport_bento",
        python_callable=reimport_bento_callable,
    )

    # tfidf ∥ (svm → mlp) : svm et mlp lisent le MÊME .npy de 13 Go - deux lectures
    # concurrentes à travers le bind-mount Windows→Docker échouent (lecture partielle).
    # On chaîne les deux lecteurs d'embeddings ; le temps total reste ≈ max des branches.
    t_check >> [t_train_tfidf, t_train_svm]
    t_train_svm >> t_train_mlp
    [t_train_tfidf, t_train_mlp] >> t_gate
    t_gate >> t_promote >> t_reimport
