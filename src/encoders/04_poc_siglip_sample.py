"""PoC B (Cycle 17.0) - Matching visuel pur SigLIP sur ÉCHANTILLON catalogue.

Protocole (induction - pendant du PoC A) :
1. Échantillonne ~2 000 produits Electronics avec ≥ 2 images (mêmes critères que A).
2. Télécharge l'image MAIN de chacun (mesure le débit CDN réel) → index visuel.
3. Pour ~100 d'entre eux, télécharge la 2ᵉ vue (proxy « photo utilisateur »).
4. Encode tout avec SigLIP (frozen), index flat numpy, recall@1/@5 mesurés.

⚠ BIAIS DOCUMENTÉS (à lire avec les chiffres) :
- Espace de recherche 2 k items vs 3,16 M en prod → recall OPTIMISTE (moins de
  distracteurs). Le PoC A, lui, cherche dans l'index COMPLET.
- Query = photo studio Amazon (vue différente) vs vraie photo utilisateur
  (lumière/fond/angle dégradés) → OPTIMISTE aussi (domain shift non mesuré).
- SigLIP *base* (CPU-friendly) vs SO400M prévu D-009 → légèrement PESSIMISTE.

Sortie : `reports/11_poc_photo/poc_b_siglip_sample.json`

Lancer :

    python -m src.encoders.04_poc_siglip_sample
"""

from __future__ import annotations

import ast
import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import polars as pl
import requests
from PIL import Image

from src.config import REPO_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

N_INDEX = 2000
N_QUERIES = 100
SEED = 42
RAW_META = REPO_ROOT / "data" / "raw" / "full" / "meta" / "Electronics.parquet"
OUT_DIR = REPO_ROOT / "reports" / "11_poc_photo"
MODEL_ID = "google/siglip-base-patch16-224"
BATCH = 16


def _sample(n: int) -> list[dict]:
    df = (
        pl.scan_parquet(RAW_META)
        .select(["parent_asin", "images"])
        .filter(pl.col("images").str.len_chars() > 200)
        .head(60_000)
        .collect()
        .sample(fraction=1.0, shuffle=True, seed=SEED)
    )
    picked = []
    for row in df.iter_rows(named=True):
        try:
            imgs = ast.literal_eval(row["images"])
        except (ValueError, SyntaxError):
            continue
        urls = [
            i.get("large") or i.get("hi_res") for i in imgs if i.get("large") or i.get("hi_res")
        ]
        if len(urls) < 2:
            continue
        picked.append({"parent_asin": row["parent_asin"], "main": urls[0], "alt": urls[1]})
        if len(picked) >= n:
            break
    return picked


def _download(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:  # noqa: BLE001 - image manquante = skip, pas crash
        return None


def _download_all(urls: list[str], label: str) -> dict[int, Image.Image]:
    started = time.perf_counter()
    out: dict[int, Image.Image] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(_download, u): i for i, u in enumerate(urls)}
        for fut, i in futures.items():
            img = fut.result()
            if img is not None:
                out[i] = img
    dt = time.perf_counter() - started
    log.info(
        "%s : %d/%d images en %.1fs (%.1f img/s)", label, len(out), len(urls), dt, len(out) / dt
    )
    return out


def _encode(images: list[Image.Image], model, processor) -> np.ndarray:
    import torch

    embs = []
    for i in range(0, len(images), BATCH):
        batch = images[i : i + BATCH]
        inputs = processor(images=batch, return_tensors="pt")
        with torch.no_grad():
            feats = model.get_image_features(**inputs)
        # Selon la version transformers, get_image_features renvoie un Tensor
        # ou un BaseModelOutputWithPooling → prendre le pooler_output.
        if not isinstance(feats, torch.Tensor):
            feats = feats.pooler_output
        feats = feats / feats.norm(dim=-1, keepdim=True)
        embs.append(feats.cpu().numpy())
    return np.concatenate(embs, axis=0)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = _sample(N_INDEX)
    log.info("échantillon : %d produits", len(sample))

    index_imgs = _download_all([p["main"] for p in sample], "index MAIN")
    query_ids = sorted(index_imgs.keys())[:N_QUERIES]
    query_imgs = _download_all([sample[i]["alt"] for i in query_ids], "queries ALT")
    query_ids = [i for i in query_ids if i in query_imgs]

    log.info("chargement SigLIP %s (CPU)…", MODEL_ID)
    from transformers import AutoModel, AutoProcessor

    model = AutoModel.from_pretrained(MODEL_ID)
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    idx_keys = sorted(index_imgs.keys())
    t0 = time.perf_counter()
    index_emb = _encode([index_imgs[i] for i in idx_keys], model, processor)
    t_index = time.perf_counter() - t0
    log.info(
        "index encodé : %d vecteurs en %.0fs (%.2f img/s)",
        len(idx_keys),
        t_index,
        len(idx_keys) / t_index,
    )

    query_emb = _encode([query_imgs[i] for i in query_ids], model, processor)

    sims = query_emb @ index_emb.T  # cosine (vecteurs L2-normalisés)
    pos_of = {k: j for j, k in enumerate(idx_keys)}
    ranks = []
    for qi, q_orig in enumerate(query_ids):
        order = np.argsort(-sims[qi])
        target = pos_of[q_orig]
        ranks.append(int(np.where(order == target)[0][0]) + 1)

    n = len(ranks)
    summary = {
        "protocol": "ALT view -> SigLIP -> flat search among N_INDEX MAIN views",
        "model": MODEL_ID,
        "n_index": len(idx_keys),
        "n_queries": n,
        "recall_at_1": sum(1 for r in ranks if r == 1) / n,
        "recall_at_5": sum(1 for r in ranks if r <= 5) / n,
        "recall_at_30": sum(1 for r in ranks if r <= 30) / n,
        "encode_throughput_img_per_sec_cpu": round(len(idx_keys) / t_index, 2),
        "biases": [
            "search space 2k vs 3.16M prod (optimistic)",
            "studio->studio query vs real user photo (optimistic)",
            "siglip-base vs SO400M (slightly pessimistic)",
        ],
        "ranks": ranks,
    }
    out = OUT_DIR / "poc_b_siglip_sample.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info(
        "PoC B : recall@1=%.2f recall@5=%.2f recall@30=%.2f (n=%d, index=%d)",
        summary["recall_at_1"],
        summary["recall_at_5"],
        summary["recall_at_30"],
        n,
        len(idx_keys),
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "ranks"}, indent=2))


if __name__ == "__main__":
    main()
