"""Sous-todo 2.3 — Encoder texte Arctic Embed L v2 (multilingue, 1024 dim).

Encode chaque produit (`title + description`) en un vecteur 1024-dim
sémantique normalisé L2. Sortie : 1 fichier `.npy` par split + 1 index
parquet pour le mapping `parent_asin → row_id`.

Modèle externe arctic (cf. docs/modeles.md) :
    Snowflake/snowflake-arctic-embed-l-v2.0
    - Architecture : XLM-RoBERTa-large multilingue
    - Output dim : 1024 (post-pooling, normalisé L2 par défaut sentence-transformers)
    - Context max : 8192 tokens (≪ cap descriptions 8192 chars en cleaning étape 04)
    - Licence : Apache 2.0
    - Frozen (pas de fine-tune, cf. ADR D-009 §6 hors-scope)

Stratégie d'exécution
---------------------
- Chargement modèle 1× au démarrage, GPU FP16 si CUDA dispo
- Lecture par split (train/val/test) en streaming polars
- Encoding batch 64 (ajustable selon VRAM)
- Sortie .npy mmap pour ne pas charger 4,5 M × 1024 × 2 bytes = ~9 GB en RAM
- Checkpoint par split (skip si .npy existe déjà = re-runs idempotents)

Lance ce script depuis la racine :

    python -m src.encoders.01_text_arctic
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import polars as pl

from src.config import (
    DATA_EMBEDDINGS,
    DATA_PROCESSED_PRODUCTS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "Snowflake/snowflake-arctic-embed-l-v2.0"
EMBED_DIM = 1024
BATCH_SIZE = 128  # RTX 4080 16GB : 128 OK pour XLM-R-large FP16 + max_seq 256
# Tokens : descriptions médianes 71 chars (~25 tokens), title 75 (~30 tokens),
# concat ≈ 55 tokens médian. 256 couvre p99. Attention en O(seq²) → 256 = 4× plus rapide que 512.
MAX_SEQ_LENGTH = 256
DTYPE_OUT = np.float16  # économie disque ~2× vs float32, perte précision négligeable pour retrieval

OUT_DIR = DATA_EMBEDDINGS / "text"
OUT_INDEX_PARQUET = DATA_EMBEDDINGS / "text_index_v1.parquet"


def _build_input_text(title: str | None, description: str | None) -> str:
    """Concat title + description, gère les None."""
    parts = []
    if title:
        parts.append(title.strip())
    if description:
        parts.append(description.strip())
    return " ".join(parts) if parts else ""


def _encode_split(model, split_name: str) -> tuple[Path, int]:
    """Encode un split products, sortie .npy mmap.

    Returns (out_npy_path, n_encoded).
    """
    in_path = DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet"
    out_path = OUT_DIR / f"text_arctic_{split_name}.npy"

    if out_path.exists():
        log.info("  → text_arctic_%s.npy déjà présent, skip", split_name)
        existing = np.load(out_path, mmap_mode="r")
        return out_path, existing.shape[0]

    log.info("  Lecture %s…", in_path.name)
    df = pl.read_parquet(
        in_path, columns=["parent_asin", "_source_category", "title", "description"]
    )
    n = df.height
    log.info("  %s : %s items à encoder", split_name, f"{n:_}")

    # Construction des inputs texte
    inputs = [_build_input_text(t, d) for t, d in zip(df["title"], df["description"], strict=False)]

    # Encoding batch
    log.info(
        "  Encoding %s : batch=%d, max_seq=%d, dtype=%s, device=%s",
        split_name,
        BATCH_SIZE,
        MAX_SEQ_LENGTH,
        DTYPE_OUT.__name__,
        model.device,
    )
    t_enc = time.time()
    embeddings = model.encode(
        inputs,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,  # L2 normalize built-in (cf. similarity_utils convention)
        convert_to_numpy=True,
    )
    enc_duration = time.time() - t_enc
    log.info(
        "  Encoding terminé : %s vecteurs %s en %.1f sec (%.0f items/sec)",
        f"{embeddings.shape[0]:_}",
        embeddings.shape,
        enc_duration,
        n / enc_duration,
    )

    # Cast en float16 + sauvegarde
    embeddings_fp16 = embeddings.astype(DTYPE_OUT)
    np.save(out_path, embeddings_fp16)
    size_mb = out_path.stat().st_size / 1_048_576
    log.info(
        "  → text_arctic_%s.npy écrit (%s items × %d dim FP16, %.1f MB)",
        split_name,
        f"{n:_}",
        embeddings.shape[1],
        size_mb,
    )

    return out_path, n


def _build_index_parquet() -> None:
    """Concat les 3 splits products avec leurs row_ids → un index global parquet.

    Format : (parent_asin, _source_category, _split, row_id_split, row_id_global)
    Permet aux modules aval (FAISS Cycle 4) de retrouver le vecteur d'un produit
    via son parent_asin.
    """
    log.info("Build text_index_v1.parquet (mapping global parent_asin → row_id)…")
    parts = []
    cumulative_offset = 0
    for split_name in ("train", "val", "test"):
        in_path = DATA_PROCESSED_PRODUCTS / f"{split_name}.parquet"
        df = (
            pl.read_parquet(in_path, columns=["parent_asin", "_source_category"])
            .with_row_index(name="row_id_split")
            .with_columns(
                pl.lit(split_name).alias("_split"),
                (pl.col("row_id_split") + cumulative_offset).alias("row_id_global"),
            )
        )
        parts.append(df)
        cumulative_offset += df.height
        log.info(
            "  %s : %s items, offset suivant = %s",
            split_name,
            f"{df.height:_}",
            f"{cumulative_offset:_}",
        )

    full_index = pl.concat(parts, how="diagonal_relaxed")
    full_index.write_parquet(OUT_INDEX_PARQUET, compression="zstd", compression_level=3)
    size_mb = OUT_INDEX_PARQUET.stat().st_size / 1_048_576
    log.info(
        "  → text_index_v1.parquet écrit (%s items, %.2f MB)", f"{full_index.height:_}", size_mb
    )


def main() -> None:
    log.info("=== Sous-todo 2.3 — Encoder texte Arctic Embed L v2 ===")
    log.info("Modèle : %s (frozen, FP16, normalize_embeddings=True)", MODEL_NAME)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Import sentence-transformers tardif (lourd) après vérification des paths
    log.info("Import sentence-transformers + chargement modèle…")
    t_load = time.time()
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info("Device : %s (CUDA dispo : %s)", device, torch.cuda.is_available())

    model = SentenceTransformer(MODEL_NAME, device=device, trust_remote_code=True)
    model.max_seq_length = MAX_SEQ_LENGTH
    if device == "cuda":
        model.half()  # FP16 pour gagner ~2× en VRAM et vitesse
    log.info("Modèle chargé en %.1f sec, max_seq=%d", time.time() - t_load, model.max_seq_length)

    # Encode les 3 splits
    t_total = time.time()
    total_items = 0
    for split_name in ("train", "val", "test"):
        log.info("--- Split %s ---", split_name)
        _, n = _encode_split(model, split_name)
        total_items += n

    log.info(
        "\n=== %s items encodés au total en %.1f min ===",
        f"{total_items:_}",
        (time.time() - t_total) / 60,
    )

    # Build index parquet global
    _build_index_parquet()

    log.info("\nSous-todo 2.3 OK.")
    log.info("Sorties :")
    log.info("  - data/embeddings/text/text_arctic_{train,val,test}.npy (3 fichiers)")
    log.info("  - data/embeddings/text_index_v1.parquet (mapping parent_asin → row_id)")


if __name__ == "__main__":
    main()
