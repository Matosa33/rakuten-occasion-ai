"""Tests du logger structlog central + middleware request_id (C14.1, D-029)."""

from __future__ import annotations

import json
import logging
import os

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Force le format JSON dans les tests (pas TTY).
os.environ["LOG_FORMAT"] = "json"


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Reset structlog config + context entre tests pour éviter les fuites."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    # Force la reconfig au prochain get_logger.
    from src.observability import logging as obs_log

    obs_log._CONFIGURED = False
    yield
    structlog.contextvars.clear_contextvars()


def test_get_logger_emit_json_parseable(capsys):
    """Logger central émet du JSON valide sur stdout avec niveau + timestamp."""
    from src.observability.logging import get_logger

    log = get_logger("test")
    log.info("event-test", model="m5", f1=0.95)

    captured = capsys.readouterr().out.strip()
    assert captured, "logger doit écrire sur stdout"
    data = json.loads(captured)
    assert data["event"] == "event-test"
    assert data["model"] == "m5"
    assert data["f1"] == 0.95
    assert data["level"] == "info"
    assert "timestamp" in data


def test_bind_request_id_propage_dans_les_logs(capsys):
    """`bind_request_id` injecte la valeur dans tout log émis après le bind."""
    from src.observability.logging import bind_request_id, clear_request_context, get_logger

    log = get_logger("test")
    bind_request_id("abc123")
    log.info("after-bind")
    out_with = capsys.readouterr().out.strip()

    clear_request_context()
    log.info("after-clear")
    out_without = capsys.readouterr().out.strip()

    assert json.loads(out_with)["request_id"] == "abc123"
    assert "request_id" not in json.loads(out_without)


def test_middleware_genere_request_id_et_le_renvoie_en_header():
    """Le middleware génère un request_id si absent, le renvoie dans la réponse."""
    from src.api.middleware import REQUEST_ID_HEADER, request_id_middleware

    app = FastAPI()
    app.middleware("http")(request_id_middleware)

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/ping")
    assert r.status_code == 200
    req_id = r.headers.get(REQUEST_ID_HEADER)
    assert req_id and len(req_id) >= 8, "header X-Request-ID attendu en réponse"


def test_middleware_propage_request_id_entrant_du_client():
    """Si le client envoie X-Request-ID, le middleware le réutilise (traçabilité E2E)."""
    from src.api.middleware import REQUEST_ID_HEADER, request_id_middleware

    app = FastAPI()
    app.middleware("http")(request_id_middleware)

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    client = TestClient(app)
    client_req_id = "tracing-from-gateway-42"
    r = client.get("/ping", headers={REQUEST_ID_HEADER: client_req_id})
    assert r.headers[REQUEST_ID_HEADER] == client_req_id


def test_log_level_env_var_respecte(capsys, monkeypatch):
    """`LOG_LEVEL=WARNING` filtre bien les info()."""
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    # Force la reconfig avec le nouveau LOG_LEVEL.
    from src.observability import logging as obs_log

    obs_log._CONFIGURED = False
    log = obs_log.get_logger("test")
    log.info("filtered-out")
    log.warning("kept")

    out = capsys.readouterr().out.strip().splitlines()
    # Seul le warning doit avoir été émis.
    events = [json.loads(line)["event"] for line in out if line]
    assert "filtered-out" not in events
    assert "kept" in events
    # Restaure logging stdlib root level pour ne pas polluer les tests suivants.
    logging.getLogger().setLevel(logging.WARNING)
