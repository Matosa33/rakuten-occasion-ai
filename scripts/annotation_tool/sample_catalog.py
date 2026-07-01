"""Échantillon DIVERSIFIÉ du catalogue → guide de scraping pour le dataset photos d'éval.

But : t'orienter sur QUELS produits scraper pour couvrir la diversité réelle de notre BDD
(les 4 macro-catégories × un maximum de catégories FINES distinctes), pas seulement ce qu'on
a sous la main. Échantillonne ~100 produits, **stratifié par macro** et **une seule entrée par
catégorie feuille** (maximise la couverture fine), de façon reproductible (seed).

Sortie : `reports/05_retrieval/catalog_sample_100.{md,csv}` (titres = exemples Amazon ; tu
cherches l'équivalent réel sur leboncoin pour photographier la même CATÉGORIE).

Lancer :

    .venv/Scripts/python.exe scripts/annotation_tool/sample_catalog.py [--n 100]
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import CATEGORIES, DATA_PROCESSED_PRODUCTS, REPO_ROOT  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MACROS = list(CATEGORIES)  # source de vérité : valeurs réelles de `_source_category`
OUT_DIR = REPO_ROOT / "reports" / "05_retrieval"
SEED = 42


def build(n_total: int) -> pl.DataFrame:
    tr = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "train.parquet",
        columns=["parent_asin", "_source_category", "title", "price_num"],
    )
    lk = pl.read_parquet(
        DATA_PROCESSED_PRODUCTS / "product_lookup.parquet",
        columns=["parent_asin", "category_leaf", "category_path", "brand"],
    )
    df = tr.join(lk, on="parent_asin", how="inner").filter(pl.col("category_leaf").is_not_null())

    per_macro = max(1, n_total // len(MACROS))
    picks: list[pl.DataFrame] = []
    for macro in MACROS:
        sub = df.filter(pl.col("_source_category") == macro)
        if sub.height == 0:
            log.warning("macro %s absente du train.", macro)
            continue
        # shuffle → 1 produit (aléatoire) par catégorie feuille → on en garde per_macro
        shuffled = sub.sample(fraction=1.0, shuffle=True, seed=SEED)
        one_per_leaf = shuffled.unique(subset=["category_leaf"], keep="first")
        take = min(per_macro, one_per_leaf.height)
        picks.append(one_per_leaf.sample(n=take, seed=SEED))
        log.info("%s : %d catégories fines distinctes échantillonnées.", macro, take)

    return pl.concat(picks).sort(["_source_category", "category_leaf"])


def write(df: pl.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # CSV exploitable
    csv_path = OUT_DIR / "catalog_sample_100.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["macro", "category_leaf", "brand", "title", "price_usd", "parent_asin"])
        for r in df.iter_rows(named=True):
            w.writerow(
                [
                    r["_source_category"],
                    r["category_leaf"],
                    r.get("brand") or "",
                    (r["title"] or "")[:90],
                    r.get("price_num") or "",
                    r["parent_asin"],
                ]
            )
    # MD lisible
    lines = [
        f"# Catalogue - échantillon diversifié ({df.height} produits)",
        "",
        "> Guide de scraping : couvre les 4 macro-catégories × un max de **catégories fines**",
        "> distinctes. Les titres sont des exemples Amazon → trouve l'équivalent réel sur",
        "> leboncoin (même **catégorie**) pour photographier. Vise ≥2 photos/produit.",
        "",
        "| Macro | Catégorie fine | Marque | Exemple de produit |",
        "|---|---|---|---|",
    ]
    for r in df.iter_rows(named=True):
        title = (r["title"] or "").replace("|", "/")[:70]
        brand = (r.get("brand") or "").replace("|", "/")[:20]
        lines.append(f"| {r['_source_category']} | {r['category_leaf']} | {brand} | {title} |")
    (OUT_DIR / "catalog_sample_100.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Écrit : %s (+ .csv)", OUT_DIR / "catalog_sample_100.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="nombre total de produits (défaut 100)")
    args = ap.parse_args()
    df = build(args.n)
    write(df)
    log.info("Total : %d produits sur %d macros.", df.height, df["_source_category"].n_unique())


if __name__ == "__main__":
    main()
