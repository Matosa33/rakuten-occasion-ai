"""Étape 2/5 du cleaning — Drop colonnes sparses, sauf cas spéciaux Books.

Drop par défaut :
- `subtitle` (~85 % NaN au full D-008)
- `author` (~89 % NaN au full D-008)

Exception : pour la catégorie Books (et CDs_and_Vinyl, Movies_and_TV), ces
champs sont **denses** (NaN < 50 %) et porteurs de signal. On les conserve
pour ces sous-périmètres uniquement.

Stratégie : on ne supprime pas la colonne entière ; on **vide** (set None)
les valeurs hors-domaine, ce qui permet de garder un schéma stable au
parquet et de laisser Pandera (Cycle 1.4) faire la validation finale.

Lance ce script depuis la racine du repo :

    python -m src.data.clean.02_drop_sparse_columns

Sortie : data/processed/intermediate/02_meta_pruned.parquet
"""

from __future__ import annotations

import logging

import polars as pl

from src.config import DATA_PROCESSED_INTERMEDIATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

IN_PATH = DATA_PROCESSED_INTERMEDIATE / "01_meta_enriched.parquet"
OUT_PATH = DATA_PROCESSED_INTERMEDIATE / "02_meta_pruned.parquet"

# Catégories où subtitle et author portent du signal (NaN < 50 % mesuré au full)
TEXT_RICH_CATEGORIES = ("Books", "CDs_and_Vinyl", "Movies_and_TV")


def main() -> None:
    log.info("=== Étape 2/5 cleaning : drop colonnes sparses (subtitle, author) ===")

    if not IN_PATH.exists():
        raise FileNotFoundError(
            f"{IN_PATH.name} introuvable. Lance d'abord "
            "`python -m src.data.clean.01_join_meta_with_review_aggregates`."
        )

    if OUT_PATH.exists():
        log.info("→ output déjà présent (%s), skip", OUT_PATH.name)
        return

    log.info("Lecture %s…", IN_PATH.name)
    lf = pl.scan_parquet(IN_PATH)

    # Mesurer le NaN ratio AVANT (pour le rapport)
    n_total = lf.select(pl.len()).collect(engine="streaming").item()
    nan_subtitle_before = (
        lf.select(pl.col("subtitle").is_null().mean()).collect(engine="streaming").item()
    )
    nan_author_before = (
        lf.select(pl.col("author").is_null().mean()).collect(engine="streaming").item()
    )
    log.info(
        "Avant : %s items, subtitle %.1f %% NaN, author %.1f %% NaN",
        f"{n_total:_}",
        nan_subtitle_before * 100,
        nan_author_before * 100,
    )

    # Vider subtitle et author hors des cat text-rich
    text_rich_mask = pl.col("_source_category").is_in(list(TEXT_RICH_CATEGORIES))
    pruned_lf = lf.with_columns(
        pl.when(text_rich_mask).then(pl.col("subtitle")).otherwise(None).alias("subtitle"),
        pl.when(text_rich_mask).then(pl.col("author")).otherwise(None).alias("author"),
    )

    log.info("Écriture %s…", OUT_PATH.name)
    pruned_lf.sink_parquet(OUT_PATH, compression="zstd", compression_level=3)

    # Mesurer APRÈS pour vérifier
    out_lf = pl.scan_parquet(OUT_PATH)
    nan_subtitle_after = (
        out_lf.select(pl.col("subtitle").is_null().mean()).collect(engine="streaming").item()
    )
    nan_author_after = (
        out_lf.select(pl.col("author").is_null().mean()).collect(engine="streaming").item()
    )
    log.info(
        "Après : subtitle %.1f %% NaN (vidé hors %s), author %.1f %% NaN",
        nan_subtitle_after * 100,
        TEXT_RICH_CATEGORIES,
        nan_author_after * 100,
    )

    size_gb = OUT_PATH.stat().st_size / 1_073_741_824
    log.info("→ %s écrit (%.2f GB)", OUT_PATH.name, size_gb)
    log.info("Étape 2/5 OK.")


if __name__ == "__main__":
    main()
