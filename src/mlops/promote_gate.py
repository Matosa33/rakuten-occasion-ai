"""Promote gate champion/challenger pour `rakuten-classifier@Production` (Cycle 12.3, D-024).

Compare le challenger (dernière version enregistrée) au champion (`@Production`)
sur une métrique de référence et bouge l'alias seulement si **challenger ≥ champion + ε**.
Évite la régression silencieuse (R15). Trace la décision dans les tags de la version.

Cas limites :
- aucune version → `no_versions`
- challenger == champion (D-023 : push d'artefact dégradé in-container → pas de
  nouvelle version créée) → `skipped_no_challenger`, sans bouger l'alias.

Lancer :

    python -m src.mlops.promote_gate
"""

from __future__ import annotations

import json
import logging

from mlflow.tracking import MlflowClient

from src.mlops.mlflow_utils import REGISTERED_MODEL, setup_mlflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

METRIC = "test_f1_weighted"
EPSILON = 0.001  # marge mini pour promouvoir (évite oscillations sur bruit)


def _metric(client: MlflowClient, run_id: str, key: str) -> float:
    """Récupère une métrique d'un run, -1 si absente."""
    return float(client.get_run(run_id).data.metrics.get(key, -1.0))


def decide_and_promote(metric: str = METRIC, epsilon: float = EPSILON) -> dict:
    """Compare challenger vs champion ; bouge `@Production` si meilleur.

    Returns:
        dict avec `decision`, `promoted`, `champion_f1`, `challenger_f1`, `version`.
    """
    setup_mlflow()
    client = MlflowClient()

    versions = client.search_model_versions(f"name='{REGISTERED_MODEL}'")
    if not versions:
        log.warning("Aucune version registry → rien à promouvoir.")
        return {"decision": "no_versions", "promoted": False}

    latest = max(versions, key=lambda v: int(v.version))

    try:
        champion = client.get_model_version_by_alias(REGISTERED_MODEL, "Production")
    except Exception:  # noqa: BLE001 — pas d'alias encore
        champion = None

    # D-023 in-container : artefact non poussé → pas de nouvelle version → latest = champion.
    if champion is not None and latest.version == champion.version:
        log.info(
            "Pas de nouveau challenger (latest=v%s=@Production) → skip (cf. D-023).",
            latest.version,
        )
        return {
            "decision": "skipped_no_challenger",
            "promoted": False,
            "version": latest.version,
        }

    challenger_f1 = _metric(client, latest.run_id, metric)
    champion_f1 = _metric(client, champion.run_id, metric) if champion else -1.0

    if challenger_f1 >= champion_f1 + epsilon:
        client.set_registered_model_alias(REGISTERED_MODEL, "Production", latest.version)
        client.set_model_version_tag(
            REGISTERED_MODEL, latest.version, "promote_decision", "promoted"
        )
        client.set_model_version_tag(
            REGISTERED_MODEL, latest.version, "champion_f1_before", f"{champion_f1:.4f}"
        )
        log.info(
            "PROMOTED v%s : %s=%.4f ≥ %.4f + ε (%.4f).",
            latest.version,
            metric,
            challenger_f1,
            champion_f1,
            epsilon,
        )
        decision = "promoted"
        promoted = True
    else:
        client.set_model_version_tag(REGISTERED_MODEL, latest.version, "promote_decision", "kept")
        log.info(
            "KEPT champion v%s : challenger v%s %s=%.4f < %.4f + ε.",
            champion.version if champion else "?",
            latest.version,
            metric,
            challenger_f1,
            champion_f1,
        )
        decision = "kept"
        promoted = False

    return {
        "decision": decision,
        "promoted": promoted,
        "version": latest.version,
        "champion_f1": champion_f1,
        "challenger_f1": challenger_f1,
        "metric": metric,
        "epsilon": epsilon,
    }


def main() -> None:
    result = decide_and_promote()
    # C14.3 (D-031) : push la décision promote_gate vers Pushgateway pour
    # visibilité Grafana. Import lazy + try/except → fonctionnel sans la stack obs.
    try:
        from src.monitoring.push_metrics import push_promote_metrics

        push_promote_metrics(result)
    except ImportError:
        log.warning("prometheus_client non installé → push Pushgateway skip (R15 graceful).")
    # CLI output JSON consommable par script aval (pipe / jq), pas un log → R6 ok (D-029).
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
