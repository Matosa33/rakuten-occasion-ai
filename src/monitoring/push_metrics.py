"""Helpers push métriques batch vers le Pushgateway Prometheus (Cycle 14.3, D-031).

Pourquoi un module dédié
------------------------
Les jobs `drift_detection` et `promote_gate` s'exécutent par à-coups (DAG Airflow).
Le pattern Prometheus standard scrape-pull ne marche pas sur un process court ;
on **push** donc les métriques après chaque run vers le Pushgateway, qui les
expose à Prometheus jusqu'au prochain push (qui les remplace via le grouping key
`job=rakuten_batch`).

Convention de naming
--------------------
Préfixe `rakuten_` pour namespacer nos métriques métiers vs `http_*` (golden
signals C14.2) et éviter tout conflit futur. Voir D-031 pour la liste complète.

Dégradation propre
------------------
Si le Pushgateway n'est pas joignable (smoke standalone, env. soutenance sans
docker compose up), on log et on retourne (R15) — JAMAIS faire échouer la
batch métier à cause d'un push obs raté.
"""

from __future__ import annotations

import os
import time

from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

from src.observability.logging import get_logger

_log = get_logger(__name__)

# URL par défaut = nom de service Docker (résolu via DNS interne du compose).
# Override via env var quand on tourne en local hôte ou en CI.
PUSHGATEWAY_URL = os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091")
BATCH_JOB_NAME = "rakuten_batch"

# Liste fermée des décisions promote_gate possibles → pour pousser une Gauge
# par valeur à chaque run (1 pour la décision active, 0 pour les autres). C'est
# plus simple à grapher qu'un counter incrémentiel sur un job batch (cf. D-031).
_PROMOTE_DECISIONS = ("promoted", "kept", "skipped_no_challenger", "no_versions")


def push_drift_metrics(result: dict) -> bool:
    """Push les métriques de drift Evidently vers le Pushgateway.

    Args:
        result: dict renvoyé par `detect_drift()` (drift_share, drifted_columns_count,
                drift_detected, threshold, n_reference, n_current).

    Returns:
        True si push OK, False si Pushgateway injoignable (degraded mode).
    """
    registry = CollectorRegistry()

    Gauge(
        "rakuten_drift_share",
        "Evidently DataDriftPreset : part de colonnes driftées (0-1).",
        registry=registry,
    ).set(float(result.get("drift_share", 0.0)))

    Gauge(
        "rakuten_drift_columns_count",
        "Evidently DataDriftPreset : nombre absolu de colonnes driftées.",
        registry=registry,
    ).set(int(result.get("drifted_columns_count", 0)))

    Gauge(
        "rakuten_drift_detected",
        "1 si drift au-dessus du seuil, sinon 0 (alerte binaire).",
        registry=registry,
    ).set(1 if result.get("drift_detected") else 0)

    Gauge(
        "rakuten_drift_threshold",
        "Seuil de DriftedColumnsCount.share au-dessus duquel on alerte.",
        registry=registry,
    ).set(float(result.get("threshold", 0.0)))

    Gauge(
        "rakuten_drift_last_run_timestamp",
        "Timestamp Unix du dernier drift_check (jobs batch idempotent).",
        registry=registry,
    ).set(time.time())

    Gauge(
        "rakuten_drift_reference_sample_size",
        "Taille de l'échantillon de référence (train) utilisé pour le drift.",
        registry=registry,
    ).set(int(result.get("n_reference", 0)))

    Gauge(
        "rakuten_drift_current_sample_size",
        "Taille de l'échantillon courant (test/proxy live) utilisé pour le drift.",
        registry=registry,
    ).set(int(result.get("n_current", 0)))

    return _push("drift_check", registry)


def push_promote_metrics(result: dict) -> bool:
    """Push les métriques de promote_gate vers le Pushgateway.

    Args:
        result: dict renvoyé par `decide_and_promote()` (decision, promoted, version,
                champion_f1, challenger_f1, epsilon).

    Returns:
        True si push OK, False si Pushgateway injoignable.
    """
    registry = CollectorRegistry()

    Gauge(
        "rakuten_promote_champion_f1",
        "F1 weighted du champion actuel (@Production) au moment de la décision.",
        registry=registry,
    ).set(float(result.get("champion_f1", -1.0)))

    Gauge(
        "rakuten_promote_challenger_f1",
        "F1 weighted du challenger (dernière version registry) évalué.",
        registry=registry,
    ).set(float(result.get("challenger_f1", -1.0)))

    Gauge(
        "rakuten_promote_epsilon",
        "Marge mini pour promouvoir (challenger ≥ champion + ε).",
        registry=registry,
    ).set(float(result.get("epsilon", 0.0)))

    # Gauge par décision possible : 1 pour la décision active, 0 pour les autres.
    # Permet à Grafana de filtrer/colorer un panel "decision actuelle" sans counter.
    decision_g = Gauge(
        "rakuten_promote_decision",
        "Décision promote_gate du dernier run (1 = active, 0 = autres).",
        labelnames=["decision"],
        registry=registry,
    )
    active = result.get("decision", "no_versions")
    for d in _PROMOTE_DECISIONS:
        decision_g.labels(decision=d).set(1 if d == active else 0)

    Gauge(
        "rakuten_promote_last_run_timestamp",
        "Timestamp Unix du dernier promote_gate.",
        registry=registry,
    ).set(time.time())

    return _push("promote_gate", registry)


def _push(stage: str, registry: CollectorRegistry) -> bool:
    """Push effectif vers le Pushgateway. Dégradation propre si injoignable."""
    try:
        # `grouping_key` permet de différencier les stages tout en partageant le
        # job_name (la requête PromQL filtre par `stage="drift_check"` etc.).
        push_to_gateway(
            PUSHGATEWAY_URL,
            job=BATCH_JOB_NAME,
            registry=registry,
            grouping_key={"stage": stage},
        )
        _log.info("pushgateway_push_ok", stage=stage, url=PUSHGATEWAY_URL)
        return True
    except Exception as e:  # noqa: BLE001 — robust to network / DNS issues
        _log.warning(
            "pushgateway_push_failed",
            stage=stage,
            url=PUSHGATEWAY_URL,
            error=str(e),
        )
        return False
