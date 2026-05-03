"""Invariants de similarity_utils — propriétés mathématiques fondamentales.

Ces tests garantissent que les briques de similarité respectent les invariants
attendus. Si l'un casse, tous les modules ML aval (encoders, classifieurs,
FAISS, pricing) sont potentiellement compromis.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.encoders.similarity_utils import (
    cosine_similarity,
    inner_product,
    l2_distance,
    l2_normalize,
    top_k_similar,
)

RNG = np.random.default_rng(42)


# ─── l2_normalize ─────────────────────────────────────────────────────────


def test_l2_normalize_1d_produces_unit_norm():
    """Norme L2 du vecteur normalisé = 1."""
    v = np.array([3.0, 4.0])
    out = l2_normalize(v)
    assert np.isclose(np.linalg.norm(out), 1.0)


def test_l2_normalize_2d_produces_unit_norms_per_row():
    """Chaque ligne d'une matrice normalisée a norme 1."""
    m = RNG.normal(size=(10, 5))
    out = l2_normalize(m)
    norms = np.linalg.norm(out, axis=-1)
    assert np.allclose(norms, 1.0)


def test_l2_normalize_zero_vector_returns_zero_no_nan():
    """R11 guard : vecteur nul → vecteur nul (pas de NaN propagé)."""
    v = np.zeros(5)
    out = l2_normalize(v)
    assert not np.any(np.isnan(out))
    assert np.allclose(out, 0)


def test_l2_normalize_does_not_mutate_input():
    """Pure function : l'input n'est pas modifié."""
    v = np.array([1.0, 2.0, 3.0])
    v_copy = v.copy()
    _ = l2_normalize(v)
    assert np.allclose(v, v_copy)


def test_l2_normalize_preserves_direction():
    """La normalisation conserve la direction (signe et ratios)."""
    v = np.array([2.0, -4.0, 6.0])
    out = l2_normalize(v)
    # ratios entre composantes preservés
    assert np.isclose(out[0] / out[1], v[0] / v[1])
    assert np.isclose(out[2] / out[1], v[2] / v[1])


# ─── cosine_similarity ────────────────────────────────────────────────────


def test_cosine_self_similarity_is_one():
    """cos(v, v) = 1 pour tout v non-nul."""
    v = np.array([1.0, 2.0, 3.0, 4.0])
    assert np.isclose(cosine_similarity(v, v), 1.0)


def test_cosine_orthogonal_vectors_zero():
    """cos(v1, v2) = 0 pour vecteurs orthogonaux."""
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert np.isclose(cosine_similarity(a, b), 0.0)


def test_cosine_opposite_vectors_minus_one():
    """cos(v, -v) = -1."""
    v = np.array([1.0, 2.0, 3.0])
    assert np.isclose(cosine_similarity(v, -v), -1.0)


def test_cosine_in_range_minus_one_one():
    """cos ∈ [-1, 1] pour tous vecteurs aléatoires."""
    a = RNG.normal(size=100)
    b = RNG.normal(size=100)
    sim = cosine_similarity(a, b)
    assert -1.0 <= sim <= 1.0


def test_cosine_is_symmetric():
    """cos(a, b) = cos(b, a)."""
    a = RNG.normal(size=50)
    b = RNG.normal(size=50)
    assert np.isclose(cosine_similarity(a, b), cosine_similarity(b, a))


def test_cosine_1d_vs_2d():
    """1D vs 2D retourne un vecteur shape (B,)."""
    query = RNG.normal(size=10)
    corpus = RNG.normal(size=(20, 10))
    sims = cosine_similarity(query, corpus)
    assert sims.shape == (20,)
    assert np.all((sims >= -1) & (sims <= 1))


def test_cosine_2d_vs_2d_pairwise():
    """2D vs 2D retourne matrice (B_a, B_b)."""
    a = RNG.normal(size=(5, 8))
    b = RNG.normal(size=(7, 8))
    sims = cosine_similarity(a, b)
    assert sims.shape == (5, 7)


# ─── inner_product ────────────────────────────────────────────────────────


def test_inner_product_normalized_equals_cosine():
    """ip(L2_normalize(a), L2_normalize(b)) == cos(a, b)."""
    a = RNG.normal(size=20)
    b = RNG.normal(size=20)
    ip = inner_product(l2_normalize(a), l2_normalize(b))
    cos = cosine_similarity(a, b)
    assert np.isclose(ip, cos)


# ─── l2_distance ──────────────────────────────────────────────────────────


def test_l2_distance_self_is_zero():
    """L2(v, v) = 0."""
    v = RNG.normal(size=15)
    assert np.isclose(l2_distance(v, v), 0.0)


def test_l2_distance_is_symmetric():
    """L2(a, b) = L2(b, a)."""
    a = RNG.normal(size=10)
    b = RNG.normal(size=10)
    assert np.isclose(l2_distance(a, b), l2_distance(b, a))


def test_l2_distance_triangle_inequality():
    """L2(a, c) ≤ L2(a, b) + L2(b, c)."""
    a = RNG.normal(size=5)
    b = RNG.normal(size=5)
    c = RNG.normal(size=5)
    assert l2_distance(a, c) <= l2_distance(a, b) + l2_distance(b, c) + 1e-10


def test_l2_distance_normalized_relates_to_cosine():
    """Sur vecteurs normalisés : L2² = 2 - 2·cos."""
    a = l2_normalize(RNG.normal(size=20))
    b = l2_normalize(RNG.normal(size=20))
    l2 = l2_distance(a, b)
    cos = cosine_similarity(a, b)
    assert np.isclose(l2**2, 2 - 2 * cos, atol=1e-6)


# ─── top_k_similar ────────────────────────────────────────────────────────


def test_top_k_returns_correct_shape_1d():
    query = RNG.normal(size=10)
    corpus = RNG.normal(size=(50, 10))
    idx, scores = top_k_similar(query, corpus, k=5, metric="cosine")
    assert idx.shape == (5,)
    assert scores.shape == (5,)


def test_top_k_returns_descending_for_cosine():
    query = RNG.normal(size=10)
    corpus = RNG.normal(size=(50, 10))
    _, scores = top_k_similar(query, corpus, k=10, metric="cosine")
    assert np.all(np.diff(scores) <= 0)  # décroissant


def test_top_k_returns_ascending_for_l2():
    query = RNG.normal(size=10)
    corpus = RNG.normal(size=(50, 10))
    _, scores = top_k_similar(query, corpus, k=10, metric="l2")
    assert np.all(np.diff(scores) >= 0)  # croissant


def test_top_k_finds_self_in_corpus():
    """Si query ∈ corpus, le top-1 est l'index de query lui-même."""
    corpus = RNG.normal(size=(20, 8))
    query = corpus[7].copy()
    idx, scores = top_k_similar(query, corpus, k=1, metric="cosine")
    assert idx[0] == 7
    assert np.isclose(scores[0], 1.0)


def test_top_k_invalid_metric_raises():
    with pytest.raises(ValueError, match="metric inconnue"):
        top_k_similar(RNG.normal(size=5), RNG.normal(size=(10, 5)), metric="manhattan")
