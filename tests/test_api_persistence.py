"""Tests persistence SQLAlchemy + endpoints /history et /identify/stream (Cycle 9.4/9.5).

Isole la DB de test dans un fichier temporaire via DATABASE_URL pour ne pas
polluer la DB de dev. On recharge le module persistence avec la nouvelle URL.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def persistence_tmp(tmp_path, monkeypatch):
    """Persistence pointant vers une DB SQLite temporaire isolée."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import src.api.persistence as persistence

    importlib.reload(persistence)
    return persistence


class TestPersistence:
    def test_log_and_retrieve(self, persistence_tmp):
        pid = persistence_tmp.log_identification(
            query_text="iphone 13",
            status="identified",
            top1_parent_asin="B001",
            top1_category="Cell_Phones_and_Accessories",
            top1_score=0.91,
            suggested_price_eur=320.0,
            price_confidence_level="L2",
        )
        assert pid >= 1
        logs = persistence_tmp.recent_logs(limit=5)
        assert len(logs) == 1
        assert logs[0]["query_text"] == "iphone 13"
        assert logs[0]["status"] == "identified"
        assert logs[0]["top1_parent_asin"] == "B001"

    def test_recent_logs_order_desc(self, persistence_tmp):
        for i in range(3):
            persistence_tmp.log_identification(query_text=f"q{i}", status="ood")
        logs = persistence_tmp.recent_logs(limit=10)
        assert len(logs) == 3
        assert logs[0]["query_text"] == "q2"  # dernier inséré en premier

    def test_query_text_truncated_to_2000(self, persistence_tmp):
        persistence_tmp.log_identification(query_text="x" * 5000, status="ood")
        logs = persistence_tmp.recent_logs(limit=1)
        assert len(logs[0]["query_text"]) <= 2000


class TestHistoryEndpoint:
    def test_history_returns_logs(self, persistence_tmp):
        # main importe persistence comme module ; on patche sa référence
        import src.api.main as api_main

        importlib.reload(api_main)
        api_main.persistence = persistence_tmp
        persistence_tmp.log_identification(query_text="test", status="identified")

        client = TestClient(api_main.app)
        r = client.get("/history?limit=5")
        assert r.status_code == 200
        body = r.json()
        assert "logs" in body
        assert len(body["logs"]) >= 1


class TestStreamEndpoint:
    def test_stream_503_when_not_loaded(self):
        import src.api.main as api_main

        importlib.reload(api_main)
        api_main.APP_STATE["identification"] = None
        client = TestClient(api_main.app)
        r = client.post("/identify/stream", json={"image_url": "x", "text_hint": "iphone"})
        assert r.status_code == 503

    def test_stream_emits_events(self):
        import src.api.main as api_main

        importlib.reload(api_main)
        from src.api.pipeline import Candidate, IdentificationResult

        class FakeIdent:
            ready = True

            def identify(self, q, already_observed=None):
                return IdentificationResult(
                    status="identified",
                    candidates=[Candidate("B001", "iPhone", "Apple", "Electronics", 0.9)],
                    next_observation=None,
                    explanation="ok",
                )

        api_main.APP_STATE["identification"] = FakeIdent()
        client = TestClient(api_main.app)
        with client.stream(
            "POST", "/identify/stream", json={"image_url": "x", "text_hint": "iphone"}
        ) as r:
            assert r.status_code == 200
            content = "".join(chunk for chunk in r.iter_text())
        assert "event: step" in content
        assert "event: result" in content
        assert "event: done" in content
        assert "B001" in content
