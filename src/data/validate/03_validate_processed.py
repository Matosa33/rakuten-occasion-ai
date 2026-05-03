"""Sous-todo 1.4 — Valide les sorties du pipeline 1.2 contre les schemas Pandera.

Pour chaque split (train/val/test), valide :
- products/{split}.parquet contre ProductSchema
- reviews_index/{split}.parquet contre ReviewIndexSchema (via sample 100k)

Stratégie hybride :
- ProductSchema : validation **complète** sur products/ (~26 M lignes total,
  ~5-10 min en streaming Pandera-polars)
- ReviewIndexSchema : validation sur **sample 100k par split** (348 M lignes
  totales = trop coûteux pour validation en CI ou batch interactif)

Sortie : `reports/02_cleaning/pandera_validation.md` + `pandera_validation.json`

Lance ce script depuis la racine du repo :

    python -m src.data.validate.03_validate_processed
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import pandera.errors
import polars as pl

from src.config import (
    DATA_PROCESSED_PRODUCTS,
    DATA_PROCESSED_REVIEWS_INDEX,
    REPORTS_CLEANING,
    SEED,
)
from src.data.validate.schemas import ProductSchema, ReviewIndexSchema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUT_JSON = REPORTS_CLEANING / "pandera_validation.json"


def _validate_products_split(split_name: str) -> dict[str, Any]:
    """Validate full split products contre ProductSchema."""
    path = DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet"
    if not path.exists():
        return {"split": split_name, "status": "missing", "path": str(path)}

    log.info("Lecture %s…", path.name)
    t0 = time.time()
    df = pl.read_parquet(path)
    n = df.height
    log.info("  %s : %s lignes, validation Pandera (full)…", split_name, f"{n:_}")

    try:
        ProductSchema.validate(df, lazy=True)
        duration = time.time() - t0
        log.info(
            "  ✓ %s : ProductSchema OK (%s lignes, %.1f s)",
            split_name,
            f"{n:_}",
            duration,
        )
        return {
            "split": split_name,
            "schema": "ProductSchema",
            "status": "ok",
            "n_rows": n,
            "duration_seconds": round(duration, 1),
            "errors": [],
        }
    except pandera.errors.SchemaErrors as e:
        # `lazy=True` collecte toutes les erreurs avant de raise
        duration = time.time() - t0
        errors = e.failure_cases.head(20).to_dicts()
        log.error(
            "  ✗ %s : ProductSchema KO (%d failure cases, %.1f s)",
            split_name,
            len(e.failure_cases),
            duration,
        )
        return {
            "split": split_name,
            "schema": "ProductSchema",
            "status": "ko",
            "n_rows": n,
            "duration_seconds": round(duration, 1),
            "n_errors": len(e.failure_cases),
            "errors_sample": errors,
        }
    except pandera.errors.SchemaError as e:
        duration = time.time() - t0
        log.error("  ✗ %s : ProductSchema KO (%s, %.1f s)", split_name, e, duration)
        return {
            "split": split_name,
            "schema": "ProductSchema",
            "status": "ko",
            "n_rows": n,
            "duration_seconds": round(duration, 1),
            "n_errors": 1,
            "error_msg": str(e),
        }


def _validate_reviews_index_sample(split_name: str, n_sample: int = 100_000) -> dict[str, Any]:
    """Validate sample du reviews_index contre ReviewIndexSchema."""
    path = DATA_PROCESSED_REVIEWS_INDEX / f"{split_name}.parquet"
    if not path.exists():
        return {"split": split_name, "status": "missing", "path": str(path)}

    log.info("Sample %d lignes de %s…", n_sample, path.name)
    t0 = time.time()
    # Lecture lazy + sample uniforme (filter modulo)
    n_total = pl.scan_parquet(path).select(pl.len()).collect(engine="streaming").item()
    step = max(1, n_total // n_sample)
    df_sample = (
        pl.scan_parquet(path)
        .with_row_index()
        .filter(pl.col("index") % step == 0)
        .drop("index")
        .collect(engine="streaming")
    )
    if df_sample.height > n_sample:
        df_sample = df_sample.sample(n=n_sample, seed=SEED)

    log.info(
        "  %s : sample=%s sur %s lignes totales, validation Pandera…",
        split_name,
        f"{df_sample.height:_}",
        f"{n_total:_}",
    )

    try:
        ReviewIndexSchema.validate(df_sample, lazy=True)
        duration = time.time() - t0
        log.info(
            "  ✓ %s : ReviewIndexSchema OK (sample %s, %.1f s)",
            split_name,
            f"{df_sample.height:_}",
            duration,
        )
        return {
            "split": split_name,
            "schema": "ReviewIndexSchema",
            "status": "ok",
            "n_total": n_total,
            "n_sample": df_sample.height,
            "duration_seconds": round(duration, 1),
            "errors": [],
        }
    except pandera.errors.SchemaErrors as e:
        duration = time.time() - t0
        errors = e.failure_cases.head(20).to_dicts()
        log.error(
            "  ✗ %s : ReviewIndexSchema KO (%d failure cases sur sample)",
            split_name,
            len(e.failure_cases),
        )
        return {
            "split": split_name,
            "schema": "ReviewIndexSchema",
            "status": "ko",
            "n_total": n_total,
            "n_sample": df_sample.height,
            "duration_seconds": round(duration, 1),
            "n_errors": len(e.failure_cases),
            "errors_sample": errors,
        }


def main() -> None:
    log.info("=== Sous-todo 1.4 — Validation Pandera des sorties pipeline 1.2 ===")

    REPORTS_CLEANING.mkdir(parents=True, exist_ok=True)

    results = {"products": {}, "reviews_index": {}}

    for split_name in ("train", "val", "test"):
        results["products"][split_name] = _validate_products_split(split_name)

    for split_name in ("train", "val", "test"):
        results["reviews_index"][split_name] = _validate_reviews_index_sample(split_name)

    OUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Métriques → %s", OUT_JSON)

    # Synthèse
    log.info("\n=== Synthèse validation Pandera ===")
    n_ok = 0
    n_ko = 0
    for category in ("products", "reviews_index"):
        for split, r in results[category].items():
            status = r.get("status", "?")
            log.info("  [%s] %s/%s — %s", status, category, split, r.get("schema", "?"))
            if status == "ok":
                n_ok += 1
            elif status == "ko":
                n_ko += 1

    log.info("Total : %d OK / %d KO sur 6 validations", n_ok, n_ko)
    if n_ko > 0:
        log.warning("⚠️ %d validation(s) KO — voir %s pour détails", n_ko, OUT_JSON)
    else:
        log.info("Sous-todo 1.4 OK — tous les schemas validés.")


if __name__ == "__main__":
    main()
