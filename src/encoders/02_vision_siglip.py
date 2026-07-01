"""Sous-todo 2.2 - Encoder vision SigLIP base sur images Amazon CDN.

Pour chaque produit (`parent_asin`) du périmètre actif (4 cat D-011, ~4,5 M
items), on récupère son image principale depuis l'URL CDN Amazon et on
l'encode via SigLIP en un vecteur 1024-dim normalisé L2.

Modèle externe siglip (cf. docs/modeles.md) :
    google/siglip-base-patch16-224
    - Architecture : ViT-B/16, sigmoid loss (vs softmax CLIP)
    - Output dim : 768 (base) ou 1024 (large) selon variant - base ici
    - Image input : 224×224 RGB
    - Licence : Apache 2.0
    - Frozen (pas de fine-tune, cf. ADR D-009)

Stratégie d'exécution
---------------------
- Lecture URL principale par produit : étape pré-processing dédiée
  qui parse `images` (string JSON liste of dict) et extrait `large` ou
  `hi_res` du `variant=='MAIN'`.
- Pipeline parallèle : ThreadPoolExecutor download (CPU) + GPU encoding
  par batch. Pendant que GPU encode batch N, CPU télécharge batch N+1.
- Checkpoint par catégorie : on encode cat-par-cat et sauve un .npy +
  parquet d'index intermédiaire après chaque cat. Reprise idempotente
  si interruption.
- Robustesse réseau : timeout 10 sec, retry exponentiel 3×, skip avec
  log si URL morte.
- Streaming : pas de stockage des JPG bruts, juste les vecteurs FP16.

Sortie (par cat puis concat global) :
- `data/embeddings/vision/checkpoints/<cat>.npy` (intermédiaires)
- `data/embeddings/vision/checkpoints/<cat>_index.parquet`
- `data/embeddings/vision_siglip_v1.npy` (concat final)
- `data/embeddings/vision_index_v1.parquet` (mapping parent_asin → row_id global)

Lance ce script depuis la racine :

    python -m src.encoders.02_vision_siglip
"""

from __future__ import annotations

import ast
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import polars as pl
import requests
from PIL import Image

from src.config import (
    CATEGORIES,
    DATA_EMBEDDINGS,
    DATA_RAW_FULL_META,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_NAME = "google/siglip-base-patch16-224"
EMBED_DIM = 768  # SigLIP base
BATCH_SIZE = 64  # ajustable selon VRAM
DTYPE_OUT = np.float16
N_DOWNLOAD_WORKERS = 24  # threads parallèles download
DOWNLOAD_TIMEOUT_SEC = 8
DOWNLOAD_RETRIES = 2
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Rakuten-AI-MVP-Research/0.1"

OUT_DIR = DATA_EMBEDDINGS / "vision"
CHECKPOINT_DIR = OUT_DIR / "checkpoints"
OUT_NPY_FINAL = DATA_EMBEDDINGS / "vision_siglip_v1.npy"
OUT_INDEX_FINAL = DATA_EMBEDDINGS / "vision_index_v1.parquet"


def _extract_main_image_url(images_str: str | None) -> str | None:
    """Parse la colonne `images` stringifiée et retourne la meilleure URL.

    Format Amazon Reviews 2023 : "[{'thumb': '...', 'large': '...',
    'variant': 'MAIN', 'hi_res': '...'}, {...}]"

    Stratégie : trouver l'entrée `variant=='MAIN'` (sinon premier entry),
    puis prendre `hi_res > large > thumb` dans cet ordre.
    """
    if not images_str or images_str in ("[]", "null", "None"):
        return None
    try:
        images_list = ast.literal_eval(images_str)
    except (ValueError, SyntaxError):
        return None
    if not images_list:
        return None
    # Cherche MAIN, sinon prend le premier
    main = next(
        (img for img in images_list if isinstance(img, dict) and img.get("variant") == "MAIN"), None
    )
    if main is None:
        main = images_list[0] if isinstance(images_list[0], dict) else None
    if main is None:
        return None
    return main.get("hi_res") or main.get("large") or main.get("thumb")


def _download_image(url: str, session: requests.Session) -> bytes | None:
    """GET HTTP avec timeout + retry. Retourne les bytes ou None si échec."""
    for attempt in range(DOWNLOAD_RETRIES + 1):
        try:
            resp = session.get(url, timeout=DOWNLOAD_TIMEOUT_SEC)
            if resp.status_code == 200:
                return resp.content
            if resp.status_code == 404:
                return None  # pas de retry sur 404
        except requests.RequestException:
            if attempt < DOWNLOAD_RETRIES:
                time.sleep(0.5 * (2**attempt))  # backoff exponentiel
    return None


def _process_batch_images(
    batch_urls: list[tuple[str, str]],  # [(parent_asin, url), ...]
    session: requests.Session,
    processor,
    model,
    device: str,
) -> tuple[list[str], np.ndarray]:
    """Download batch d'URLs, encode via SigLIP, retourne (parent_asins_ok, embeddings)."""
    import torch

    # Download parallèle
    images_pil: dict[str, Image.Image] = {}
    with ThreadPoolExecutor(max_workers=N_DOWNLOAD_WORKERS) as ex:
        futures = {ex.submit(_download_image, url, session): pa for pa, url in batch_urls}
        for fut in as_completed(futures):
            pa = futures[fut]
            try:
                img_bytes = fut.result()
                if img_bytes:
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    images_pil[pa] = img
            except Exception as e:  # noqa: BLE001 - une image corrompue ne doit pas tuer le batch
                log.debug("Image %s corrompue, skip : %s", pa, e)

    if not images_pil:
        return [], np.zeros((0, EMBED_DIM), dtype=DTYPE_OUT)

    # Encode batch GPU
    parent_asins_ok = list(images_pil.keys())
    image_list = [images_pil[pa] for pa in parent_asins_ok]

    inputs = processor(images=image_list, return_tensors="pt").to(device)
    with torch.no_grad():
        if device == "cuda":
            inputs = {k: v.half() if v.dtype == torch.float32 else v for k, v in inputs.items()}
        outputs = model.get_image_features(**inputs)
        # Normalize L2
        outputs = outputs / outputs.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    embeddings = outputs.cpu().numpy().astype(DTYPE_OUT)

    return parent_asins_ok, embeddings


def _process_one_category(cat: str, processor, model, device: str) -> tuple[Path, Path, int, int]:
    """Encode toutes les images d'une cat. Retourne (npy_path, index_path, n_ok, n_total)."""
    npy_path = CHECKPOINT_DIR / f"{cat}.npy"
    index_path = CHECKPOINT_DIR / f"{cat}_index.parquet"

    if npy_path.exists() and index_path.exists():
        existing = np.load(npy_path, mmap_mode="r")
        log.info(
            "  → checkpoint %s déjà présent : %s vecteurs, skip", cat, f"{existing.shape[0]:_}"
        )
        return npy_path, index_path, existing.shape[0], existing.shape[0]

    log.info("Lecture meta %s + extraction URLs principales…", cat)
    df = pl.read_parquet(
        DATA_RAW_FULL_META / f"{cat}.parquet",
        columns=["parent_asin", "images"],
    )
    n_total = df.height
    log.info("  %s : %s items meta", cat, f"{n_total:_}")

    # Extraction URLs
    urls = [_extract_main_image_url(s) for s in df["images"]]
    parent_asins = df["parent_asin"].to_list()
    pairs_with_url = [(pa, u) for pa, u in zip(parent_asins, urls, strict=False) if u is not None]
    n_with_url = len(pairs_with_url)
    log.info(
        "  %s : %s items avec URL principale extraite (%.1f %%)",
        cat,
        f"{n_with_url:_}",
        100 * n_with_url / n_total,
    )

    # Encoding par batch
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    all_pa_ok: list[str] = []
    all_embeddings: list[np.ndarray] = []

    n_batches = (n_with_url + BATCH_SIZE - 1) // BATCH_SIZE
    log.info("  Encoding %s en %d batches de %d…", cat, n_batches, BATCH_SIZE)
    t0 = time.time()
    last_log_t = t0

    for i in range(0, n_with_url, BATCH_SIZE):
        batch = pairs_with_url[i : i + BATCH_SIZE]
        pa_ok, embs = _process_batch_images(batch, session, processor, model, device)
        all_pa_ok.extend(pa_ok)
        all_embeddings.append(embs)

        # Log progress toutes les 60 sec
        if time.time() - last_log_t > 60:
            elapsed = time.time() - t0
            done = i + len(batch)
            rate = done / elapsed
            eta = (n_with_url - done) / rate / 60 if rate > 0 else 0
            log.info(
                "  %s : %s/%s items (%.0f items/sec, ETA %.1f min)",
                cat,
                f"{done:_}",
                f"{n_with_url:_}",
                rate,
                eta,
            )
            last_log_t = time.time()

    if all_embeddings:
        embeddings_full = np.vstack(all_embeddings)
    else:
        embeddings_full = np.zeros((0, EMBED_DIM), dtype=DTYPE_OUT)

    n_ok = len(all_pa_ok)
    log.info(
        "  %s : %s/%s items encodés (%.1f %% des items avec URL, %.1f %% du total) en %.1f min",
        cat,
        f"{n_ok:_}",
        f"{n_with_url:_}",
        100 * n_ok / max(n_with_url, 1),
        100 * n_ok / n_total,
        (time.time() - t0) / 60,
    )

    # Sauvegarde checkpoint
    np.save(npy_path, embeddings_full)
    pl.DataFrame(
        {
            "parent_asin": all_pa_ok,
            "_source_category": [cat] * n_ok,
            "row_id_cat": list(range(n_ok)),
        }
    ).write_parquet(index_path, compression="zstd", compression_level=3)

    return npy_path, index_path, n_ok, n_total


def _concat_checkpoints() -> None:
    """Concat les checkpoints par cat → fichier .npy + index parquet finaux."""
    log.info("Concat checkpoints → vision_siglip_v1.npy + vision_index_v1.parquet…")
    arrays: list[np.ndarray] = []
    index_parts: list[pl.DataFrame] = []
    cumulative_offset = 0

    for cat in CATEGORIES:
        npy_path = CHECKPOINT_DIR / f"{cat}.npy"
        index_path = CHECKPOINT_DIR / f"{cat}_index.parquet"
        if not (npy_path.exists() and index_path.exists()):
            log.warning("  ⚠️ checkpoint %s manquant, skip", cat)
            continue
        arr = np.load(npy_path)
        idx_df = pl.read_parquet(index_path).with_columns(
            (pl.col("row_id_cat") + cumulative_offset).alias("row_id_global")
        )
        arrays.append(arr)
        index_parts.append(idx_df)
        cumulative_offset += arr.shape[0]
        log.info(
            "  %s : %s vecteurs (offset suivant %s)",
            cat,
            f"{arr.shape[0]:_}",
            f"{cumulative_offset:_}",
        )

    if not arrays:
        log.error("Aucun checkpoint trouvé.")
        return

    full_array = np.vstack(arrays)
    full_index = pl.concat(index_parts, how="diagonal_relaxed")

    np.save(OUT_NPY_FINAL, full_array)
    full_index.write_parquet(OUT_INDEX_FINAL, compression="zstd", compression_level=3)

    npy_size_gb = OUT_NPY_FINAL.stat().st_size / 1_073_741_824
    idx_size_mb = OUT_INDEX_FINAL.stat().st_size / 1_048_576
    log.info(
        "→ vision_siglip_v1.npy : %s vecteurs × %d dim FP16 (%.2f GB)",
        f"{full_array.shape[0]:_}",
        full_array.shape[1],
        npy_size_gb,
    )
    log.info(
        "→ vision_index_v1.parquet : %s items (%.1f MB)", f"{full_index.height:_}", idx_size_mb
    )


def main() -> None:
    log.info("=== Sous-todo 2.2 - Encoder vision SigLIP base ===")
    log.info("Modèle : %s (frozen, FP16, normalize L2)", MODEL_NAME)
    log.info("Périmètre actif : %d catégories (D-011 MVP)", len(CATEGORIES))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Import transformers + chargement SigLIP…")
    t_load = time.time()
    import torch
    from transformers import AutoModel, AutoProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info("Device : %s", device)

    processor = AutoProcessor.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()
    if device == "cuda":
        model = model.half()
    log.info("Modèle chargé en %.1f sec, embed_dim=%d", time.time() - t_load, EMBED_DIM)

    # Encoding par cat (checkpoint après chaque)
    t_total = time.time()
    n_ok_total = 0
    n_total_total = 0
    for cat in CATEGORIES:
        log.info("\n--- Catégorie : %s ---", cat)
        _, _, n_ok, n_total = _process_one_category(cat, processor, model, device)
        n_ok_total += n_ok
        n_total_total += n_total

    log.info(
        "\n=== Encoding global terminé : %s/%s items (%.1f %%) en %.1f min ===",
        f"{n_ok_total:_}",
        f"{n_total_total:_}",
        100 * n_ok_total / max(n_total_total, 1),
        (time.time() - t_total) / 60,
    )

    # Concat final
    _concat_checkpoints()

    log.info("\nSous-todo 2.2 OK.")


if __name__ == "__main__":
    main()
