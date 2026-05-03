"""Étape 6/6 du cleaning — Split stratifié 70/15/15 GroupKFold(parent_asin).

À ce stade :
- Input : `data/processed/intermediate/05_meta_features.parquet`
  (~26 M items product-level, enrichi + nettoyé + features)

Stratégie de split (anti-leakage cf. R3 + audit findings L1/L2/B1) :

1. **Group = parent_asin** : chaque produit (et toutes ses variantes
   asin) est entièrement dans UN seul split. Éviter L1 (variantes du
   même produit dans train ET test). Trivial ici car on est déjà
   product-level (1 ligne = 1 parent_asin), mais formalisé pour C07.

2. **Stratification = `_source_category`** : chaque catégorie est
   représentée à la même proportion dans les 3 splits. Anti-B1
   (déséquilibre catégoriel : Home_and_Kitchen 67M reviews vs
   Appliances 2M). Sans stratification, les petites cat seraient
   sous-représentées en val/test.

3. **Ratios 70/15/15** : standard ML, train assez large pour les
   classifieurs, val pour grid search hyperparams, test gardé immaculé
   pour métriques finales.

4. **Seed = 42** (cf. `src/config.py SEED`) pour reproductibilité.

Sorties :
- `data/processed/products/train.parquet` (~18 M items, 70 %)
- `data/processed/products/val.parquet`   (~4 M items, 15 %)
- `data/processed/products/test.parquet`  (~4 M items, 15 %)
- `data/processed/reviews_index/train.parquet` (parent_asin → split, joint
  ensuite lazy avec data/raw/full/reviews/ pour le RAG Cycle 6)
- `data/processed/reviews_index/val.parquet`
- `data/processed/reviews_index/test.parquet`

Lance ce script depuis la racine du repo :

    python -m src.data.split.01_split_stratified_groupkfold
"""

from __future__ import annotations

import logging

import polars as pl

from src.config import (
    CATEGORIES,
    DATA_PROCESSED_INTERMEDIATE,
    DATA_PROCESSED_PRODUCTS,
    DATA_PROCESSED_REVIEWS_INDEX,
    DATA_RAW_FULL_REVIEWS,
    SEED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

IN_PATH = DATA_PROCESSED_INTERMEDIATE / "05_meta_features.parquet"
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
TEST_FRAC = 0.15  # = 1 - TRAIN_FRAC - VAL_FRAC

assert abs(TRAIN_FRAC + VAL_FRAC + TEST_FRAC - 1.0) < 1e-9, "Fractions doivent sommer à 1"


def _stratified_split_one_category(df: pl.DataFrame, cat: str) -> pl.DataFrame:
    """Split stratifié 70/15/15 dans une catégorie (déjà product-level)."""
    n = df.height
    if n == 0:
        return df.with_columns(pl.lit(None).cast(pl.Utf8).alias("_split"))

    # Shuffle déterministe via sample(n, seed) — déjà stratifié par cat car
    # on opère cat-par-cat
    df_shuffled = df.sample(n=n, seed=SEED, shuffle=True)
    n_train = int(n * TRAIN_FRAC)
    n_val = int(n * VAL_FRAC)
    # n_test = n - n_train - n_val (le reste)

    splits = (
        ["train"] * n_train
        + ["val"] * n_val
        + ["test"] * (n - n_train - n_val)
    )
    return df_shuffled.with_columns(pl.Series("_split", splits))


def main() -> None:
    log.info("=== Étape 6/6 cleaning : split stratifié 70/15/15 ===")
    log.info("Stratégie : group=parent_asin (anti-L1), stratify=_source_category (anti-B1)")
    log.info("Seed=%d, fractions=%.0f/%.0f/%.0f", SEED, TRAIN_FRAC * 100, VAL_FRAC * 100, TEST_FRAC * 100)

    if not IN_PATH.exists():
        raise FileNotFoundError(f"{IN_PATH.name} introuvable. Lance d'abord les étapes 01-05.")

    DATA_PROCESSED_PRODUCTS.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED_REVIEWS_INDEX.mkdir(parents=True, exist_ok=True)

    log.info("Lecture %s…", IN_PATH.name)
    full_df = pl.read_parquet(IN_PATH)
    log.info("Total : %s items product-level", f"{full_df.height:_}")

    # Stratification cat-par-cat
    log.info("Stratification cat-par-cat…")
    parts: list[pl.DataFrame] = []
    for cat in CATEGORIES:
        df_cat = full_df.filter(pl.col("_source_category") == cat)
        df_cat_split = _stratified_split_one_category(df_cat, cat)
        parts.append(df_cat_split)
        counts = df_cat_split["_split"].value_counts().sort("_split")
        log.info(
            "  %s : n=%s, splits=%s",
            cat,
            f"{df_cat.height:_}",
            {row["_split"]: row["count"] for row in counts.to_dicts()},
        )

    full_split = pl.concat(parts, how="diagonal_relaxed")

    # Sauvegarde products par split
    for split_name in ("train", "val", "test"):
        df_split = full_split.filter(pl.col("_split") == split_name).drop("_split")
        out = DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet"
        df_split.write_parquet(out, compression="zstd", compression_level=3)
        size_gb = out.stat().st_size / 1_073_741_824
        log.info(
            "  → products/%s.parquet : %s items (%.2f GB)",
            split_name,
            f"{df_split.height:_}",
            size_gb,
        )

    # Construction reviews_index : (parent_asin, asin, _split) joint depuis
    # reviews bruts. Permet au RAG Cycle 6 de retrouver toutes les reviews
    # d'un produit dans le bon split sans dupliquer le contenu reviews.
    log.info("Construction reviews_index split-aware…")
    parent_asin_to_split = full_split.select("parent_asin", "_split")

    for split_name in ("train", "val", "test"):
        parent_asins_in_split = parent_asin_to_split.filter(
            pl.col("_split") == split_name
        )["parent_asin"].to_list()

        log.info(
            "  reviews_index/%s : %s parent_asins, scan reviews + join lazy…",
            split_name,
            f"{len(parent_asins_in_split):_}",
        )

        # Scan tous les reviews de toutes les cat, join sur parent_asin du split
        index_parts = []
        for cat in CATEGORIES:
            reviews_lf = pl.scan_parquet(DATA_RAW_FULL_REVIEWS / f"{cat}.parquet")
            cat_index = (
                reviews_lf.select("parent_asin", "asin", "user_id", "timestamp")
                .filter(pl.col("parent_asin").is_in(parent_asins_in_split))
                .with_columns(
                    pl.lit(cat).alias("_source_category"),
                    pl.lit(split_name).alias("_split"),
                )
                .collect(engine="streaming")
            )
            index_parts.append(cat_index)

        index_df = pl.concat(index_parts, how="diagonal_relaxed")
        out = DATA_PROCESSED_REVIEWS_INDEX / f"{split_name}.parquet"
        index_df.write_parquet(out, compression="zstd", compression_level=3)
        size_gb = out.stat().st_size / 1_073_741_824
        log.info(
            "  → reviews_index/%s.parquet : %s lignes (%.2f GB)",
            split_name,
            f"{index_df.height:_}",
            size_gb,
        )

    log.info("Étape 6/6 OK. Sortie products + reviews_index dans data/processed/")


if __name__ == "__main__":
    main()
