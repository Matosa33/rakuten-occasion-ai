"""Tests endpoints API + services pipeline (Cycle 9.1 RUN).

On évite de déclencher le lifespan (chargement FAISS 13 GB) : TestClient
sans context manager → APP_STATE reste vide, on l'injecte manuellement.
PricingService est testé en vrai (M8 = config légère 537 bytes).
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.pipeline import (
    Candidate,
    IdentificationResult,
    PricingService,
)
from src.auth.jwt_utils import create_access_token
from src.config import DATA_MODELS

client = TestClient(api_main.app)

# Bearer JWT valide pour tous les endpoints protégés (Cycle 15.1, D-032).
# /health reste public donc ne reçoit pas ces headers.
AUTH = {"Authorization": f"Bearer {create_access_token(subject='demo')}"}


@pytest.fixture(autouse=True)
def _clear_state():
    """Reset APP_STATE avant chaque test."""
    api_main.APP_STATE["identification"] = None
    api_main.APP_STATE["pricing"] = None
    yield
    api_main.APP_STATE["identification"] = None
    api_main.APP_STATE["pricing"] = None


class TestHealth:
    def test_health_ok_when_nothing_loaded(self):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["models_loaded"]["identification"] is False
        assert body["models_loaded"]["pricing"] is False


class TestIdentify:
    def test_503_when_service_not_loaded(self):
        r = client.post("/identify", headers=AUTH, json={"image_url": "x", "text_hint": "iPhone"})
        assert r.status_code == 503

    def test_422_on_empty_text_hint(self):
        # Inject un faux service prêt
        class FakeIdent:
            ready = True

            def identify(self, q, already_observed=None):  # pragma: no cover
                raise AssertionError("ne doit pas être appelé sur texte vide")

        api_main.APP_STATE["identification"] = FakeIdent()
        r = client.post("/identify", headers=AUTH, json={"image_url": "x", "text_hint": "   "})
        assert r.status_code == 422

    def test_identified_path(self):
        class FakeIdent:
            ready = True

            def identify(self, q, already_observed=None):
                return IdentificationResult(
                    status="identified",
                    candidates=[
                        Candidate(
                            "B001", "iPhone 14", "Apple", "Cell_Phones_and_Accessories", 0.92
                        ),
                        Candidate(
                            "B002", "iPhone 13", "Apple", "Cell_Phones_and_Accessories", 0.71
                        ),
                    ],
                    next_observation=None,
                    explanation="Top-1 confiant.",
                )

        api_main.APP_STATE["identification"] = FakeIdent()
        r = client.post(
            "/identify", headers=AUTH, json={"image_url": "x", "text_hint": "iPhone 14 noir"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "identified"
        assert len(body["top_candidates"]) == 2
        assert body["top_candidates"][0]["parent_asin"] == "B001"
        assert body["next_observation"] is None

    def test_ambiguous_path_returns_observation(self):
        _akinator = importlib.import_module("src.retrieval.04_akinator_backend")
        obs = _akinator.ObservationRequest(
            attribute="title",
            observation_type="back_view",
            instruction="Photographiez le dos",
            candidates_count=2,
            discriminative_score=0.8,
        )

        class FakeIdent:
            ready = True

            def identify(self, q, already_observed=None):
                # Variantes proches → observation Akinator présente, statut par tier (to_confirm)
                return IdentificationResult(
                    status="to_confirm",
                    candidates=[
                        Candidate("B001", "T1", "S1", "Electronics", 0.55),
                        Candidate("B002", "T2", "S2", "Electronics", 0.53),
                    ],
                    next_observation=obs,
                    explanation="Variantes proches.",
                )

        api_main.APP_STATE["identification"] = FakeIdent()
        r = client.post("/identify", headers=AUTH, json={"image_url": "x", "text_hint": "appareil"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "to_confirm"
        assert body["next_observation"]["observation_type"] == "back_view"


class TestPrice:
    def test_503_when_pricing_not_loaded(self):
        r = client.post("/price", headers=AUTH, json={"category": "Electronics"})
        assert r.status_code == 503

    @pytest.mark.skipif(
        not (DATA_MODELS / "m8_pricing_v1.joblib").exists(),
        reason="M8 pricing artifact absent (lance Cycle 7.1)",
    )
    def test_price_real_m8(self):
        pricing = PricingService()
        pricing.load()
        api_main.APP_STATE["pricing"] = pricing
        r = client.post(
            "/price",
            headers=AUTH,
            json={"category": "Electronics", "condition": "bon_etat", "age_years": 2.0},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["confidence_level"] in {"L1", "L2", "L3", "L4"}
        assert body["suggested_price_eur"] >= 0.0
        assert "explanation" in body


class TestDescribe:
    def test_describe_503_when_not_loaded(self):
        # /describe est câblé (9.3b) → 503 quand le service n'est pas chargé
        r = client.post("/describe", headers=AUTH, json={"parent_asin": "B001"})
        assert r.status_code == 503


class TestPricingService:
    @pytest.mark.skipif(
        not (DATA_MODELS / "m8_pricing_v1.joblib").exists(),
        reason="M8 pricing artifact absent",
    )
    def test_suggest_uses_category_median(self):
        pricing = PricingService()
        pricing.load()
        result = pricing.suggest(category="Electronics", condition="bon_etat", age_years=2.0)
        # Sans catalog_price ni knn → L3 (cat médiane) ou L4 si médiane absente
        assert result.confidence_level in {"L3", "L4"}
