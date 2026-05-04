"""Tests pour Akinator backend (src/retrieval/04_akinator_backend.py)."""

from __future__ import annotations

import importlib

_akinator = importlib.import_module("src.retrieval.04_akinator_backend")
compute_discriminative_attributes = _akinator.compute_discriminative_attributes
select_next_observation = _akinator.select_next_observation
is_ambiguous = _akinator.is_ambiguous
is_clarified = _akinator.is_clarified
ATTRIBUTE_OBSERVATION_MAP = _akinator.ATTRIBUTE_OBSERVATION_MAP


class TestAmbiguityCheck:
    def test_close_scores_are_ambiguous(self):
        assert is_ambiguous(0.85, 0.83)

    def test_distant_scores_not_ambiguous(self):
        assert not is_ambiguous(0.85, 0.70)

    def test_clarified_when_gap_large(self):
        assert is_clarified(0.85, 0.60)

    def test_not_clarified_when_close(self):
        assert not is_clarified(0.85, 0.80)


class TestDiscriminativeAttributes:
    def test_empty_input_returns_empty(self):
        assert compute_discriminative_attributes([]) == []

    def test_attributes_with_all_same_values_score_zero(self):
        cands = [
            {"color": "red", "brand": "Apple"},
            {"color": "red", "brand": "Apple"},
            {"color": "red", "brand": "Apple"},
        ]
        result = compute_discriminative_attributes(cands)
        # Tous les scores devraient être 0 (entropie nulle)
        assert all(s == 0.0 for _, s in result)

    def test_all_different_values_score_one(self):
        cands = [
            {"color": "red"},
            {"color": "blue"},
            {"color": "green"},
        ]
        result = compute_discriminative_attributes(cands)
        # Entropie = log2(3), normalisée = 1.0
        assert any(s == 1.0 for _, s in result)

    def test_attributes_only_in_one_candidate_excluded(self):
        cands = [
            {"unique_attr": "value", "common": "x"},
            {"common": "y"},
        ]
        result = compute_discriminative_attributes(cands)
        attr_names = [a for a, _ in result]
        assert "unique_attr" not in attr_names  # n'apparaît qu'1 fois
        assert "common" in attr_names

    def test_sorted_by_discriminance_desc(self):
        cands = [
            {"a": "x", "b": "y"},
            {"a": "x", "b": "z"},  # b varie, a non
            {"a": "x", "b": "w"},
        ]
        result = compute_discriminative_attributes(cands)
        # b devrait être en premier (discriminant), a après
        if len(result) >= 2:
            scores = [s for _, s in result]
            assert scores == sorted(scores, reverse=True)


class TestObservationSelection:
    def test_returns_none_when_no_discrimination(self):
        cands = [{"color": "red"}, {"color": "red"}]
        obs = select_next_observation(cands)
        assert obs is None

    def test_skips_already_asked_attributes(self):
        cands = [
            {"color": "red", "brand": "Apple"},
            {"color": "blue", "brand": "Samsung"},
        ]
        obs = select_next_observation(cands, already_asked_attributes={"color", "brand"})
        # Tous discriminants demandés → None
        assert obs is None

    def test_returns_known_observation_type_when_attribute_mapped(self):
        cands = [
            {"brand": "Apple", "color": "red"},
            {"brand": "Samsung", "color": "blue"},
        ]
        obs = select_next_observation(cands)
        assert obs is not None
        assert obs.observation_type in {
            mapping["type"] for mapping in ATTRIBUTE_OBSERVATION_MAP.values()
        } | {"back_view"}  # ou DEFAULT_OBSERVATION
        assert obs.candidates_count == 2
        assert 0.0 <= obs.discriminative_score <= 1.0


class TestObservationMap:
    def test_all_mappings_have_required_keys(self):
        for attr, mapping in ATTRIBUTE_OBSERVATION_MAP.items():
            assert "type" in mapping
            assert "instruction" in mapping
            assert isinstance(mapping["instruction"], str)
            assert len(mapping["instruction"]) > 10  # instruction lisible
