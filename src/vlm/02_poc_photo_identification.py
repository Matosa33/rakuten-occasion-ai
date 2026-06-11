"""PoC A (Cycle 17.0) — Identification produit depuis une PHOTO via VLM-extraction.

Protocole (induction, pas déduction — exigence humaine 2026-06-11) :
1. Échantillonne N produits du catalogue Electronics ayant ≥ 2 images ET présents
   dans le train (= dans l'index FAISS de l'API).
2. Pour chaque produit : la 2ᵉ image (vue différente de la MAIN = meilleur proxy
   disponible d'une « photo utilisateur ») est envoyée au VLM OpenRouter avec un
   prompt d'extraction orientée recherche.
3. La description extraite alimente `POST /identify` de l'API réelle (index
   complet 3,16 M produits) — le chemin de prod exact.
4. Mesure : rang du parent_asin source dans les candidats → hit@1 / hit@5 / hit@30,
   latences VLM + retrieval, et échantillon des descriptions pour inspection.

Sortie : `reports/11_poc_photo/poc_a_vlm_extraction.json`

Lancer (stack compose up, API healthy) :

    python -m src.vlm.02_poc_photo_identification
"""

from __future__ import annotations

import ast
import json
import logging
import os
import time

import polars as pl
import requests
from dotenv import load_dotenv

from src.config import DATA_PROCESSED_PRODUCTS, REPO_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

N_PRODUCTS = 25
SEED = 42
RAW_META = REPO_ROOT / "data" / "raw" / "full" / "meta" / "Electronics.parquet"
OUT_DIR = REPO_ROOT / "reports" / "11_poc_photo"
API_BASE = os.environ.get("POC_API_BASE", "http://localhost:8082/api")  # via proxy frontend
VLM_MODEL = os.environ.get("POC_VLM_MODEL", "google/gemma-4-31b-it")

# v2 (induction PoC) : le format télégraphique "Object type: X, Brand: Y" du v1
# matche mal les titres catalogue. On demande au VLM d'écrire COMME un titre
# Amazon (l'espace dans lequel l'index a été encodé).
VLM_PROMPT = (
    "Look at this product photo. Write the most likely Amazon product listing title "
    "for it: brand, model name/number, key specs, color — exactly as a seller would "
    "title it. Use any text visible in the image. Reply with the title only."
)


def _sample_products() -> list[dict]:
    """N produits Electronics avec ≥ 2 images, présents dans le train (= l'index)."""
    train_asins = set(
        pl.scan_parquet(DATA_PROCESSED_PRODUCTS / "train.parquet")
        .select("parent_asin")
        .collect()["parent_asin"]
        .to_list()
    )
    log.info("train asins: %s", f"{len(train_asins):_}")

    df = (
        pl.scan_parquet(RAW_META)
        .select(["parent_asin", "title", "images"])
        .filter(pl.col("images").str.len_chars() > 200)  # heuristique multi-images
        .head(40_000)
        .collect()
    )
    picked: list[dict] = []
    for row in df.sample(fraction=1.0, shuffle=True, seed=SEED).iter_rows(named=True):
        if row["parent_asin"] not in train_asins:
            continue
        try:
            imgs = ast.literal_eval(row["images"])
        except (ValueError, SyntaxError):
            continue
        urls = [
            i.get("large") or i.get("hi_res") for i in imgs if i.get("large") or i.get("hi_res")
        ]
        if len(urls) < 2:
            continue
        picked.append(
            {
                "parent_asin": row["parent_asin"],
                "title": row["title"],
                "query_image": urls[1],  # 2ᵉ vue = proxy photo user
            }
        )
        if len(picked) >= N_PRODUCTS:
            break
    return picked


def _vlm_describe(key: str, image_url: str) -> tuple[str, float]:
    started = time.perf_counter()
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": VLM_MODEL,
            "max_tokens": 150,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VLM_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        },
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip(), time.perf_counter() - started


def _api_token() -> str:
    r = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": "demo", "password": "demo"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _identify(token: str, text: str) -> tuple[list[str], float]:
    started = time.perf_counter()
    r = requests.post(
        f"{API_BASE}/identify",
        headers={"Authorization": f"Bearer {token}"},
        json={"text_hint": text},
        timeout=180,
    )
    r.raise_for_status()
    asins = [c["parent_asin"] for c in r.json()["top_candidates"]]
    return asins, time.perf_counter() - started


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key = os.environ["OPENROUTER_API_KEY"]
    products = _sample_products()
    log.info("échantillon : %d produits avec 2ᵉ vue", len(products))
    token = _api_token()

    results = []
    for i, p in enumerate(products, 1):
        try:
            desc, t_vlm = _vlm_describe(key, p["query_image"])
            candidates, t_ret = _identify(token, desc)
            rank = (
                candidates.index(p["parent_asin"]) + 1 if p["parent_asin"] in candidates else None
            )
        except Exception as e:  # noqa: BLE001 — un échec réseau ne tue pas le bench
            log.warning("produit %s en erreur : %s", p["parent_asin"], e)
            desc, t_vlm, candidates, t_ret, rank = f"(error: {e})", None, [], None, None
        results.append(
            {
                "parent_asin": p["parent_asin"],
                "title": p["title"][:90],
                "vlm_description": desc,
                "rank": rank,
                "t_vlm_sec": round(t_vlm, 2) if t_vlm else None,
                "t_retrieval_sec": round(t_ret, 2) if t_ret else None,
            }
        )
        log.info("[%d/%d] rank=%s | %s", i, len(products), rank, desc[:80])

    ranks = [r["rank"] for r in results if r["rank"] is not None]
    n_ok = len([r for r in results if not str(r["vlm_description"]).startswith("(error")])
    summary = {
        "protocol": "2nd catalog view -> VLM describe -> /identify on FULL 3.16M index",
        "model": VLM_MODEL,
        "n_products": len(results),
        "n_calls_ok": n_ok,
        "hit_at_1": sum(1 for r in ranks if r == 1) / n_ok if n_ok else 0,
        "hit_at_5": sum(1 for r in ranks if r <= 5) / n_ok if n_ok else 0,
        "hit_at_30": len(ranks) / n_ok if n_ok else 0,
        "median_t_vlm_sec": sorted(r["t_vlm_sec"] for r in results if r["t_vlm_sec"])[n_ok // 2]
        if n_ok
        else None,
        "results": results,
    }
    out = OUT_DIR / "poc_a_vlm_extraction.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(
        "PoC A : hit@1=%.2f hit@5=%.2f hit@30=%.2f (n=%d) -> %s",
        summary["hit_at_1"],
        summary["hit_at_5"],
        summary["hit_at_30"],
        n_ok,
        out,
    )
    # Sortie programme JSON (pipe/jq) — R6 ok (D-029).
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
