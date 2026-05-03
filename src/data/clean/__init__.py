"""Cleaning pipeline — Phase P02, sous-todo 1.2.

5 scripts numérotés (R1) à exécuter dans l'ordre :

    01_join_meta_with_review_aggregates.py
        Pour chaque produit (parent_asin), agréger des features depuis ses
        reviews (n_reviews, mean_rating, std_rating, pct_verified,
        pct_positive, pct_negative, year_first, year_last, n_unique_users).
        Left join sur meta → meta enrichi product-level.
        Sortie : data/processed/intermediate/01_meta_enriched.parquet

    02_drop_sparse_columns.py
        Drop subtitle (~85 % NaN) et author (~89 % NaN) sauf sous-périmètre
        Books où ces champs sont denses (NaN < 50 %). Décision par catégorie.
        Sortie : data/processed/intermediate/02_meta_pruned.parquet

    03_normalize_text.py
        Normalise title + description : strip HTML résiduel, normalisation
        Unicode NFKC, lowercase prudent (uniquement la première lettre des
        mots non-acronymes), trim whitespace.
        Sortie : data/processed/intermediate/03_meta_normalized.parquet

    04_cap_text_lengths.py
        Cap description à 8192 caractères (max audit mesuré 1,48 M chars).
        Flag description_too_short pour les descriptions < 5 chars (45 %
        des items au full).
        Sortie : data/processed/intermediate/04_meta_capped.parquet

    05_feature_engineering.py
        Parser price (regex [^\\d.]), parser timestamps coalesce, dériver
        log_price (log1p), price_band (low/mid/high), age_in_years,
        length_title, length_description, has_description.
        Sortie : data/processed/intermediate/05_meta_features.parquet

Voir BRAIN/decisions.md D-008 (périmètre) + D-009 (archi RAG-grounded).

Stack : polars lazy + streaming engine (cf. ADR D-006). Tous les scripts
utilisent `engine="streaming"` au .collect() pour tenir les volumes
(348 M reviews + 26 M items) sans saturer la RAM.
"""
