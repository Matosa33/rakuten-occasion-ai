"""Utilitaires de similarité vectorielle (Cycle 2.1).

Module **importable** (pas de main()). Fournit les briques mathématiques
de base utilisées par tous les modules ML aval :
- Cycle 2 (encoders) : normalisation des embeddings
- Cycle 3 (classifieurs) : k-NN, calcul de distances
- Cycle 4 (FAISS) : choix entre IP / cosine / L2 selon le pré-traitement
- Cycle 7 (pricing) : KNN voisins en espace embedding

Conventions
-----------
- Vecteurs en `np.ndarray` 1D (N,) ou 2D (B, N).
- dtype encouragé : `float32` pour FAISS, `float16` pour stockage compact.
- Toutes les fonctions sont **stateless** (R3 anti-leakage).
- Les fonctions ne mutent JAMAIS les inputs (pas de `x /= norm`, retourne une copie).

Pourquoi un module dédié plutôt que des appels inline
------------------------------------------------------
- Source unique de vérité : si on change la convention (ex: float16 vs float32),
  un seul fichier à modifier.
- R11 guard sur normalisation L2 : implémenté UNE FOIS ici, jamais oublié ailleurs.
- Tests d'invariants centralisés : on garantit cosine_sim ∈ [-1, 1], normalisation produit norme 1, etc.

Usage
-----
    from src.encoders.similarity_utils import l2_normalize, cosine_similarity, inner_product

    embeddings = np.load("data/embeddings/vision_siglip_v1.npy")
    embeddings_normed = l2_normalize(embeddings)  # shape (B, N), norme 1 par ligne
    sim = cosine_similarity(query_vec, embeddings_normed)  # shape (B,)
"""

from __future__ import annotations

import numpy as np

# Tolérance numérique pour considérer une norme comme nulle (R11 guard).
# 1e-12 est l'epsilon par défaut pour float64 ; pour float16 utiliser ~1e-4.
DEFAULT_NORM_EPS = 1e-12


def l2_normalize(
    x: np.ndarray,
    eps: float = DEFAULT_NORM_EPS,
    axis: int = -1,
) -> np.ndarray:
    """Normalise L2 le long d'un axe (par défaut : dernier axe).

    Pour un vecteur 1D (N,) : retourne x / ||x||.
    Pour une matrice (B, N) : normalise chaque ligne indépendamment.

    Garde-fou R11 : si ||x|| < eps, retourne un vecteur nul (pas de NaN
    propagé silencieusement). Ce cas indique typiquement un bug amont
    (embedding non-initialisé, padding, etc.) — à logger en prod.

    Args:
        x: Tableau numpy 1D ou 2D.
        eps: Seuil sous lequel on considère la norme comme nulle.
        axis: Axe le long duquel calculer la norme (défaut : -1).

    Returns:
        Tableau de même shape que x, avec norme L2 = 1 par ligne (ou 0 si input nul).
    """
    norms = np.linalg.norm(x, axis=axis, keepdims=True)
    # Évite la division par zéro : remplace les normes < eps par 1, puis
    # la sortie sera 0 (input divisé par 1, mais input nul → reste nul).
    safe_norms = np.where(norms < eps, 1.0, norms)
    return np.where(norms < eps, 0.0, x / safe_norms)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity entre vecteurs (= inner product après L2 normalize).

    Cas supportés :
    - 1D vs 1D : retourne un scalaire ∈ [-1, 1].
    - 1D vs 2D : retourne un vecteur (N_b,) — similarité du query avec chaque vecteur de b.
    - 2D vs 2D : retourne une matrice (N_a, N_b) — similarité pairwise.

    Note : pour les pipelines retrieval (FAISS), il est plus efficace de
    pré-normaliser TOUS les vecteurs UNE FOIS via `l2_normalize`, puis
    utiliser l'inner product (FAISS metric=METRIC_INNER_PRODUCT). La
    fonction `cosine_similarity` ici est pour les usages ad hoc.

    Args:
        a: Vecteur(s) source(s), shape (N,) ou (B_a, N).
        b: Vecteur(s) cible(s), shape (N,) ou (B_b, N).

    Returns:
        Similarité(s) cosine ∈ [-1, 1], shape selon les inputs.
    """
    a_norm = l2_normalize(a)
    b_norm = l2_normalize(b)
    return inner_product(a_norm, b_norm)


def inner_product(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Inner product (= dot product). Cf. cosine_similarity pour les shapes."""
    if a.ndim == 1 and b.ndim == 1:
        return np.dot(a, b)
    if a.ndim == 1:
        # 1D vs 2D : (N,) vs (B, N) → (B,)
        return b @ a
    if b.ndim == 1:
        return a @ b
    # 2D vs 2D : (B_a, N) vs (B_b, N) → (B_a, B_b)
    return a @ b.T


def l2_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distance euclidienne L2 entre vecteurs.

    Note : sur des vecteurs L2-normalisés (norme 1), il existe une équivalence
    monotone entre L2 distance et cosine similarity :
        L2(a, b)² = 2 - 2·cos(a, b)
    Donc trier par L2 ascendant = trier par cosine descendant. Le choix entre
    L2 et cosine est principalement une question d'API (FAISS supporte
    METRIC_L2 et METRIC_INNER_PRODUCT).

    Args:
        a, b: Vecteurs 1D ou 2D (mêmes contraintes que cosine_similarity).

    Returns:
        Distance(s) L2 ∈ [0, +∞[, shape selon les inputs.
    """
    if a.ndim == 1 and b.ndim == 1:
        return np.linalg.norm(a - b)
    if a.ndim == 1:
        return np.linalg.norm(b - a, axis=-1)
    if b.ndim == 1:
        return np.linalg.norm(a - b, axis=-1)
    # 2D vs 2D : pairwise distance, shape (B_a, B_b)
    # Identité : ||a - b||² = ||a||² + ||b||² - 2·a·b
    a_norm_sq = (a**2).sum(axis=1, keepdims=True)
    b_norm_sq = (b**2).sum(axis=1)
    cross = a @ b.T
    sq_dists = a_norm_sq + b_norm_sq - 2 * cross
    return np.sqrt(np.maximum(sq_dists, 0))  # max pour éviter sqrt négatif (numérique)


def top_k_similar(
    query: np.ndarray,
    corpus: np.ndarray,
    k: int = 5,
    metric: str = "cosine",
) -> tuple[np.ndarray, np.ndarray]:
    """Retourne les top-k indices et scores du corpus les plus similaires au query.

    Utile pour des recherches **petites** (< 100k items) sans installer FAISS.
    Pour > 100k items, utiliser FAISS (cf. Cycle 4).

    Args:
        query: Vecteur 1D (N,) ou batch 2D (B, N).
        corpus: Matrice (M, N) des vecteurs candidats.
        k: Nombre de top voisins à retourner.
        metric: "cosine" | "ip" (inner product) | "l2".

    Returns:
        Tuple (indices, scores) :
        - indices : shape (k,) si query 1D, (B, k) si 2D
        - scores : shape (k,) ou (B, k), trié décroissant pour cosine/ip,
          croissant pour l2.
    """
    if metric == "cosine":
        scores = cosine_similarity(query, corpus)
        descending = True
    elif metric == "ip":
        scores = inner_product(query, corpus)
        descending = True
    elif metric == "l2":
        scores = l2_distance(query, corpus)
        descending = False
    else:
        raise ValueError(f"metric inconnue : {metric}. Attendu : cosine | ip | l2.")

    # argsort retourne ascendant ; on inverse pour cosine/ip
    if scores.ndim == 1:
        order = np.argsort(scores)
        if descending:
            order = order[::-1]
        top_idx = order[:k]
        return top_idx, scores[top_idx]
    # Batch
    order = np.argsort(scores, axis=-1)
    if descending:
        order = order[:, ::-1]
    top_idx = order[:, :k]
    top_scores = np.take_along_axis(scores, top_idx, axis=-1)
    return top_idx, top_scores
