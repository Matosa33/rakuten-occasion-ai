"""Cycle 10.x / D-018 — Lookup d'affichage produit (vignette + catégorie fine).

Les colonnes riches (`images`, `categories`) ont été droppées du processed au
cleaning (D-006). L'UI a besoin de :
- la **vignette** (URL CDN) par candidat,
- la **catégorie fine** (feuille du breadcrumb `categories`, ex: "Graphics Cards"),
  pour répondre à F1 "catégorie L2" via l'architecture grounded (on identifie le
  produit exact → on affiche SA vraie catégorie, pas un classifieur L2 séparé, cf. D-018).

Plutôt que de re-joindre la raw meta lourde par requête, on pré-construit un
lookup minimal `[parent_asin, image_url, category_leaf]` chargé en RAM par
l'IdentificationService.

Sortie : `data/processed/products/product_lookup.parquet`.

Lance :

    python -m src.data.clean.06_build_product_lookup
"""

from __future__ import annotations

import ast
import logging

import polars as pl

from src.config import CATEGORIES, DATA_PROCESSED_PRODUCTS, DATA_RAW_FULL_META

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUT_LOOKUP = DATA_PROCESSED_PRODUCTS / "product_lookup.parquet"


def _extract_thumb_url(images_str: str | None) -> str | None:
    """URL vignette de l'entrée MAIN (thumb > large > hi_res, petit = charge vite)."""
    if not images_str or images_str in ("[]", "null", "None"):
        return None
    try:
        images_list = ast.literal_eval(images_str)
    except (ValueError, SyntaxError):
        return None
    if not images_list:
        return None
    main = next(
        (img for img in images_list if isinstance(img, dict) and img.get("variant") == "MAIN"),
        None,
    )
    if main is None:
        main = images_list[0] if isinstance(images_list[0], dict) else None
    if main is None:
        return None
    return main.get("thumb") or main.get("large") or main.get("hi_res")


def _extract_category_leaf(categories_str: str | None) -> str | None:
    """Feuille du breadcrumb `categories` (la catégorie la plus fine = L2/L3).

    Ex: "['Electronics', 'Television & Video', 'Video Glasses']" → "Video Glasses".
    """
    if not categories_str or categories_str in ("[]", "null", "None"):
        return None
    try:
        cats = ast.literal_eval(categories_str)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(cats, list) or not cats:
        return None
    leaf = cats[-1]
    return str(leaf) if leaf else None


def main() -> None:
    log.info("=== Lookup produit parent_asin → (vignette, catégorie fine) ===")
    DATA_PROCESSED_PRODUCTS.mkdir(parents=True, exist_ok=True)

    if OUT_LOOKUP.exists():
        log.info("→ %s déjà présent, skip", OUT_LOOKUP.name)
        return

    frames = []
    for cat in CATEGORIES:
        meta_path = DATA_RAW_FULL_META / f"{cat}.parquet"
        if not meta_path.exists():
            log.warning("  meta %s absente, skip", cat)
            continue
        df = pl.read_parquet(meta_path, columns=["parent_asin", "images", "categories"])
        image_urls = [_extract_thumb_url(s) for s in df["images"]]
        cat_leaves = [_extract_category_leaf(s) for s in df["categories"]]
        sub = pl.DataFrame(
            {
                "parent_asin": df["parent_asin"],
                "image_url": image_urls,
                "category_leaf": cat_leaves,
            }
        )
        n_img = sub.filter(pl.col("image_url").is_not_null()).height
        n_cat = sub.filter(pl.col("category_leaf").is_not_null()).height
        log.info(
            "  %s : %s items (%s vignettes, %s cat fines)",
            cat,
            f"{df.height:_}",
            f"{n_img:_}",
            f"{n_cat:_}",
        )
        frames.append(sub)

    if not frames:
        log.error("Aucune meta lue. Abandon.")
        return

    lookup = pl.concat(frames).unique(subset=["parent_asin"], keep="first")
    lookup.write_parquet(OUT_LOOKUP)
    log.info("→ %s : %s lignes", OUT_LOOKUP.name, f"{lookup.height:_}")


if __name__ == "__main__":
    main()
