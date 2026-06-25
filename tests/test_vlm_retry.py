"""Retry des appels VLM (Cycle 35.4) : un 429/5xx ponctuel ne doit pas tuer le flow."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import src.vlm.photo_extraction as pe


def _resp(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    side = pe.requests.HTTPError(f"HTTP {status}") if status >= 400 else None
    r.raise_for_status = MagicMock(side_effect=side)
    return r


def test_post_with_retry_reessaie_puis_reussit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_post(url, headers, json, timeout):  # noqa: ANN001, ARG001
        calls["n"] += 1
        return _resp(503 if calls["n"] < 3 else 200)

    monkeypatch.setattr(pe.requests, "post", fake_post)
    monkeypatch.setattr(pe.time, "sleep", lambda _s: None)
    r = pe.post_with_retry({"x": 1}, "key")
    assert calls["n"] == 3
    assert r.status_code == 200


def test_post_with_retry_echoue_apres_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pe.requests, "post", lambda *a, **k: _resp(429))
    monkeypatch.setattr(pe.time, "sleep", lambda _s: None)
    with pytest.raises(pe.requests.HTTPError):
        pe.post_with_retry({"x": 1}, "key")
