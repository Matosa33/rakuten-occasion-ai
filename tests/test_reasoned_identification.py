"""Cycle 36 — tests de l'identification raisonnée (src/vlm/reasoned_identification.py).

Best-effort, non bloquant : pas de réseau réel (post_with_retry + _to_data_url monkeypatchés).
On vérifie la sérialisation des fiches, le grounding (anti-hallucination ASIN), le rejet d'ancre
non sourcée, le parsing tolérant et la dégradation propre.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import src.vlm.reasoned_identification as ri_mod
from src.vlm.reasoned_identification import (
    SourcedFacet,
    _parse,
    build_identify_prompt,
    reason_identify,
    summarize_candidate,
)


@dataclass
class FakeCandidate:
    parent_asin: str
    title: str = ""
    brand: str = ""
    category_fine: str = ""
    price: float | None = None
    attributes: dict[str, str] = field(default_factory=dict)


class FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def _cands() -> list[FakeCandidate]:
    return [
        FakeCandidate("A1", "Coros Pace 2 GPS Watch", "Coros", "Running GPS Units", 150.0,
                      {"capacity": "", "color": "black"}),
        FakeCandidate("A2", "Coros Pace 2 Nylon Band strap", "Coros", "Watch Bands", 13.0),
        FakeCandidate("A3", "Garmin Forerunner 55", "Garmin", "Running GPS Units", 199.0),
    ]


def test_summarize_candidate_includes_price_and_index() -> None:
    line = summarize_candidate(0, _cands()[0])
    assert line.startswith("[0] Coros Pace 2")
    assert "price_usd=150.00" in line
    assert "asin=A1" in line
    # sans prix valide → pas de price_usd
    no_price = summarize_candidate(1, FakeCandidate("X", "Thing", price=None))
    assert "price_usd" not in no_price


def test_summarize_candidate_truncates_long_title() -> None:
    long = summarize_candidate(0, FakeCandidate("X", "Z" * 300))
    # [0] + 140 chars max de titre
    assert len(long.split(" | ")[0]) <= 4 + ri_mod.TITLE_TRUNC + 1


def test_build_prompt_contains_candidates_and_exclusion_rules() -> None:
    prompt = build_identify_prompt(_cands(), {"brand": "Coros"}, "montre running")
    assert "[0]" in prompt and "[2]" in prompt
    assert "brand=Coros" in prompt and "seller_text: montre running" in prompt
    # règles d'exclusion accessoires présentes
    for kw in ("strap", "bundle", "charger", "case"):
        assert kw in prompt


def test_parse_valid_json_returns_dataclass() -> None:
    raw = json.dumps({
        "product_family": "Coros Pace 2 GPS watch",
        "family_confidence": 0.9,
        "chosen_parent_asin": "A1",
        "catalog_miss": False,
        "reference_new_price_usd": 150,
        "reference_new_confidence": 0.7,
        "price_anchor_evidence": [0, 2],
        "ask_question": False,
        "facet_question": "",
        "facets": [{"key": "color", "value": "black", "source": "observed"},
                   {"key": "brand", "value": "Coros", "source": "0"}],
    })
    out = _parse(raw, _cands())
    assert out is not None
    assert out.chosen_parent_asin == "A1"
    assert out.reference_new_price_usd == 150.0
    assert out.price_anchor_evidence == [0, 2]
    assert SourcedFacet("color", "black", "observed") in out.facets


def test_parse_rejects_hallucinated_asin() -> None:
    raw = json.dumps({"chosen_parent_asin": "ZZZ", "reference_new_price_usd": 150,
                      "price_anchor_evidence": [0], "facets": []})
    out = _parse(raw, _cands())
    assert out is not None
    assert out.chosen_parent_asin == "A1"  # retombe sur le top-1 (grounded)


def test_parse_drops_anchor_when_no_evidence_and_not_catalog_miss() -> None:
    raw = json.dumps({"chosen_parent_asin": "A1", "reference_new_price_usd": 150,
                      "price_anchor_evidence": [], "catalog_miss": False, "facets": []})
    out = _parse(raw, _cands())
    assert out is not None
    assert out.reference_new_price_usd is None  # ancre non groundée → jetée


def test_parse_keeps_anchor_for_catalog_miss_by_analogy() -> None:
    raw = json.dumps({"chosen_parent_asin": "", "reference_new_price_usd": 150,
                      "price_anchor_evidence": [], "catalog_miss": True, "facets": []})
    out = _parse(raw, _cands())
    assert out is not None
    assert out.reference_new_price_usd == 150.0  # analogie tolérée en catalog-miss


def test_parse_handles_fences_and_prose() -> None:
    fenced = "```json\n" + json.dumps({"chosen_parent_asin": "A1", "facets": []}) + "\n```"
    assert _parse(fenced, _cands()) is not None
    prose = "Here is the answer: " + json.dumps({"chosen_parent_asin": "A1", "facets": []}) + " done."
    assert _parse(prose, _cands()) is not None
    assert _parse("not json at all", _cands()) is None


def test_parse_clamps_confidence_and_drops_invalid_facet_source() -> None:
    raw = json.dumps({"chosen_parent_asin": "A1", "family_confidence": 1.7,
                      "reference_new_confidence": -0.2, "price_anchor_evidence": [0],
                      "reference_new_price_usd": 10,
                      "facets": [{"key": "k", "value": "v", "source": "99"},  # index hors borne
                                 {"key": "ok", "value": "v", "source": "1"}]})
    out = _parse(raw, _cands())
    assert out is not None
    assert out.family_confidence == 1.0
    assert out.reference_new_confidence == 0.0
    assert [f.key for f in out.facets] == ["ok"]  # facette à source invalide jetée


def test_reason_identify_returns_none_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    called = {"n": 0}
    monkeypatch.setattr(ri_mod, "post_with_retry", lambda *a, **k: called.__setitem__("n", 1))
    assert reason_identify([], _cands()) is None
    assert called["n"] == 0  # aucun appel réseau


def test_reason_identify_returns_none_on_http_error(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(ri_mod, "_to_data_url", lambda p: "data:image/jpeg;base64,xxx")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(ri_mod, "post_with_retry", boom)
    assert reason_identify(["/fake.jpg"], _cands()) is None  # pas de propagation


def test_reason_identify_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(ri_mod, "_to_data_url", lambda p: "data:image/jpeg;base64,xxx")
    payload_seen = {}

    def fake_post(payload, key, timeout=90):
        payload_seen.update(payload)
        return FakeResponse(json.dumps({
            "product_family": "Coros Pace 2 GPS watch", "family_confidence": 0.9,
            "chosen_parent_asin": "A1", "catalog_miss": False,
            "reference_new_price_usd": 150, "reference_new_confidence": 0.7,
            "price_anchor_evidence": [0], "ask_question": False, "facet_question": "",
            "facets": [{"key": "color", "value": "black", "source": "observed"}],
        }))

    monkeypatch.setattr(ri_mod, "post_with_retry", fake_post)
    out = reason_identify(["/fake.jpg"], _cands(), observed={"color": "black"}, seller_text="montre")
    assert out is not None
    assert out.chosen_parent_asin == "A1"
    assert out.reference_new_price_usd == 150.0
    assert payload_seen["model"] == ri_mod.IDENTIFY_MODEL
