"""Audit pipeline — Phase P02, sous-todo 1.1.

4 scripts numérotés (R1) à exécuter dans l'ordre :

    01_load_full.py              télécharge les catégories définies par D-008
    02_audit_qualite.py          NaN, types, doublons, longueurs textes
    03_audit_distributions.py    catégories, prix, ratings, temporel
    04_audit_biais_leakage.py    biais et fuites potentielles

Stack lourd : polars (lazy/streaming) + huggingface_hub (download avec resume).
Voir BRAIN/decisions.md D-006 (polars), D-007 (full vs sample, superseded by D-008),
D-008 (périmètre = 15 cat evergreen-occasion choisies par méta-first).

La constante `CATEGORIES` ci-dessous est la **source unique de vérité** du périmètre,
importée par 01..04. Pour changer le périmètre, éditer ici uniquement.

Chaque script lit/écrit dans data/raw/full/ et reports/figures/, et
produit une section du rapport reports/audit_v1_amazon_reviews_2023.md.
"""

# Périmètre D-008 — 15 catégories evergreen-occasion (Tier 1 + Books physiques).
# Voir BRAIN/decisions.md D-008 pour la justification critère par critère.
# Volume mesuré : ~227 GB JSONL → ~57 GB parquet zstd, ~285 M reviews attendus.
CATEGORIES: tuple[str, ...] = (
    "Clothing_Shoes_and_Jewelry",
    "Home_and_Kitchen",
    "Books",
    "Electronics",
    "Tools_and_Home_Improvement",
    "Automotive",
    "Sports_and_Outdoors",
    "Cell_Phones_and_Accessories",
    "Movies_and_TV",
    "Toys_and_Games",
    "CDs_and_Vinyl",
    "Baby_Products",
    "Video_Games",
    "Musical_Instruments",
    "Appliances",
)


# Colonnes à structures imbriquées (List[Struct], List[String], Struct) à droper
# avant concat. Raison : selon que le parquet a été écrit par polars natif ou par
# le fallback pandas chunked (cf. 01_load_full.py), ces colonnes ont un dtype
# différent (List[Struct] vs String stringifié). Le concat diagonal_relaxed essaie
# de les unifier en String et le cast List→String échoue. On les drop puisqu'aucun
# script d'audit n'en a besoin (audit textuel = title/text/description seulement).
COMPLEX_COLS_TO_DROP: tuple[str, ...] = (
    "images",
    "videos",
    "features",
    "categories",
    "details",
    "bought_together",
)


def scan_concat(dir_path, drop_complex: bool = True):
    """Concat lazy des N parquets d'une famille (reviews ou meta) avec _source_category.

    `drop_complex=True` (défaut) : retire les colonnes List/Struct connues
    incompatibles avec le concat diagonal_relaxed (cf. COMPLEX_COLS_TO_DROP).
    """
    import polars as pl

    paths = [dir_path / f"{cat}.parquet" for cat in CATEGORIES]
    parts = []
    for p, cat in zip(paths, CATEGORIES, strict=True):
        lf = pl.scan_parquet(p)
        if drop_complex:
            present = [c for c in COMPLEX_COLS_TO_DROP if c in lf.collect_schema().names()]
            if present:
                lf = lf.drop(present)
        parts.append(lf.with_columns(pl.lit(cat).alias("_source_category")))
    return pl.concat(parts, how="diagonal_relaxed")
