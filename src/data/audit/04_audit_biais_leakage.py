"""Étape 4/4 — Audit biais & leakage sur les 3 catégories COMPLÈTES (polars lazy).

Lit  : data/raw/full/{reviews,meta}/<Cat>.parquet
Écrit:
  - reports/audit_biais_leakage_metrics.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from src.data.audit import scan_concat  # source unique de vérité (D-008)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEWS_DIR = REPO_ROOT / "data" / "raw" / "full" / "reviews"
META_DIR = REPO_ROOT / "data" / "raw" / "full" / "meta"
REPORTS_DIR = REPO_ROOT / "reports"


def detect_category_imbalance(reviews_lf: pl.LazyFrame) -> dict[str, Any]:
    counts = reviews_lf.group_by("_source_category").agg(pl.len().alias("n")).collect(engine="streaming")
    n_min = int(counts["n"].min() or 1)
    n_max = int(counts["n"].max() or 1)
    ratio = n_max / max(n_min, 1)
    return {
        "label": "B1 — déséquilibre catégoriel (reviews FULL)",
        "severity": "high" if ratio > 5 else ("medium" if ratio > 2 else "low"),
        "max_min_ratio": round(ratio, 2),
        "counts": {row["_source_category"]: int(row["n"]) for row in counts.to_dicts()},
    }


def detect_verified_purchase_bias(reviews_lf: pl.LazyFrame) -> dict[str, Any]:
    if "verified_purchase" not in reviews_lf.collect_schema().names():
        return {"label": "B2 — verified_purchase", "severity": "n/a"}
    # Type mixte : bool natif dans certains parquets (polars sink_parquet),
    # string "True"/"False" dans d'autres (fallback pandas chunked qui stringifie tout).
    # Le concat diagonal_relaxed promeut en string → on parse comme string truthy.
    is_true = (
        pl.col("verified_purchase")
        .cast(pl.Utf8, strict=False)
        .str.to_lowercase()
        .is_in(["true", "1"])
    )
    stats = (
        reviews_lf.select(
            n_total=pl.len(),
            n_true=is_true.sum(),
        )
        .collect(engine="streaming")
        .to_dicts()[0]
    )
    n_total = int(stats["n_total"])
    n_true = int(stats["n_true"] or 0)
    pct = round(100 * n_true / n_total, 1) if n_total else 0
    return {
        "label": "B2 — biais de validation (verified_purchase, reviews FULL)",
        "severity": "medium" if pct < 70 else "low",
        "pct_verified_true": pct,
        "n_true": n_true,
        "n_false": n_total - n_true,
    }


def detect_price_bias(meta_lf: pl.LazyFrame) -> dict[str, Any]:
    if "price" not in meta_lf.collect_schema().names():
        return {"label": "B3 — prix", "severity": "n/a"}
    valid = meta_lf.with_columns(
        pl.col("price")
        .cast(pl.Utf8, strict=False)
        .str.replace_all(r"[^\d.]", "")
        .cast(pl.Float64, strict=False)
        .alias("_price_num")
    ).filter(pl.col("_price_num").is_not_null() & (pl.col("_price_num") > 0))
    n_valid = valid.select(pl.len()).collect(engine="streaming").item()
    if n_valid == 0:
        return {
            "label": "B3 — prix",
            "severity": "high",
            "reason": "aucun prix exploitable",
            "n_valid_prices": 0,
        }
    n_below_50 = valid.filter(pl.col("_price_num") < 50).select(pl.len()).collect(engine="streaming").item()
    pct = round(100 * n_below_50 / n_valid, 1)
    return {
        "label": "B3 — biais de prix (concentration low-end, meta FULL)",
        "severity": "medium" if pct > 75 else "low",
        "pct_below_50_dollars": pct,
        "n_valid_prices": int(n_valid),
    }


def detect_temporal_bias(reviews_lf: pl.LazyFrame) -> dict[str, Any]:
    if "timestamp" not in reviews_lf.collect_schema().names():
        return {"label": "B4 — temporel", "severity": "n/a"}
    # Format mixte (cf. 03_audit_distributions.py temporal_distribution).
    ts_str = pl.col("timestamp").cast(pl.Utf8, strict=False)
    year_expr = (
        pl.coalesce(
            ts_str.str.to_datetime(strict=False).dt.year(),
            ts_str.cast(pl.Int64, strict=False)
            .cast(pl.Datetime(time_unit="ms"), strict=False)
            .dt.year(),
        ).alias("year")
    )
    by_year = (
        reviews_lf.with_columns(year_expr)
        .group_by("year")
        .agg(pl.len().alias("n"))
        .sort("year")
        .collect(engine="streaming")
    )
    rows = [r for r in by_year.to_dicts() if r["year"] is not None]
    if not rows:
        return {"label": "B4 — temporel", "severity": "n/a"}
    total = sum(r["n"] for r in rows)
    last_3y_threshold = max(r["year"] for r in rows) - 2
    last_3 = sum(r["n"] for r in rows if r["year"] >= last_3y_threshold)
    pct = round(100 * last_3 / total, 1) if total else 0
    return {
        "label": "B4 — biais temporel (concentration récente, reviews FULL)",
        "severity": "medium" if pct > 70 else "low",
        "pct_last_3_years": pct,
        "min_year": min(r["year"] for r in rows),
        "max_year": max(r["year"] for r in rows),
    }


def detect_parent_asin_leakage(reviews_lf: pl.LazyFrame) -> dict[str, Any]:
    stats = (
        reviews_lf.select(
            n_total=pl.len(),
            n_unique_parent=pl.col("parent_asin").n_unique(),
        )
        .collect(engine="streaming")
        .to_dicts()[0]
    )
    n_total = int(stats["n_total"])
    n_unique = int(stats["n_unique_parent"])
    factor = round(n_total / max(n_unique, 1), 2)
    return {
        "label": "L1 — variantes (reviews/parent_asin)",
        "severity": "high" if n_unique < 0.5 * n_total else "low",
        "n_total": n_total,
        "n_unique_parent_asin": n_unique,
        "duplication_factor": factor,
    }


def detect_user_leakage(reviews_lf: pl.LazyFrame) -> dict[str, Any]:
    if "user_id" not in reviews_lf.collect_schema().names():
        return {"label": "L2 — user_id", "severity": "n/a"}
    n_total = reviews_lf.select(pl.len()).collect(engine="streaming").item()
    n_unique_users = reviews_lf.select(pl.col("user_id").n_unique()).collect(engine="streaming").item()
    # Combien d'users ont > 1 review : on group_by puis filter
    multi = (
        reviews_lf.group_by("user_id")
        .agg(pl.len().alias("n"))
        .filter(pl.col("n") > 1)
        .select(pl.len())
        .collect(engine="streaming")
        .item()
    )
    return {
        "label": "L2 — leakage de groupe (user_id répétés, reviews FULL)",
        "severity": "medium" if n_unique_users < 0.7 * n_total else "low",
        "n_total": int(n_total),
        "n_unique_users": int(n_unique_users),
        "users_with_more_than_1_review": int(multi),
    }


def detect_title_duplicates(reviews_lf: pl.LazyFrame) -> dict[str, Any]:
    if "title" not in reviews_lf.collect_schema().names():
        return {"label": "L3 — titres", "severity": "n/a"}
    stats = (
        reviews_lf.select(
            n_total=pl.len(),
            n_unique_title=pl.col("title").n_unique(),
        )
        .collect(engine="streaming")
        .to_dicts()[0]
    )
    n_dup = int(stats["n_total"]) - int(stats["n_unique_title"])
    return {
        "label": "L3 — leakage par titres identiques (reviews FULL)",
        "severity": "medium" if n_dup > 50 else "low",
        "n_total": int(stats["n_total"]),
        "n_unique_titles": int(stats["n_unique_title"]),
        "n_duplicated_titles": n_dup,
    }


def _run(label: str, fn, *args):
    log.info("→ %s …", label)
    res = fn(*args)
    log.info("  ✓ %s", label)
    return res


def main() -> None:
    log.info("=== Étape 4/4 : audit biais & leakage (FULL via polars) ===")
    reviews_lf = scan_concat(REVIEWS_DIR)
    meta_lf = scan_concat(META_DIR)

    findings = {
        "biais": [
            _run("B1 cat imbalance", detect_category_imbalance, reviews_lf),
            _run("B2 verified_purchase", detect_verified_purchase_bias, reviews_lf),
            _run("B3 price", detect_price_bias, meta_lf),
            _run("B4 temporal", detect_temporal_bias, reviews_lf),
        ],
        "leakages": [
            _run("L1 parent_asin", detect_parent_asin_leakage, reviews_lf),
            _run("L2 user_id", detect_user_leakage, reviews_lf),
            _run("L3 titles", detect_title_duplicates, reviews_lf),
        ],
    }

    out_json = REPORTS_DIR / "audit_biais_leakage_metrics.json"
    out_json.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")

    for f in findings["biais"] + findings["leakages"]:
        log.info("[%s] %s", f.get("severity", "?"), f.get("label"))

    log.info("Findings → %s", out_json)
    log.info("Étape 4 OK.")


if __name__ == "__main__":
    main()
