"""Étape 3/5 du cleaning - Normalisation textuelle title + description.

Pipeline de normalisation prudent (préserve l'information autant que
possible - le cleaning ne corrige pas, il prépare) :

1. Strip HTML résiduel : `<br>`, `<p>`, `&amp;`, `&nbsp;` etc. Polars n'a
   pas d'unescape HTML natif, on traite les cas les plus fréquents par
   regex + remplacements explicites.
2. Normalisation Unicode NFKC : décompose puis recompose en forme
   canonique (équivalence visuelle, ex : ligatures `ﬁ` → `fi`).
3. Trim whitespace (multiple spaces, leading/trailing).
4. **Pas de lowercase global** : on préserve la casse car les acronymes
   et marques (USB, Apple, Samsung) portent du signal pour la
   classification et l'identification. Le lowercase éventuel se fait
   au moment du token-matching côté TF-IDF (Cycle 3.2) ou côté encoder
   (les modèles font leur propre tokenization).

Stack
-----
polars lazy + sink_parquet streaming. Aucun .collect() lourd.

Lance ce script depuis la racine du repo :

    python -m src.data.clean.03_normalize_text

Sortie : data/processed/intermediate/03_meta_normalized.parquet
"""

from __future__ import annotations

import logging

import polars as pl

from src.config import DATA_PROCESSED_INTERMEDIATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

IN_PATH = DATA_PROCESSED_INTERMEDIATE / "02_meta_pruned.parquet"
OUT_PATH = DATA_PROCESSED_INTERMEDIATE / "03_meta_normalized.parquet"

# Colonnes textuelles à normaliser
TEXT_COLS = ("title", "description", "subtitle", "author", "store")

# Patterns regex pour HTML strip (les plus fréquents dans les meta scrappées)
HTML_TAG_PATTERN = r"<[^>]+>"
HTML_ENTITY_REPLACEMENTS = [
    ("&amp;", "&"),
    ("&lt;", "<"),
    ("&gt;", ">"),
    ("&quot;", '"'),
    ("&#39;", "'"),
    ("&apos;", "'"),
    ("&nbsp;", " "),
    ("&mdash;", "-"),
    ("&ndash;", "-"),
    ("&hellip;", "…"),
]


def _normalize_col(col_name: str) -> pl.Expr:
    """Construit l'expression polars de normalisation pour une colonne texte."""
    expr = pl.col(col_name).cast(pl.Utf8, strict=False)
    # 1. Drop HTML tags
    expr = expr.str.replace_all(HTML_TAG_PATTERN, " ")
    # 2. HTML entities
    for entity, replacement in HTML_ENTITY_REPLACEMENTS:
        expr = expr.str.replace_all(entity, replacement, literal=True)
    # 3. NFKC normalization (polars n'a pas de fonction native - on garde la
    #    string telle quelle ; la normalisation Unicode complète sera faite
    #    côté encoder qui a son propre tokenizer NFKC. Ici on reste défensif
    #    sur les espaces multiples seulement.)
    # 4. Collapse whitespace (multiple spaces → single)
    expr = expr.str.replace_all(r"\s+", " ").str.strip_chars()
    # 5. Empty string → null pour cohérence avec NaN d'origine
    expr = pl.when(expr.str.len_chars() == 0).then(None).otherwise(expr)
    return expr.alias(col_name)


def main() -> None:
    log.info("=== Étape 3/5 cleaning : normalisation textuelle ===")

    if not IN_PATH.exists():
        raise FileNotFoundError(
            f"{IN_PATH.name} introuvable. Lance d'abord les étapes précédentes."
        )

    if OUT_PATH.exists():
        log.info("→ output déjà présent (%s), skip", OUT_PATH.name)
        return

    log.info("Lecture %s…", IN_PATH.name)
    lf = pl.scan_parquet(IN_PATH)
    schema_names = lf.collect_schema().names()

    cols_to_normalize = [c for c in TEXT_COLS if c in schema_names]
    log.info("Normalisation des colonnes : %s", cols_to_normalize)

    normalized_lf = lf.with_columns([_normalize_col(c) for c in cols_to_normalize])

    log.info("Écriture %s…", OUT_PATH.name)
    normalized_lf.sink_parquet(OUT_PATH, compression="zstd", compression_level=3)

    size_gb = OUT_PATH.stat().st_size / 1_073_741_824
    log.info("→ %s écrit (%.2f GB)", OUT_PATH.name, size_gb)
    log.info("Étape 3/5 OK.")


if __name__ == "__main__":
    main()
