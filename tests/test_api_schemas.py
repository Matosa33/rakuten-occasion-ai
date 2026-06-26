"""Tests pour les Pydantic v2 schemas API (src/api/schemas.py)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    CandidateMeta,
    CategoryEnum,
    ConditionEnum,
    ConfidenceLevelEnum,
    DescribeRequest,
    HealthResponse,
    IdentifyRequest,
    PriceRequest,
    PriceResponse,
)


class TestEnums:
    def test_4_categories_d011(self):
        cats = {c.value for c in CategoryEnum}
        assert cats == {
            "Electronics",
            "Cell_Phones_and_Accessories",
            "Video_Games",
            "Tools_and_Home_Improvement",
        }

    def test_conditions(self):
        # Cycle 36 : ajout de "pour_pieces" (HS / pour pièces, cas courant occasion).
        conds = {c.value for c in ConditionEnum}
        assert conds == {"neuf", "tres_bon_etat", "bon_etat", "correct", "pour_pieces"}

    def test_4_confidence_levels(self):
        levels = {lvl.value for lvl in ConfidenceLevelEnum}
        assert levels == {"L1", "L2", "L3", "L4"}


class TestIdentifyRequest:
    def test_minimal_request(self):
        req = IdentifyRequest(image_url="https://example.com/img.jpg")
        assert req.image_url.endswith(".jpg")
        assert req.text_hint == ""
        assert req.already_observed == {}

    def test_with_observations(self):
        req = IdentifyRequest(
            image_url="data:image/png;base64,iVB...",
            text_hint="Téléphone Samsung",
            already_observed={"color": "noir"},
        )
        assert req.already_observed["color"] == "noir"


class TestPriceRequest:
    def test_minimal_with_defaults(self):
        req = PriceRequest(category="Electronics")
        assert req.condition == ConditionEnum.BON_ETAT
        assert req.age_years == 2.0
        assert req.parent_asin is None

    def test_age_years_must_be_positive(self):
        with pytest.raises(ValidationError):
            PriceRequest(category="Electronics", age_years=-1.0)

    def test_age_years_max_50(self):
        with pytest.raises(ValidationError):
            PriceRequest(category="Electronics", age_years=51.0)


class TestPriceResponse:
    def test_valid_response(self):
        resp = PriceResponse(
            suggested_price_eur=49.99,
            confidence_level="L2",
            confidence_score=0.65,
            range_low=35.0,
            range_high=65.0,
            explanation="Test",
            method="knn_median",
        )
        assert resp.confidence_level == ConfidenceLevelEnum.L2

    def test_confidence_score_must_be_in_unit_interval(self):
        with pytest.raises(ValidationError):
            PriceResponse(
                suggested_price_eur=10.0,
                confidence_level="L1",
                confidence_score=1.5,
                range_low=8.0,
                range_high=12.0,
                explanation="x",
                method="catalog_meta",
            )


class TestCandidateMeta:
    def test_score_must_be_in_unit_interval(self):
        with pytest.raises(ValidationError):
            CandidateMeta(
                parent_asin="B00X",
                title="t",
                category="Electronics",
                score=1.5,
            )

    def test_minimal(self):
        c = CandidateMeta(parent_asin="B00X", title="t", category="Electronics", score=0.85)
        assert c.brand == ""
        assert c.image_url == ""


class TestDescribeRequest:
    def test_default_condition(self):
        req = DescribeRequest(parent_asin="B00ABC")
        assert req.condition == ConditionEnum.BON_ETAT


class TestHealthResponse:
    def test_default_status_ok(self):
        h = HealthResponse()
        assert h.status == "ok"
        assert h.version == "0.1.0"
        assert h.models_loaded == {}
