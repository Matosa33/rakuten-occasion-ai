"""Étape 1/5 du cleaning - Enrichir meta avec agrégats de ses reviews.

Pour chaque produit (`parent_asin`) du périmètre actif (15 cat D-008), on
agrège les reviews qui le concernent en features descriptives, puis on
joint left sur la table meta. Résultat : un dataset product-level où
chaque ligne = 1 produit avec sa fiche meta + ses signaux d'usage.

Pourquoi product-level (vs review-level)
-----------------------------------------
Les 8 modèles ML internes (knn-faiss à pricing-cascade) du projet sont **product-level** :
classifier la catégorie d'un produit, retrouver un produit dans le
catalogue (FAISS), prédire son prix. La granularité review-level n'est
utile qu'au RAG (Cycle 6) qui aura besoin du texte des reviews - ce
besoin est servi séparément par `data/raw/full/reviews/` (déjà sur
disque) + un index split-aware produit en étape 06.

Cf. ADR D-009 (architecture cible RAG-grounded).

Agrégats produits par parent_asin
----------------------------------
- n_reviews : nombre de reviews
- mean_rating : moyenne du rating (cast Float64)
- std_rating : écart-type
- pct_verified : % verified_purchase=true (parsing string truthy défensif,
  cf. learnings.md timestamp-mixte-parser-deux-chemins-coalesce)
- pct_5stars, pct_1stars : % de notes extrêmes (signal sentiment)
- year_first_review, year_last_review : étendue temporelle (parsing
  timestamp coalesce Int64 ms / String ISO)
- n_unique_users : nombre de reviewers distincts
- mean_helpful_vote : moyenne des votes utiles (signal qualité reviews)

Stack
-----
polars lazy + streaming engine (R20 / D-006). Aucun .collect() sans
engine="streaming" ; agrégations cat-par-cat puis concat pour borner
la RAM même sur 348 M reviews × 15 cat.

Lance ce script depuis la racine du repo :

    python -m src.data.clean.01_join_meta_with_review_aggregates

Sortie : data/processed/intermediate/01_meta_enriched.parquet (~5-8 GB
zstd attendu, à mesurer).
"""

from __future__ import annotations

import logging

import polars as pl

from src.config import (
    CATEGORIES,
    COMPLEX_COLS_TO_DROP,
    DATA_PROCESSED_INTERMEDIATE,
    DATA_RAW_FULL_META,
    DATA_RAW_FULL_REVIEWS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUT_PATH = DATA_PROCESSED_INTERMEDIATE / "01_meta_enriched.parquet"


def _aggregate_reviews_per_product(reviews_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Group reviews par parent_asin → agrégats numériques.

    Patterns défensifs réutilisés :
    - rating cast Float64 (mix str "5"/"5.0" après concat hétérogène)
    - verified_purchase parsé en string truthy (Bool natif vs String "True"/"False")
    - timestamp coalesce (Int64 ms vs String ISO)
    """
    rating = pl.col("rating").cast(pl.Float64, strict=False)

    verified_truthy = (
        pl.col("verified_purchase")
        .cast(pl.Utf8, strict=False)
        .str.to_lowercase()
        .is_in(["true", "1"])
    )

    ts_str = pl.col("timestamp").cast(pl.Utf8, strict=False)
    year_expr = pl.coalesce(
        ts_str.str.to_datetime(strict=False).dt.year(),
        ts_str.cast(pl.Int64, strict=False)
        .cast(pl.Datetime(time_unit="ms"), strict=False)
        .dt.year(),
    )

    helpful_int = pl.col("helpful_vote").cast(pl.Int64, strict=False)

    return (
        reviews_lf.with_columns(
            rating.alias("_rating"),
            verified_truthy.alias("_verified"),
            year_expr.alias("_year"),
            helpful_int.alias("_helpful"),
        )
        .group_by("parent_asin")
        .agg(
            pl.len().alias("n_reviews"),
            pl.col("_rating").mean().alias("mean_rating"),
            pl.col("_rating").std().alias("std_rating"),
            pl.col("_verified").mean().alias("pct_verified"),
            (pl.col("_rating").round(0).cast(pl.Int64) == 5).mean().alias("pct_5stars"),
            (pl.col("_rating").round(0).cast(pl.Int64) == 1).mean().alias("pct_1stars"),
            pl.col("_year").min().alias("year_first_review"),
            pl.col("_year").max().alias("year_last_review"),
            pl.col("user_id").n_unique().alias("n_unique_users"),
            pl.col("_helpful").mean().alias("mean_helpful_vote"),
        )
    )


def _scan_meta_clean(cat: str) -> pl.LazyFrame:
    """Scan meta de la cat avec drop des colonnes complexes (D-006/D-009)."""
    lf = pl.scan_parquet(DATA_RAW_FULL_META / f"{cat}.parquet")
    present = [c for c in COMPLEX_COLS_TO_DROP if c in lf.collect_schema().names()]
    if present:
        lf = lf.drop(present)
    return lf.with_columns(pl.lit(cat).alias("_source_category"))


def _process_one_category(cat: str) -> pl.DataFrame:
    """Pipeline cat-par-cat pour borner le pic mémoire."""
    log.info("--- Cat : %s ---", cat)

    reviews_lf = pl.scan_parquet(DATA_RAW_FULL_REVIEWS / f"{cat}.parquet")
    aggregates_lf = _aggregate_reviews_per_product(reviews_lf)

    meta_lf = _scan_meta_clean(cat)

    enriched_lf = meta_lf.join(aggregates_lf, on="parent_asin", how="left")

    df = enriched_lf.collect(engine="streaming")
    log.info(
        "  %s : %s items meta enrichis (couverture reviews : %.2f %%)",
        cat,
        f"{df.height:_}",
        100 * df.filter(pl.col("n_reviews").is_not_null()).height / df.height,
    )
    return df


def main() -> None:
    log.info("=== Étape 1/5 cleaning : enrichir meta avec agrégats reviews ===")
    log.info("Périmètre actif : %d catégories (D-008)", len(CATEGORIES))

    DATA_PROCESSED_INTERMEDIATE.mkdir(parents=True, exist_ok=True)

    if OUT_PATH.exists():
        log.info("→ output déjà présent (%s), skip", OUT_PATH.name)
        log.info("   pour re-générer, supprimer le fichier d'abord.")
        return

    parts: list[pl.DataFrame] = []
    for cat in CATEGORIES:
        df = _process_one_category(cat)
        parts.append(df)

    log.info("Concat des %d catégories…", len(CATEGORIES))
    full = pl.concat(parts, how="diagonal_relaxed")
    log.info("Total items meta enrichis : %s", f"{full.height:_}")

    log.info("Écriture %s (parquet zstd niveau 3)…", OUT_PATH.name)
    full.write_parquet(OUT_PATH, compression="zstd", compression_level=3)

    size_gb = OUT_PATH.stat().st_size / 1_073_741_824
    log.info("→ %s écrit (%.2f GB)", OUT_PATH.name, size_gb)
    log.info("Étape 1/5 OK.")


if __name__ == "__main__":
    main()
