"""Cycle 10.x — Lookup léger parent_asin → URL vignette (pour l'UI candidats).

La colonne `images` (List[Struct] stringifiée) a été droppée du processed au
cleaning (D-006). Mais l'UI veut afficher une vignette par candidat. Plutôt
que de re-joindre la raw meta lourde à chaque requête, on pré-construit un
**lookup minimal** `[parent_asin, image_url]` pour les 4 cat D-011, chargé en
RAM par l'IdentificationService (Cycle 9).

On préfère `thumb > large > hi_res` (vignette = petite image, charge vite côté
navigateur). URLs CDN publiques Amazon (affichage, pas de download serveur).

Sortie : `data/processed/products/images_lookup.parquet` (~4.5M lignes, 2 cols).

Lance :

    python -m src.data.clean.06_build_images_lookup
"""

from __future__ import annotations

import ast
import logging

import polars as pl

from src.config import CATEGORIES, DATA_PROCESSED_PRODUCTS, DATA_RAW_FULL_META

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUT_LOOKUP = DATA_PROCESSED_PRODUCTS / "images_lookup.parquet"


def _extract_thumb_url(images_str: str | None) -> str | None:
    """Extrait l'URL vignette de l'entrée MAIN (thumb > large > hi_res)."""
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
    # Vignette : on privilégie la plus petite (thumb) pour un chargement rapide.
    return main.get("thumb") or main.get("large") or main.get("hi_res")


def main() -> None:
    log.info("=== Lookup images parent_asin → URL vignette (4 cat D-011) ===")
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
        df = pl.read_parquet(meta_path, columns=["parent_asin", "images"])
        urls = [_extract_thumb_url(s) for s in df["images"]]
        sub = pl.DataFrame({"parent_asin": df["parent_asin"], "image_url": urls}).filter(
            pl.col("image_url").is_not_null()
        )
        log.info("  %s : %s/%s items avec vignette", cat, f"{sub.height:_}", f"{df.height:_}")
        frames.append(sub)

    if not frames:
        log.error("Aucune meta lue. Abandon.")
        return

    lookup = pl.concat(frames).unique(subset=["parent_asin"], keep="first")
    lookup.write_parquet(OUT_LOOKUP)
    log.info("→ %s : %s lignes", OUT_LOOKUP.name, f"{lookup.height:_}")


if __name__ == "__main__":
    main()
