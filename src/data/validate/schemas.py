"""Sous-todo 1.4 — Schemas Pandera pour les sorties du pipeline 1.2.

Ces schemas servent de **contrat formel** entre les sous-todos. Toute
modification du pipeline cleaning/split (sous-todo 1.2) qui casse un de
ces schemas doit lever une décision explicite (mise à jour du schema
+ révision des consommateurs aval).

Schemas définis
---------------
- ProductSchema       : `data/processed/products/{train,val,test}.parquet`
- ReviewIndexSchema   : `data/processed/reviews_index/{train,val,test}.parquet`

Pourquoi Pandera (vs assertions ad hoc)
---------------------------------------
- **Déclaratif** : un schema = un objet Python lisible vs N assertions éparpillées.
- **Reusable** : même schema en CI (sample) et en batch (full).
- **Erreurs lisibles** : Pandera dit exactement quelle colonne, quelle ligne,
  quelle règle est cassée — pas un AssertionError opaque.
- **Validation lazy avec polars natif** : `schema.validate(lazy_frame)` est
  cohérent avec le moteur d'audit (cf. ADR D-006).

Stratégie de validation
-----------------------
- En CI : valide un sample N=10 000 lignes (rapide, suffit pour détecter
  une régression de schéma).
- En batch (sous-todo 1.4 RUN) : valide le full (~26 M items + ~348 M reviews)
  pour confirmer qu'aucune donnée ne viole les contrats.

Utilisation
-----------
    from src.data.validate.pandera_schemas import ProductSchema, ReviewIndexSchema
    import polars as pl

    df = pl.read_parquet("data/processed/products/train.parquet")
    ProductSchema.validate(df, lazy=True)  # raises pa.errors.SchemaError si KO
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl
from pandera.polars import Column, DataFrameSchema

# ─────────────────────────────────────────────────────────────────────────────
# Schema product-level (data/processed/products/{train,val,test}.parquet)
# ─────────────────────────────────────────────────────────────────────────────

ProductSchema = DataFrameSchema(
    columns={
        # ── Clé primaire et provenance ─────────────────────────────────────
        "parent_asin": Column(
            str,
            nullable=False,
            unique=False,  # unique par split, pas global
            description="Identifiant produit Amazon canonique (regex B[0-9A-Z]{9} typique)",
        ),
        "_source_category": Column(
            str,
            nullable=False,
            description="Catégorie source (15 valeurs D-008)",
            checks=pa.Check.isin(
                [
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
                ]
            ),
        ),
        # ── Champs meta originaux ──────────────────────────────────────────
        "main_category": Column(str, nullable=True),
        "title": Column(str, nullable=True, description="Titre produit (cap 1024 chars)"),
        "average_rating": Column(str, nullable=True, description="Stringifié dans le full"),
        "rating_number": Column(str, nullable=True),
        "description": Column(str, nullable=True, description="Cap 8192 chars"),
        "price": Column(str, nullable=True, description="String brut original (parser séparément)"),
        "store": Column(str, nullable=True),
        "subtitle": Column(str, nullable=True, description="Vidé hors text-rich cats"),
        "author": Column(str, nullable=True, description="Vidé hors text-rich cats"),
        # ── Agrégats reviews (étape 01_join) ───────────────────────────────
        # Types polars natifs explicites pour matcher exactement la sortie
        # du group_by (UInt32 pour pl.len() / n_unique, Float64 pour mean/std,
        # Int32 pour dt.year()).
        "n_reviews": Column(
            pl.UInt32,
            nullable=True,
            checks=pa.Check.greater_than_or_equal_to(0),
        ),
        "mean_rating": Column(pl.Float64, nullable=True, checks=pa.Check.in_range(0, 5)),
        "std_rating": Column(
            pl.Float64, nullable=True, checks=pa.Check.greater_than_or_equal_to(0)
        ),
        "pct_verified": Column(pl.Float64, nullable=True, checks=pa.Check.in_range(0, 1)),
        "pct_5stars": Column(pl.Float64, nullable=True, checks=pa.Check.in_range(0, 1)),
        "pct_1stars": Column(pl.Float64, nullable=True, checks=pa.Check.in_range(0, 1)),
        "year_first_review": Column(pl.Int32, nullable=True, checks=pa.Check.in_range(1996, 2023)),
        "year_last_review": Column(pl.Int32, nullable=True, checks=pa.Check.in_range(1996, 2023)),
        "n_unique_users": Column(
            pl.UInt32, nullable=True, checks=pa.Check.greater_than_or_equal_to(0)
        ),
        "mean_helpful_vote": Column(
            pl.Float64, nullable=True, checks=pa.Check.greater_than_or_equal_to(0)
        ),
        # ── Flags qualité (étape 04_cap) ───────────────────────────────────
        "description_too_short": Column(pl.Boolean, nullable=False),
        "title_too_short": Column(pl.Boolean, nullable=False),
        "has_description": Column(pl.Boolean, nullable=False),
        "has_title": Column(pl.Boolean, nullable=False),
        # ── Features dérivées (étape 05_feature_engineering) ───────────────
        "price_num": Column(
            pl.Float64,
            nullable=True,  # null pour les ~59 % d'items sans prix valide
            checks=pa.Check.greater_than(0),
        ),
        "log_price": Column(pl.Float64, nullable=True, checks=pa.Check.greater_than(0)),
        "price_band": Column(
            pl.Utf8,
            nullable=True,
            checks=pa.Check.isin(["low", "mid", "high"]),
        ),
        "length_title": Column(pl.UInt32, nullable=False, checks=pa.Check.in_range(0, 1024)),
        "length_description": Column(pl.UInt32, nullable=False, checks=pa.Check.in_range(0, 8192)),
        "n_reviews_log": Column(
            pl.Float64, nullable=True, checks=pa.Check.greater_than_or_equal_to(0)
        ),
        "years_active": Column(
            pl.Int32, nullable=True, checks=pa.Check.greater_than_or_equal_to(1)
        ),
        "recency_year": Column(pl.Int32, nullable=True, checks=pa.Check.in_range(0, 27)),
    },
    strict=False,  # Tolère des colonnes supplémentaires (futures features)
    name="ProductSchema",
)


# ─────────────────────────────────────────────────────────────────────────────
# Schema reviews_index (data/processed/reviews_index/{train,val,test}.parquet)
# ─────────────────────────────────────────────────────────────────────────────

ReviewIndexSchema = DataFrameSchema(
    columns={
        "parent_asin": Column(str, nullable=False),
        "asin": Column(str, nullable=True, description="Variante ASIN (peut différer du parent)"),
        "user_id": Column(str, nullable=True),
        "timestamp": Column(
            str,
            nullable=True,
            description="Format mixte Int64 ms / String ISO selon source écriture",
        ),
        "_source_category": Column(
            str,
            nullable=False,
            checks=pa.Check.isin(
                [
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
                ]
            ),
        ),
        "_split": Column(
            str,
            nullable=False,
            checks=pa.Check.isin(["train", "val", "test"]),
        ),
    },
    strict=False,
    name="ReviewIndexSchema",
)
