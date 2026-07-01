"""Étape 4/5 du cleaning - Cap longueurs textes + flags qualité.

Cap obligatoire :
- `description` à 8192 caractères (max audit mesuré : 1 476 557 chars,
  outlier énorme - sans cap, l'encoder texte plante ou ralentit
  drastiquement).
- `title` à 1024 caractères (max audit mesuré : 2000, déjà raisonnable,
  cap par sécurité).

Flags qualité ajoutés (booléens, utiles pour le cleaning aval et le RAG) :
- `description_too_short` : description < 5 chars (45 % des items au full
  D-008, à imputer ou filtrer en C06+).
- `title_too_short` : title < 5 chars (rare ~0 % au full).
- `has_description` : description not null après cleaning.
- `has_title` : title not null.

Stack
-----
polars lazy + sink_parquet streaming.

Lance ce script depuis la racine du repo :

    python -m src.data.clean.04_cap_text_lengths

Sortie : data/processed/intermediate/04_meta_capped.parquet
"""

from __future__ import annotations

import logging

import polars as pl

from src.config import DATA_PROCESSED_INTERMEDIATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

IN_PATH = DATA_PROCESSED_INTERMEDIATE / "03_meta_normalized.parquet"
OUT_PATH = DATA_PROCESSED_INTERMEDIATE / "04_meta_capped.parquet"

DESCRIPTION_CAP_CHARS = 8192
TITLE_CAP_CHARS = 1024
SHORT_TEXT_THRESHOLD = 5


def main() -> None:
    log.info("=== Étape 4/5 cleaning : cap longueurs + flags qualité ===")

    if not IN_PATH.exists():
        raise FileNotFoundError(f"{IN_PATH.name} introuvable.")

    if OUT_PATH.exists():
        log.info("→ output déjà présent (%s), skip", OUT_PATH.name)
        return

    log.info("Lecture %s…", IN_PATH.name)
    lf = pl.scan_parquet(IN_PATH)

    capped_lf = lf.with_columns(
        # Cap description (slice retourne null si input null, OK)
        pl.col("description").str.slice(0, DESCRIPTION_CAP_CHARS).alias("description"),
        pl.col("title").str.slice(0, TITLE_CAP_CHARS).alias("title"),
    ).with_columns(
        # Flags qualité (calculés après cap)
        (pl.col("description").str.len_chars() < SHORT_TEXT_THRESHOLD)
        .fill_null(True)
        .alias("description_too_short"),
        (pl.col("title").str.len_chars() < SHORT_TEXT_THRESHOLD)
        .fill_null(True)
        .alias("title_too_short"),
        pl.col("description").is_not_null().alias("has_description"),
        pl.col("title").is_not_null().alias("has_title"),
    )

    log.info("Écriture %s…", OUT_PATH.name)
    capped_lf.sink_parquet(OUT_PATH, compression="zstd", compression_level=3)

    size_gb = OUT_PATH.stat().st_size / 1_073_741_824
    log.info("→ %s écrit (%.2f GB)", OUT_PATH.name, size_gb)
    log.info("Étape 4/5 OK.")


if __name__ == "__main__":
    main()
