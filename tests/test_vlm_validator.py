"""Tests pour VLM zero-shot validator (src/vlm/01_zero_shot_validate.py)."""

from __future__ import annotations

import importlib

_vlm = importlib.import_module("src.vlm.01_zero_shot_validate")
parse_vlm_response = _vlm.parse_vlm_response
MockVLMValidator = _vlm.MockVLMValidator
VLMResponse = _vlm.VLMResponse


class TestParseVLMResponse:
    def test_parses_valid_json(self):
        raw = '{"match": true, "confidence": 0.85, "reason": "Same model"}'
        resp = parse_vlm_response(raw)
        assert resp.parse_ok
        assert resp.match is True
        assert resp.confidence == 0.85
        assert "Same model" in resp.reason

    def test_handles_invalid_json(self):
        resp = parse_vlm_response("not json at all")
        assert not resp.parse_ok
        assert resp.match is False
        assert resp.confidence == 0.0

    def test_handles_partial_json_missing_fields(self):
        # JSON valide mais sans tous les champs
        raw = '{"match": true}'
        resp = parse_vlm_response(raw)
        assert resp.parse_ok
        assert resp.match is True
        assert resp.confidence == 0.0  # default

    def test_coerces_match_to_bool(self):
        # match: 1 (truthy) → True
        raw = '{"match": 1, "confidence": 0.5, "reason": ""}'
        resp = parse_vlm_response(raw)
        assert resp.match is True


class TestMockVLMValidator:
    def test_mock_always_returns_parse_ok(self):
        validator = MockVLMValidator(seed=42)
        for _ in range(20):
            resp = validator.validate("img1", "img2", {"title": "test"})
            assert resp.parse_ok is True
            assert isinstance(resp.match, bool)
            assert 0.0 <= resp.confidence <= 1.0

    def test_mock_is_deterministic_with_seed(self):
        v1 = MockVLMValidator(seed=42)
        v2 = MockVLMValidator(seed=42)
        r1 = v1.validate("a", "b", {})
        r2 = v2.validate("a", "b", {})
        assert r1.match == r2.match
        assert abs(r1.confidence - r2.confidence) < 1e-6

    def test_mock_match_rate_around_90pct(self):
        validator = MockVLMValidator(seed=42)
        n = 1000
        n_match = sum(validator.validate("a", "b", {}).match for _ in range(n))
        # Politique mock : ~90 % match → entre 85 et 95 %
        assert 850 < n_match < 950
