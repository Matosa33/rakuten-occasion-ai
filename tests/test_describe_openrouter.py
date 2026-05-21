"""Tests /describe + client OpenRouter (Cycle 9.3b).

Sans OPENROUTER_API_KEY : le client lève OpenRouterError, le DescribeService
bascule sur MockLLMWriter (D-013). On teste les deux branches.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from src.config import DATA_PROCESSED_PRODUCTS
from src.llm import openrouter_client


class TestOpenRouterClient:
    def test_is_available_false_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert openrouter_client.is_available() is False

    def test_chat_completion_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(openrouter_client.OpenRouterError, match="OPENROUTER_API_KEY"):
            openrouter_client.chat_completion("hello")

    def test_is_available_true_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert openrouter_client.is_available() is True


class TestDescribeEndpoint:
    def test_503_when_not_loaded(self):
        import src.api.main as api_main

        importlib.reload(api_main)
        api_main.APP_STATE["describe"] = None
        client = TestClient(api_main.app)
        r = client.post("/describe", json={"parent_asin": "B001"})
        assert r.status_code == 503

    @pytest.mark.skipif(
        not (DATA_PROCESSED_PRODUCTS / "train.parquet").exists(),
        reason="train.parquet absent",
    )
    def test_describe_mock_path_real_catalog(self, monkeypatch):
        """Sans clé → MockLLMWriter, génère un listing parseable sur un vrai produit."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        import polars as pl

        from src.api.pipeline import DescribeService

        # Récupère un parent_asin réel du catalogue
        sample = pl.read_parquet(
            DATA_PROCESSED_PRODUCTS / "train.parquet", columns=["parent_asin"]
        ).head(1)
        real_asin = sample["parent_asin"][0]

        svc = DescribeService()
        svc.load()
        result = svc.describe(real_asin, condition="bon état")
        assert result.parse_ok
        assert len(result.title) > 0
        assert len(result.description) > 0

    @pytest.mark.skipif(
        not (DATA_PROCESSED_PRODUCTS / "train.parquet").exists(),
        reason="train.parquet absent",
    )
    def test_describe_404_unknown_asin(self):
        from src.api.pipeline import DescribeService

        svc = DescribeService()
        svc.load()
        with pytest.raises(ValueError, match="introuvable"):
            svc.describe("B_DOES_NOT_EXIST_999")
