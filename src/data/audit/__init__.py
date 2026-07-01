"""Audit pipeline - Phase P02, sous-todo 1.1.

4 scripts numérotés (R1) à exécuter dans l'ordre :

    01_load_full.py              télécharge les catégories définies par D-008
    02_audit_qualite.py          NaN, types, doublons, longueurs textes
    03_audit_distributions.py    catégories, prix, ratings, temporel
    04_audit_biais_leakage.py    biais et fuites potentielles

Stack lourd : polars (lazy/streaming) + huggingface_hub (download avec resume).
Voir ADR D-006 (polars), D-007 (full vs sample, superseded by D-008),
D-008 (périmètre = 15 cat evergreen-occasion choisies par méta-first).

La constante `CATEGORIES` ci-dessous est la **source unique de vérité** du périmètre,
importée par 01..04 et re-exportée depuis `src/config.py`. Pour changer le
périmètre, éditer ici uniquement.

Chaque script lit dans `data/raw/full/{reviews,meta}/` et écrit dans
`reports/01_audit/` (cf. `src/config.py` pour les chemins centralisés).
"""

# Périmètre actif D-011 - 4 catégories MVP focused (high-tech + outils).
# Voir ADR D-011 (supersede partiel D-008).
# Volume mesuré : ~4,5 M items meta + ~96 M reviews (~17 % du périmètre D-008).
# Justification : focus sur cat où la vision est cruciale et le marché occasion
# avéré, pour rester tractable sur ressources MVP (vision SigLIP ~3-4h
# total faisable, FAISS ~9 GB RAM confortable).
#
# Les 11 cat exclues du périmètre actif (Clothing, Home, Books, Automotive,
# Sports, Movies, Toys, CDs, Baby, Musical_Instruments, Appliances) restent
# téléchargées dans `data/raw/full/` (non supprimées) et peuvent être
# réintégrées en éditant ce tuple si décision D-XXX ultérieure.
CATEGORIES: tuple[str, ...] = (
    "Electronics",
    "Cell_Phones_and_Accessories",
    "Video_Games",
    "Tools_and_Home_Improvement",
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
