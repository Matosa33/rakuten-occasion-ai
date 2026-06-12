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
import json
import logging

import polars as pl

from src.config import CATEGORIES, DATA_PROCESSED_PRODUCTS, DATA_RAW_FULL_META

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUT_LOOKUP = DATA_PROCESSED_PRODUCTS / "product_lookup.parquet"

# Facettes discriminantes curées : nom canonique → clés `details` possibles.
# On exclut le bruit non-discriminant pour l'UX (Item Weight, Date First Available,
# Best Sellers Rank…). L'Akinator (entropie) choisira la meilleure facette PAR requête
# parmi celles présentes ET qui varient dans le set de candidats.
FACET_KEYS: dict[str, tuple[str, ...]] = {
    "color": ("Color",),
    "capacity": (
        "Memory Storage Capacity",
        "Digital Storage Capacity",
        "Hard Disk Size",
        "Capacity",
        "RAM",
    ),
    "size": ("Screen Size", "Size", "Display Size"),
    "material": ("Material",),
    "form_factor": ("Form Factor",),
    "style": ("Style", "Configuration"),
    "feature": ("Special Feature", "Special features"),
    "compatible_with": ("Compatible Devices", "Compatible Phone Models"),
}


MAX_IMAGES_PER_PRODUCT = 8  # borne la taille du lookup (la visionneuse n'a pas besoin de 30 vues)


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


def _extract_all_image_urls(images_str: str | None) -> list[str]:
    """TOUTES les vues du produit en grande taille (large > hi_res > thumb).

    Cycle 17.2 (D-035) : la visionneuse candidats + le VLM validateur ont besoin
    des N vues, pas seulement de la vignette MAIN. MAIN d'abord (cohérence avec
    la vignette), puis les autres variants dans l'ordre du listing.
    """
    if not images_str or images_str in ("[]", "null", "None"):
        return []
    try:
        images_list = ast.literal_eval(images_str)
    except (ValueError, SyntaxError):
        return []
    if not isinstance(images_list, list):
        return []
    entries = [img for img in images_list if isinstance(img, dict)]
    entries.sort(key=lambda img: 0 if img.get("variant") == "MAIN" else 1)
    urls: list[str] = []
    for img in entries:
        u = img.get("large") or img.get("hi_res") or img.get("thumb")
        if u and u not in urls:
            urls.append(u)
        if len(urls) >= MAX_IMAGES_PER_PRODUCT:
            break
    return urls


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


def _extract_category_path(categories_str: str | None) -> str | None:
    """Breadcrumb COMPLET « A > B > C » (17.4b, D-035) — la preuve visible que
    chaque annonce est rattachée à un rangement marketplace parfait.

    Ex: "['Electronics', 'Computers', 'Laptops']" → "Electronics > Computers > Laptops".
    """
    if not categories_str or categories_str in ("[]", "null", "None"):
        return None
    try:
        cats = ast.literal_eval(categories_str)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(cats, list) or not cats:
        return None
    parts = [str(c).strip() for c in cats if c]
    return " > ".join(parts) if parts else None


def _parse_details(details_str: str | None) -> dict:
    """Parse le dict `details` stringifié (une seule fois par item)."""
    if not details_str or details_str in ("{}", "null", "None"):
        return {}
    try:
        d = ast.literal_eval(details_str)
    except (ValueError, SyntaxError):
        return {}
    return d if isinstance(d, dict) else {}


def _brand_from_details(d: dict) -> str | None:
    """Vraie marque fabricant (`Brand`, fallback `Manufacturer`).

    Plus fiable que `store` (boutique Amazon, souvent un revendeur "Amazon Renewed").
    Cf. découverte user 2026-05-21.
    """
    brand = d.get("Brand") or d.get("Manufacturer")
    return str(brand).strip() if brand else None


def _facets_from_details(d: dict) -> dict[str, str]:
    """Extrait les facettes discriminantes curées présentes (FACET_KEYS).

    Retourne {nom_canonique: valeur} pour les seules facettes présentes — base
    de la sélection Akinator par entropie côté requête.
    """
    facets: dict[str, str] = {}
    for canon, keys in FACET_KEYS.items():
        for k in keys:
            v = d.get(k)
            if v:
                facets[canon] = str(v).strip()
                break
    return facets


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
        df = pl.read_parquet(
            meta_path, columns=["parent_asin", "images", "categories", "details", "store"]
        )
        image_urls = [_extract_thumb_url(s) for s in df["images"]]
        # 17.2 (D-035) : toutes les vues pour visionneuse + VLM validateur.
        images_all_json = [
            json.dumps(urls) if (urls := _extract_all_image_urls(s)) else None for s in df["images"]
        ]
        cat_leaves = [_extract_category_leaf(s) for s in df["categories"]]
        cat_paths = [_extract_category_path(s) for s in df["categories"]]
        # Parse details UNE fois → marque + facettes discriminantes
        brands: list[str | None] = []
        facets_json: list[str | None] = []
        for det, store in zip(df["details"], df["store"], strict=False):
            d = _parse_details(det)
            brands.append(_brand_from_details(d) or (str(store).strip() if store else None))
            facets = _facets_from_details(d)
            facets_json.append(json.dumps(facets, ensure_ascii=False) if facets else None)
        sub = pl.DataFrame(
            {
                "parent_asin": df["parent_asin"],
                "image_url": image_urls,
                "images_json": images_all_json,
                "category_leaf": cat_leaves,
                "category_path": cat_paths,
                "brand": brands,
                "facets_json": facets_json,
            }
        )
        n_img = sub.filter(pl.col("image_url").is_not_null()).height
        n_cat = sub.filter(pl.col("category_leaf").is_not_null()).height
        n_brand = sub.filter(pl.col("brand").is_not_null()).height
        n_facet = sub.filter(pl.col("facets_json").is_not_null()).height
        log.info(
            "  %s : %s items (%s vignettes, %s cat, %s marques, %s avec facettes)",
            cat,
            f"{df.height:_}",
            f"{n_img:_}",
            f"{n_cat:_}",
            f"{n_brand:_}",
            f"{n_facet:_}",
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
