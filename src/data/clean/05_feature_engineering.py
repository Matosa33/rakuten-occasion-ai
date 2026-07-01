"""Étape 5/5 du cleaning - Feature engineering numérique.

Features dérivées :
- `price_num` : prix parsé en Float64 (regex `[^\\d.]` pour virer "$",
  espaces, etc. ; cf. learnings.md timestamp-mixte / `price` mix Utf8/num).
- `log_price` : `log1p(price_num)`, utile pour modèles linéaires car
  distribution log-normale (cf. audit B3).
- `price_band` : catégoriel `"low"` (< 50 $), `"mid"` ([50, 200[),
  `"high"` (≥ 200), null si pas de prix.
- `length_title`, `length_description` : longueur en caractères (après
  cleaning étape 4).
- `n_reviews_log` : `log1p(n_reviews)` pour absorber la queue longue.
- `years_active` : `year_last_review - year_first_review + 1` (lifespan
  du produit en années visibles dans les reviews).
- `recency_year` : nombre d'années depuis `year_last_review` (par
  rapport à 2023, dernière année du dataset Amazon Reviews 2023).

Lance ce script depuis la racine du repo :

    python -m src.data.clean.05_feature_engineering

Sortie : data/processed/intermediate/05_meta_features.parquet
"""

from __future__ import annotations

import logging

import polars as pl

from src.config import DATA_PROCESSED_INTERMEDIATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

IN_PATH = DATA_PROCESSED_INTERMEDIATE / "04_meta_capped.parquet"
OUT_PATH = DATA_PROCESSED_INTERMEDIATE / "05_meta_features.parquet"

# Année de référence pour `recency_year` : dernière année du dataset Amazon
# Reviews 2023 (cf. audit reports/01_audit/audit_v1_amazon_reviews_2023.md).
DATASET_LAST_YEAR = 2023


def main() -> None:
    log.info("=== Étape 5/5 cleaning : feature engineering ===")

    if not IN_PATH.exists():
        raise FileNotFoundError(f"{IN_PATH.name} introuvable.")

    if OUT_PATH.exists():
        log.info("→ output déjà présent (%s), skip", OUT_PATH.name)
        return

    log.info("Lecture %s…", IN_PATH.name)
    lf = pl.scan_parquet(IN_PATH)

    # 1. Prix : parsing robuste string → Float64
    price_num = (
        pl.col("price")
        .cast(pl.Utf8, strict=False)
        .str.replace_all(r"[^\d.]", "")
        .cast(pl.Float64, strict=False)
    )

    # `price_num` mis null si <= 0 (parsing artifact, ex : "" → 0.0)
    price_num_clean = pl.when(price_num > 0).then(price_num).otherwise(None)

    # 2. log_price (log1p pour gérer 0 si réintroduit, mais on a filtré > 0)
    log_price = price_num_clean.log1p()

    # 3. price_band catégoriel
    price_band = (
        pl.when(price_num_clean.is_null())
        .then(None)
        .when(price_num_clean < 50)
        .then(pl.lit("low"))
        .when(price_num_clean < 200)
        .then(pl.lit("mid"))
        .otherwise(pl.lit("high"))
    )

    # 4. Longueurs textes (post-cleaning étape 4)
    length_title = pl.col("title").str.len_chars().fill_null(0)
    length_description = pl.col("description").str.len_chars().fill_null(0)

    # 5. n_reviews_log
    n_reviews_log = pl.col("n_reviews").cast(pl.Float64).log1p()

    # 6. years_active et recency_year
    years_active = (pl.col("year_last_review") - pl.col("year_first_review") + 1).cast(pl.Int32)
    recency_year = (DATASET_LAST_YEAR - pl.col("year_last_review")).cast(pl.Int32)

    features_lf = lf.with_columns(
        price_num_clean.alias("price_num"),
        log_price.alias("log_price"),
        price_band.alias("price_band"),
        length_title.alias("length_title"),
        length_description.alias("length_description"),
        n_reviews_log.alias("n_reviews_log"),
        years_active.alias("years_active"),
        recency_year.alias("recency_year"),
    )

    log.info("Écriture %s…", OUT_PATH.name)
    features_lf.sink_parquet(OUT_PATH, compression="zstd", compression_level=3)

    size_gb = OUT_PATH.stat().st_size / 1_073_741_824
    log.info("→ %s écrit (%.2f GB)", OUT_PATH.name, size_gb)
    log.info("Étape 5/5 OK.")


if __name__ == "__main__":
    main()
