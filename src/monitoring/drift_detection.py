"""Détection de drift Evidently sur les features texte + catégorie (C12.3, D-024).

Reference = échantillon `train.parquet` ; current = échantillon `test.parquet`
(*proxy démo* du flux de production réel ; en prod réelle, current viendrait du
log des entrées récentes de l'API - pas encore loggées). Features comparées :
longueur du titre, longueur de la description, distribution de `_source_category`.

Si la **part de features driftées (DataDriftPreset.share)** dépasse le seuil
`DRIFT_SHARE_THRESHOLD`, le drift est déclaré → le DAG `rakuten_drift_check` peut
déclencher `rakuten_retrain`. Rapport HTML écrit dans `monitoring/evidently/reports/`.

Lancer :

    python -m src.monitoring.drift_detection
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import polars as pl
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

from src.config import DATA_PROCESSED_PRODUCTS, REPO_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

REPORT_DIR = REPO_ROOT / "monitoring" / "evidently" / "reports"
REFERENCE_SAMPLE = 50_000  # échantillon train (référence)
CURRENT_SAMPLE = 10_000  # échantillon test (proxy démo du flux récent)
DRIFT_SHARE_THRESHOLD = 0.5  # ≥50% de features driftées → alerte

_NUM_COLS = ["title_len", "description_len"]
_CAT_COLS = ["_source_category"]


def _prepare(parquet_path: Path, n: int) -> Dataset:
    """Lit un split, échantillonne et calcule les features de drift."""
    df = (
        pl.read_parquet(parquet_path, columns=["title", "description", "_source_category"])
        .sample(n=n, seed=42)
        .with_columns(
            [
                pl.col("title").fill_null("").str.len_chars().alias("title_len"),
                pl.col("description").fill_null("").str.len_chars().alias("description_len"),
            ]
        )
        .select([*_NUM_COLS, *_CAT_COLS])
        .to_pandas()
    )
    schema = DataDefinition(numerical_columns=_NUM_COLS, categorical_columns=_CAT_COLS)
    return Dataset.from_pandas(df, data_definition=schema)


def detect_drift() -> dict:
    """Compare la référence à l'échantillon courant ; renvoie la décision et le rapport."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Préparation reference (train) + current (test, proxy démo)…")
    n_ref = REFERENCE_SAMPLE
    n_cur = CURRENT_SAMPLE
    ref = _prepare(DATA_PROCESSED_PRODUCTS / "train.parquet", n_ref)
    cur = _prepare(DATA_PROCESSED_PRODUCTS / "test.parquet", n_cur)

    log.info("Calcul du drift (Evidently DataDriftPreset)…")
    snap = Report([DataDriftPreset()]).run(reference_data=ref, current_data=cur)

    # premier metric = DriftedColumnsCount {count, share}
    metrics = snap.dict().get("metrics", [])
    drift_count_metric = next(
        (m for m in metrics if m.get("metric_name", "").startswith("DriftedColumnsCount")),
        None,
    )
    share = float(drift_count_metric["value"]["share"]) if drift_count_metric else 0.0
    count = int(drift_count_metric["value"]["count"]) if drift_count_metric else 0
    drift_detected = share >= DRIFT_SHARE_THRESHOLD

    html_path = REPORT_DIR / "drift_latest.html"
    snap.save_html(str(html_path))

    result = {
        "drift_detected": drift_detected,
        "drift_share": share,
        "drifted_columns_count": count,
        "threshold": DRIFT_SHARE_THRESHOLD,
        "report_html": str(html_path),
        "n_reference": n_ref,
        "n_current": n_cur,
    }
    log.info(
        "Drift : share=%.2f (seuil %.2f) → detected=%s (rapport %s)",
        share,
        DRIFT_SHARE_THRESHOLD,
        drift_detected,
        html_path,
    )
    return result


def main() -> None:
    result = detect_drift()
    # C14.3 (D-031) : push les drift scores vers Pushgateway pour visibilité
    # Grafana. Import lazy → pas de coupling fort obs sur le module de calcul,
    # et le run reste fonctionnel si prometheus_client n'est pas dispo.
    try:
        from src.monitoring.push_metrics import push_drift_metrics

        push_drift_metrics(result)
    except ImportError:
        log.warning("prometheus_client non installé → push Pushgateway skip (R15 graceful).")
    # CLI output JSON consommable par script aval (pipe / jq), pas un log → R6 ok (D-029).
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
