"""Tests Pandera schemas (sous-todo 1.4) — vérifications structurelles + sample.

Stratégie hybride :
- Tests sans données (rapides, toujours actifs en CI) :
    * Les schemas s'importent
    * Ils définissent les bonnes colonnes
    * Les checks de range sont cohérents
- Tests avec données (skipif si parquets absents) :
    * Sample 1k de chaque split products → ProductSchema
    * Sample 1k de chaque split reviews_index → ReviewIndexSchema
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_DIR = REPO_ROOT / "data" / "processed" / "products"
REVIEWS_INDEX_DIR = REPO_ROOT / "data" / "processed" / "reviews_index"


def _products_available() -> bool:
    return all((PRODUCTS_DIR / f"{s}.parquet").exists() for s in ("train", "val", "test"))


def _reviews_index_available() -> bool:
    return all((REVIEWS_INDEX_DIR / f"{s}.parquet").exists() for s in ("train", "val", "test"))


# ─── Tests structurels (toujours actifs) ──────────────────────────────────


def test_schemas_import():
    """Les schemas Pandera s'importent sans erreur (deps installées)."""
    from src.data.validate.schemas import ProductSchema, ReviewIndexSchema

    assert ProductSchema.name == "ProductSchema"
    assert ReviewIndexSchema.name == "ReviewIndexSchema"


def test_product_schema_has_critical_cols():
    """Le ProductSchema doit définir les colonnes critiques pour M1-M8."""
    from src.data.validate.schemas import ProductSchema

    expected_critical = {
        "parent_asin",
        "_source_category",
        "title",
        "description",
        "price_num",
        "log_price",
        "n_reviews",
        "mean_rating",
        "length_title",
        "length_description",
    }
    actual = set(ProductSchema.columns.keys())
    missing = expected_critical - actual
    assert not missing, f"Colonnes critiques manquantes du ProductSchema : {missing}"


def test_review_index_schema_has_split_col():
    """Le ReviewIndexSchema doit avoir _split (clé du partitionnement train/val/test)."""
    from src.data.validate.schemas import ReviewIndexSchema

    assert "_split" in ReviewIndexSchema.columns
    # _split doit avoir un check isin(train, val, test)
    split_col = ReviewIndexSchema.columns["_split"]
    assert split_col.checks, "_split doit avoir un check isin"


# ─── Tests avec données (sample 1k, rapides) ──────────────────────────────


@pytest.mark.skipif(not _products_available(), reason="data/processed/products/ vide")
@pytest.mark.parametrize("split_name", ["train", "val", "test"])
def test_product_schema_validates_sample(split_name: str):
    """Sample 1k de products/{split}.parquet doit valider ProductSchema."""
    import polars as pl

    from src.data.validate.schemas import ProductSchema

    df = pl.read_parquet(PRODUCTS_DIR / f"{split_name}.parquet").head(1000)
    # Pandera lèvera SchemaError si KO ; sinon retourne le df validé
    ProductSchema.validate(df, lazy=True)


@pytest.mark.skipif(not _reviews_index_available(), reason="data/processed/reviews_index/ vide")
@pytest.mark.parametrize("split_name", ["train", "val", "test"])
def test_review_index_schema_validates_sample(split_name: str):
    """Sample 1k de reviews_index/{split}.parquet doit valider ReviewIndexSchema."""
    import polars as pl

    from src.data.validate.schemas import ReviewIndexSchema

    df = pl.read_parquet(REVIEWS_INDEX_DIR / f"{split_name}.parquet").head(1000)
    ReviewIndexSchema.validate(df, lazy=True)
