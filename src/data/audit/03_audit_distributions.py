"""Étape 3/4 — Audit distributions sur le périmètre actif D-008 (polars lazy + streaming).

Lit  : data/raw/full/{reviews,meta}/<Cat>.parquet
Écrit:
  - reports/01_audit/figures/03a_distribution_reviews_par_cat.png
  - reports/01_audit/figures/03b_distribution_meta_par_cat.png
  - reports/01_audit/figures/03c_distribution_prix_meta.png
  - reports/01_audit/figures/03d_distribution_ratings_reviews.png
  - reports/01_audit/figures/03e_distribution_temporelle_reviews.png
  - reports/01_audit/audit_distributions_metrics.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import seaborn as sns

from src.config import (
    DATA_RAW_FULL_META as META_DIR,
)
from src.config import (
    DATA_RAW_FULL_REVIEWS as REVIEWS_DIR,
)
from src.config import (
    REPORTS_AUDIT as REPORTS_DIR,
)
from src.data.audit import scan_concat  # source unique de vérité (D-008)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

FIG_DIR = REPORTS_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid", context="notebook")


def per_category_count(lf: pl.LazyFrame) -> dict[str, int]:
    df = lf.group_by("_source_category").agg(pl.len().alias("n")).collect(engine="streaming")
    return {row["_source_category"]: int(row["n"]) for row in df.to_dicts()}


def plot_per_cat(counts: dict[str, int], title: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(list(counts.keys()), list(counts.values()), color="#2563eb")
    ax.set_ylabel("Nombre de lignes")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def price_stats_from_meta(meta_lf: pl.LazyFrame) -> dict[str, Any]:
    if "price" not in meta_lf.collect_schema().names():
        return {}
    # Le champ price peut être string ("$12.99", "None"), nombre, ou null.
    cleaned = meta_lf.with_columns(
        pl.col("price")
        .cast(pl.Utf8, strict=False)
        .str.replace_all(r"[^\d.]", "")
        .cast(pl.Float64, strict=False)
        .alias("_price_num")
    )
    valid = cleaned.filter(pl.col("_price_num").is_not_null() & (pl.col("_price_num") > 0))
    n_with = valid.select(pl.len()).collect(engine="streaming").item()
    n_total = meta_lf.select(pl.len()).collect(engine="streaming").item()
    if n_with == 0:
        return {"n_with_price": 0, "n_without_price": int(n_total)}

    stats = (
        valid.select(
            mean=pl.col("_price_num").mean(),
            median=pl.col("_price_num").median(),
            p95=pl.col("_price_num").quantile(0.95),
            p99=pl.col("_price_num").quantile(0.99),
            max=pl.col("_price_num").max(),
            n_above_500=(pl.col("_price_num") > 500).sum(),
        )
        .collect(engine="streaming")
        .to_dicts()[0]
    )

    # Plot
    sample = (
        valid.select(pl.col("_price_num"))
        .collect(engine="streaming")
        .sample(n=min(200_000, n_with), seed=42)["_price_num"]
        .to_numpy()
    )
    p99v = float(np.quantile(sample, 0.99)) if sample.size else 0
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].hist(np.clip(sample, 0, p99v), bins=80, color="#16a34a")
    axes[0].set_xlabel("Prix ($, clip p99)")
    axes[0].set_ylabel("Effectif")
    axes[0].set_title("Distribution prix (linéaire) — meta FULL")
    axes[1].hist(np.log1p(sample), bins=80, color="#16a34a")
    axes[1].set_xlabel("log(1 + prix)")
    axes[1].set_title("Distribution prix (log) — meta FULL")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "03c_distribution_prix_meta.png", dpi=120)
    plt.close(fig)

    return {
        "n_with_price": int(n_with),
        "n_without_price": int(n_total - n_with),
        "mean": round(float(stats["mean"]), 2),
        "median": round(float(stats["median"]), 2),
        "p95": round(float(stats["p95"]), 2),
        "p99": round(float(stats["p99"]), 2),
        "max": round(float(stats["max"]), 2),
        "n_above_500": int(stats["n_above_500"]),
    }


def ratings_distribution(reviews_lf: pl.LazyFrame) -> dict[str, int]:
    if "rating" not in reviews_lf.collect_schema().names():
        return {}
    df = (
        reviews_lf.group_by(
            pl.col("rating").cast(pl.Float64, strict=False).round(0).cast(pl.Int64).alias("r")
        )
        .agg(pl.len().alias("n"))
        .sort("r")
        .collect(engine="streaming")
    )
    counts = {str(row["r"]): int(row["n"]) for row in df.to_dicts() if row["r"] is not None}

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(list(counts.keys()), list(counts.values()), color="#f59e0b")
    ax.set_xlabel("Note (1-5)")
    ax.set_ylabel("Effectif")
    ax.set_title("Distribution des ratings — reviews FULL")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "03d_distribution_ratings_reviews.png", dpi=120)
    plt.close(fig)
    return counts


def temporal_distribution(reviews_lf: pl.LazyFrame) -> dict[str, Any]:
    if "timestamp" not in reviews_lf.collect_schema().names():
        return {}
    # Timestamp en format mixte selon que le parquet a été écrit par polars natif
    # (Int64 ms) ou par fallback pandas chunked (string ISO type "2019-08-01 03:21:10.757000").
    # Le concat diagonal_relaxed promeut tout en string → on tente les deux chemins de parse.
    ts_str = pl.col("timestamp").cast(pl.Utf8, strict=False)
    year_expr = pl.coalesce(
        ts_str.str.to_datetime(strict=False).dt.year(),
        ts_str.cast(pl.Int64, strict=False)
        .cast(pl.Datetime(time_unit="ms"), strict=False)
        .dt.year(),
    ).alias("year")
    by_year = (
        reviews_lf.with_columns(year_expr)
        .group_by("year")
        .agg(pl.len().alias("n"))
        .sort("year")
        .collect(engine="streaming")
    )

    rows = [r for r in by_year.to_dicts() if r["year"] is not None]
    if not rows:
        return {}
    counts = {str(r["year"]): int(r["n"]) for r in rows}

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.bar(list(counts.keys()), list(counts.values()), color="#7c3aed")
    ax.set_xlabel("Année")
    ax.set_ylabel("Reviews / an")
    ax.set_title("Distribution temporelle — reviews FULL")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "03e_distribution_temporelle_reviews.png", dpi=120)
    plt.close(fig)

    return {
        "min_year": int(min(counts.keys())),
        "max_year": int(max(counts.keys())),
        "by_year": counts,
    }


def main() -> None:
    log.info("=== Étape 3/4 : audit distributions (FULL via polars) ===")
    reviews_lf = scan_concat(REVIEWS_DIR)
    meta_lf = scan_concat(META_DIR)

    metrics: dict[str, Any] = {}

    log.info("Distribution reviews par catégorie…")
    metrics["reviews_per_cat"] = per_category_count(reviews_lf)
    plot_per_cat(
        metrics["reviews_per_cat"],
        "Reviews par catégorie (FULL)",
        FIG_DIR / "03a_distribution_reviews_par_cat.png",
    )

    log.info("Distribution meta par catégorie…")
    metrics["meta_per_cat"] = per_category_count(meta_lf)
    plot_per_cat(
        metrics["meta_per_cat"],
        "Items par catégorie (meta FULL)",
        FIG_DIR / "03b_distribution_meta_par_cat.png",
    )

    log.info("Distribution prix (sur meta)…")
    metrics["prices"] = price_stats_from_meta(meta_lf)

    log.info("Distribution ratings (sur reviews)…")
    metrics["ratings"] = ratings_distribution(reviews_lf)

    log.info("Distribution temporelle (sur reviews)…")
    metrics["temporal"] = temporal_distribution(reviews_lf)

    out_json = REPORTS_DIR / "audit_distributions_metrics.json"
    out_json.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Métriques → %s", out_json)
    log.info("Étape 3 OK.")


if __name__ == "__main__":
    main()
