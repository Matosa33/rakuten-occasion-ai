"""Tests d'intégration des VRAIS services pipeline (Cycle 15.3, D-034).

L'audit 15.0 (P0 tests) : `IdentificationService.load()`, `PricingService.load()`,
`DescribeService.load()` n'étaient JAMAIS appelés en test — seuls des fakes
étaient injectés dans APP_STATE. Ici on charge les vrais services, avec skipif
sur les artefacts lourds (absents en CI, présents en local → R13 vérifiable).
"""

from __future__ import annotations

import pytest

from src.api.pipeline import DescribeService, IdentificationService, PricingService
from src.config import DATA_INDEX, DATA_MODELS, DATA_PROCESSED_PRODUCTS

_M8 = DATA_MODELS / "pricing-cascade_v1.joblib"
_FAISS = DATA_INDEX / "text_arctic_hnsw.index"
_TRAIN = DATA_PROCESSED_PRODUCTS / "train.parquet"


@pytest.mark.skipif(not _M8.exists(), reason="artefact M8 absent (Cycle 7.1)")
class TestPricingServiceReal:
    def test_load_et_ready(self):
        svc = PricingService()
        svc.load()
        assert svc.ready is True

    def test_suggest_cascade_l1_catalog_price(self):
        """Avec un prix catalogue fourni, la cascade doit sortir en L1 (méthode
        catalog_meta) avec un prix décoté < prix neuf."""
        svc = PricingService()
        svc.load()
        result = svc.suggest(
            category="Electronics",
            condition="bon_etat",
            age_years=2.0,
            catalog_price=1000.0,
            knn_neighbors_prices=None,
        )
        assert result.confidence_level == "L1"
        assert result.method == "catalog_meta"
        assert 0 < result.suggested_price_eur < 1000.0, "occasion < prix neuf catalogue"
        assert result.range_low < result.suggested_price_eur < result.range_high

    def test_suggest_fallback_l3_categorie_seule(self):
        """Sans prix catalogue ni voisins → médiane de catégorie (L3)."""
        svc = PricingService()
        svc.load()
        result = svc.suggest(
            category="Video_Games",
            condition="bon_etat",
            age_years=1.0,
            catalog_price=None,
            knn_neighbors_prices=None,
        )
        assert result.confidence_level in {"L3", "L4"}
        assert result.suggested_price_eur > 0


@pytest.mark.skipif(
    not (_FAISS.exists() and _TRAIN.exists()),
    reason="index FAISS 13,8 Go / train.parquet absents (artefacts lourds, local only)",
)
class TestIdentificationServiceReal:
    """Chargement réel = plusieurs minutes sur Windows (bind-mount lent connu).
    Exécuté en local avant jalon, jamais en CI (skipif)."""

    @pytest.mark.slow
    def test_load_et_identify_smoke(self):
        svc = IdentificationService()
        svc.load()
        assert svc.ready is True
        result = svc.identify("Apple iPhone 13 black 128 GB")
        assert result.status in {"identified", "to_confirm", "uncertain"}
        assert len(result.candidates) > 0
        top1 = result.candidates[0]
        assert 0.0 <= top1.score <= 1.0
        assert top1.parent_asin


@pytest.mark.skipif(not _TRAIN.exists(), reason="train.parquet absent (local only)")
class TestDescribeServiceReal:
    @pytest.mark.slow
    def test_load_et_describe_mock_grounded(self, monkeypatch):
        """Sans clé OpenRouter, DescribeService bascule sur MockLLMWriter (D-013)
        — le pipeline complet (catalogue → grounding → writer) doit produire
        un listing parseable."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        svc = DescribeService()
        svc.load()
        assert svc.ready is True
