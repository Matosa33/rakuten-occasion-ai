"""Étape 2/4 — Audit qualité sur les 3 catégories COMPLÈTES (polars lazy).

Lit  : data/raw/full/{reviews,meta}/<Cat>.parquet (3 reviews + 3 meta)
Écrit:
  - reports/figures/02a_nan_par_colonne_reviews.png
  - reports/figures/02b_nan_par_colonne_meta.png
  - reports/figures/02_length_<col>_reviews.png  (×2)
  - reports/figures/02_length_<col>_meta.png     (×2)
  - reports/audit_qualite_metrics.json

Pourquoi polars lazy
--------------------
À ce volume (jusqu'à 200+ M lignes pour Electronics reviews), pandas en mémoire
ne tient pas (50+ GB de RAM). polars.scan_parquet() construit un plan d'exécution
lazy qui ne charge que les colonnes demandées et streame les calculs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import polars as pl
import seaborn as sns

from src.data.audit import CATEGORIES, scan_concat  # source unique de vérité (D-008)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEWS_DIR = REPO_ROOT / "data" / "raw" / "full" / "reviews"
META_DIR = REPO_ROOT / "data" / "raw" / "full" / "meta"
FIG_DIR = REPO_ROOT / "reports" / "figures"
REPORTS_DIR = REPO_ROOT / "reports"
FIG_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")


def nan_ratio_lazy(lf: pl.LazyFrame) -> dict[str, float]:
    """NaN ratio par colonne, en streaming colonne-par-colonne.

    Sur 348 M lignes × 16 colonnes, l'aggregation parallèle multi-colonnes
    fait sauter la RAM (~50 GB pic). On itère colonne par colonne avec
    `engine="streaming"` pour borner le pic à ~quelques GB.
    """
    schema = lf.collect_schema()
    cols = list(schema.names())
    n_total = lf.select(pl.len()).collect(engine="streaming").item()
    if n_total == 0:
        return {}
    ratios: dict[str, float] = {}
    for c in cols:
        n_null = lf.select(pl.col(c).is_null().sum()).collect(engine="streaming").item()
        ratios[c] = round(int(n_null) / n_total, 4)
    return ratios


def plot_nan(ratio: dict[str, float], title: str, out: Path) -> None:
    if not ratio:
        return
    items = sorted(ratio.items(), key=lambda kv: kv[1], reverse=True)
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(10, max(4, 0.35 * len(labels))))
    ax.barh(labels, values, color="#dc2626")
    ax.set_xlabel("Ratio de null")
    ax.set_title(title)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def text_length_stats(lf: pl.LazyFrame, col: str) -> dict[str, Any]:
    """Stats de longueur (caractères) pour une colonne texte."""
    if col not in lf.collect_schema().names():
        return {}
    stats = (
        lf.select(
            pl.col(col).cast(pl.Utf8, strict=False).str.len_chars().alias("len"),
        )
        .filter(pl.col("len").is_not_null())
        .select(
            n_non_null=pl.len(),
            mean=pl.col("len").mean(),
            median=pl.col("len").median(),
            p95=pl.col("len").quantile(0.95),
            max=pl.col("len").max(),
            n_below_5_chars=(pl.col("len") < 5).sum(),
        )
        .collect(engine="streaming")
        .to_dicts()[0]
    )
    return {
        k: (
            int(v)
            if v is not None and k in {"n_non_null", "max", "n_below_5_chars"}
            else (round(float(v), 2) if v is not None else None)
        )
        for k, v in stats.items()
    }


def plot_length_hist(lf: pl.LazyFrame, col: str, out: Path) -> None:
    """Histogramme des longueurs en sample : matérialiser 348 M longueurs
    int64 = ~3 GB déjà juste pour la colonne, donc on prend un sample
    aléatoire de 500k via streaming + Bernoulli sampling.
    """
    if col not in lf.collect_schema().names():
        return
    # Bernoulli sampling lazy : on garde ~0.2 % puis on cap dur à 500k.
    df_sample = (
        lf.select(
            pl.col(col).cast(pl.Utf8, strict=False).str.len_chars().alias("len"),
        )
        .filter(pl.col("len").is_not_null())
        .filter(pl.int_range(pl.len()) % 700 == 0)  # downsample ~0.14 %
        .collect(engine="streaming")
    )
    if df_sample.is_empty():
        return
    df = df_sample.sample(n=min(500_000, df_sample.height), seed=42)
    lengths = df["len"].to_numpy()
    p99 = float(df.select(pl.col("len").quantile(0.99)).item() or 0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(lengths.clip(max=p99) if p99 > 0 else lengths, bins=50, color="#2563eb")
    ax.set_xlabel(f"Longueur de '{col}' (caractères, clip p99)")
    ax.set_ylabel("Effectif")
    ax.set_title(f"Distribution longueur — {col}")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> None:
    log.info("=== Étape 2/4 : audit qualité (FULL via polars) ===")

    reviews_lf = scan_concat(REVIEWS_DIR)
    meta_lf = scan_concat(META_DIR)

    n_reviews = reviews_lf.select(pl.len()).collect(engine="streaming").item()
    n_meta = meta_lf.select(pl.len()).collect(engine="streaming").item()
    log.info("Reviews FULL : %s lignes (%d cat concat)", f"{n_reviews:_}", len(CATEGORIES))
    log.info("Meta    FULL : %s lignes (%d cat concat)", f"{n_meta:_}", len(CATEGORIES))

    metrics: dict[str, Any] = {
        "n_reviews_total": int(n_reviews),
        "n_meta_total": int(n_meta),
        "categories": list(CATEGORIES),
    }

    # NaN ratios
    log.info("Calcul NaN ratio reviews…")
    metrics["reviews_nan_ratio"] = nan_ratio_lazy(reviews_lf)
    plot_nan(
        metrics["reviews_nan_ratio"],
        "NaN par colonne (reviews FULL, 3 cat)",
        FIG_DIR / "02a_nan_par_colonne_reviews.png",
    )

    log.info("Calcul NaN ratio meta…")
    metrics["meta_nan_ratio"] = nan_ratio_lazy(meta_lf)
    plot_nan(
        metrics["meta_nan_ratio"],
        "NaN par colonne (meta FULL, 3 cat)",
        FIG_DIR / "02b_nan_par_colonne_meta.png",
    )

    # Doublons sur reviews (clés stratégiques) — n_unique colonne par colonne en streaming
    log.info("Calcul doublons reviews…")
    reviews_cols = reviews_lf.collect_schema().names()
    rev_uniq: dict[str, int | None] = {"n_total": int(n_reviews)}
    for c in ("parent_asin", "user_id", "asin"):
        if c in reviews_cols:
            rev_uniq[f"n_unique_{c}"] = int(
                reviews_lf.select(pl.col(c).n_unique()).collect(engine="streaming").item()
            )
        else:
            rev_uniq[f"n_unique_{c}"] = None
    metrics["reviews_uniqueness"] = rev_uniq

    # Doublons sur meta
    log.info("Calcul doublons meta…")
    n_unique_meta_parent = int(
        meta_lf.select(pl.col("parent_asin").n_unique()).collect(engine="streaming").item()
    )
    metrics["meta_uniqueness"] = {
        "n_total": int(n_meta),
        "n_unique_parent_asin": n_unique_meta_parent,
    }

    # Longueurs textes (reviews et meta séparément)
    log.info("Calcul longueurs textes…")
    for col in ("title", "text"):
        if col in reviews_lf.collect_schema().names():
            metrics[f"reviews_length_{col}"] = text_length_stats(reviews_lf, col)
            plot_length_hist(reviews_lf, col, FIG_DIR / f"02_length_{col}_reviews.png")

    for col in ("title", "description"):
        if col in meta_lf.collect_schema().names():
            metrics[f"meta_length_{col}"] = text_length_stats(meta_lf, col)
            plot_length_hist(meta_lf, col, FIG_DIR / f"02_length_{col}_meta.png")

    out_json = REPORTS_DIR / "audit_qualite_metrics.json"
    out_json.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Métriques → %s", out_json)
    log.info("Étape 2 OK.")


if __name__ == "__main__":
    main()
