"""Étape 1/4 - Télécharger les N catégories COMPLÈTES du périmètre actif D-008.

Source : McAuley-Lab/Amazon-Reviews-2023 (HuggingFace).
Doc    : https://amazon-reviews-2023.github.io/data_loading/huggingface.html

POURQUOI le full (et pas un sample)
-----------------------------------
Un sample (premier N lignes) introduit deux biais qui rendent l'audit non-concluant :
  - les `parent_asin` du sample reviews et du sample meta sont disjoints (~99 % NaN
    après merge - finding majeur de l'audit v1 sample superseded D-007/D-008) ;
  - les premières lignes sont concentrées sur peu d'utilisateurs et peu d'années,
    donc les distributions calculées ne reflètent pas la réalité du dataset.

On télécharge donc les 2N fichiers complets pour les N catégories du périmètre
défini par `CATEGORIES` (cf. `src/data/audit/__init__.py`, single source of vérité).
Inscrit dans ADR D-007 (full vs sample) + D-008 (périmètre).

Mécanique
---------
- Téléchargement via `huggingface_hub.hf_hub_download` qui gère :
    * le resume automatique en cas de coupure ;
    * le cache local (HF_HOME) ;
    * la vérification de l'intégrité (sha256).
- Conversion en parquet zstd côté ingestion : compresse ~3-5× le JSONL et
  permet la lecture columnar lazy par `polars.scan_parquet()` à l'audit.
- Pas de chargement en RAM du JSONL complet : conversion ligne-par-ligne
  via `polars.scan_ndjson(...).sink_parquet(...)` (streaming sink).

Sortie
------
- data/raw/full/reviews/<Cat>.parquet
- data/raw/full/meta/<Cat>.parquet

Lance ce script depuis la racine du repo :

    python -m src.data.audit.01_load_full

Espace disque requis : ~50 GB libres (35 GB JSONL cache HF + ~12 GB parquet).
Durée estimée : 30-90 min selon connexion (premier run, resume après).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import polars as pl
from huggingface_hub import hf_hub_download

from src.config import DATA_RAW
from src.config import DATA_RAW_FULL_META as META_DIR
from src.config import DATA_RAW_FULL_REVIEWS as REVIEWS_DIR
from src.data.audit import CATEGORIES  # source unique de vérité (D-008)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HF_REPO_ID = "McAuley-Lab/Amazon-Reviews-2023"

# Schémas attendus (cf. https://amazon-reviews-2023.github.io/data_loading/huggingface.html).
# Utilisé par le fallback pandas chunked pour garantir un schéma stable entre chunks
# (sinon ParquetWriter plante quand un chunk omet une colonne ou infère un type différent).
REVIEWS_COLS: tuple[str, ...] = (
    "rating",
    "title",
    "text",
    "images",
    "asin",
    "parent_asin",
    "user_id",
    "timestamp",
    "helpful_vote",
    "verified_purchase",
)
META_COLS: tuple[str, ...] = (
    "main_category",
    "title",
    "average_rating",
    "rating_number",
    "features",
    "description",
    "price",
    "images",
    "videos",
    "store",
    "categories",
    "details",
    "parent_asin",
    "bought_together",
    "subtitle",
    "author",
)


def _download_jsonl(remote_path: str) -> Path:
    """Télécharge un fichier .jsonl via hf_hub_download (resume + cache natif)."""
    log.info("hf_hub_download %s", remote_path)
    local_path = hf_hub_download(
        repo_id=HF_REPO_ID,
        filename=remote_path,
        repo_type="dataset",
        # cache local par défaut : ~/.cache/huggingface
    )
    return Path(local_path)


def _jsonl_to_parquet_polars(jsonl_path: Path, parquet_path: Path) -> bool:
    """Tente la conversion via polars (rapide, lazy). Retourne True si OK, False si échec."""
    try:
        # infer_schema_length=0 force l'inférence sur l'ensemble du fichier
        # plutôt que sur les 100 premières lignes (plus robuste mais plus lent
        # pour le scan initial). Idéal pour les meta qui mélangent prix string et number.
        pl.scan_ndjson(jsonl_path, infer_schema_length=0).sink_parquet(
            parquet_path,
            compression="zstd",
            compression_level=3,
        )
        return True
    except Exception as e:
        log.warning(
            "  polars sink_parquet a échoué (%s) → fallback pandas chunked", type(e).__name__
        )
        return False


def _jsonl_to_parquet_pandas(
    jsonl_path: Path, parquet_path: Path, expected_cols: tuple[str, ...]
) -> None:
    """Fallback : conversion pandas chunked avec schéma explicite et stable.

    - On reindex chaque chunk sur `expected_cols` (cols absentes = None).
    - On force-cast TOUTES les colonnes en string pour garantir un schéma constant
      entre chunks (sinon ParquetWriter plante).
    - Listes/dicts deviennent leur repr str ; NaN devient None Arrow.
    - Les casts numériques (price, rating, timestamp) se font côté audit/cleaning.
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    log.info(
        "  pandas chunked (chunksize=50k, schéma fixe %d cols) → %s",
        len(expected_cols),
        parquet_path.name,
    )
    writer: pq.ParquetWriter | None = None
    n_total = 0
    for chunk in pd.read_json(jsonl_path, lines=True, chunksize=50_000):
        # 1. Reindex sur les colonnes attendues (cols absentes = NaN).
        chunk = chunk.reindex(columns=list(expected_cols))
        # 2. Stringify : listes/dicts → str, NaN/None → None.
        for col in chunk.columns:
            chunk[col] = chunk[col].apply(
                lambda x: None if x is None or (isinstance(x, float) and pd.isna(x)) else str(x)
            )
            chunk[col] = chunk[col].astype("string")
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(parquet_path, table.schema, compression="zstd")
        writer.write_table(table)
        n_total += len(chunk)
    if writer is not None:
        writer.close()
    log.info("  pandas chunked OK, %s lignes écrites", f"{n_total:_}")


def _jsonl_to_parquet(jsonl_path: Path, parquet_path: Path, expected_cols: tuple[str, ...]) -> None:
    """Convertit un .jsonl en parquet zstd. Tente polars d'abord, fallback pandas chunked."""
    if parquet_path.exists():
        log.info("  → parquet déjà présent (%s), skip", parquet_path.name)
        return
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("  → conversion %s → %s", jsonl_path.name, parquet_path.name)
    if not _jsonl_to_parquet_polars(jsonl_path, parquet_path):
        # Le polars peut avoir laissé un parquet partiel : on supprime avant fallback.
        if parquet_path.exists():
            parquet_path.unlink()
        _jsonl_to_parquet_pandas(jsonl_path, parquet_path, expected_cols)
    size_mb = parquet_path.stat().st_size / 1_048_576
    log.info("  → %s écrit (%.1f MB)", parquet_path.name, size_mb)


def download_reviews_full() -> None:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        log.info("--- Reviews FULL : %s ---", cat)
        jsonl = _download_jsonl(f"raw/review_categories/{cat}.jsonl")
        _jsonl_to_parquet(jsonl, REVIEWS_DIR / f"{cat}.parquet", REVIEWS_COLS)


def download_meta_full() -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        log.info("--- Meta FULL : %s ---", cat)
        jsonl = _download_jsonl(f"raw/meta_categories/meta_{cat}.jsonl")
        _jsonl_to_parquet(jsonl, META_DIR / f"{cat}.parquet", META_COLS)


def main() -> None:
    log.info("=== Étape 1/4 : load FULL Amazon Reviews 2023 ===")
    log.info("Catégories : %s", CATEGORIES)
    log.info(
        "Volume attendu pour le périmètre D-008 : ~227 GB JSONL côté HF cache, "
        "~57 GB côté parquet local."
    )
    log.info("Répertoires de sortie : %s, %s", REVIEWS_DIR, META_DIR)

    free = shutil.disk_usage(DATA_RAW.parent).free / 1024**3
    log.info("Espace libre détecté : %.1f GB", free)
    if free < 50:
        log.warning(
            "ATTENTION : moins de 50 GB libres. "
            "Le download peut échouer au milieu. Considère libérer de l'espace."
        )

    download_reviews_full()
    download_meta_full()

    log.info("Étape 1 OK. Sorties dans data/raw/full/{reviews,meta}/")


if __name__ == "__main__":
    main()
