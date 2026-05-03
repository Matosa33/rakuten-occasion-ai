# Rapport sous-todo 2.1 — Embeddings concept + similarity utils

> Version 1.0 — 2026-05-03
> Statut : `completed`. Aucune donnée externe consommée (concept pédagogique).

## En une phrase

On pose les **briques mathématiques de base** (normalisation L2, cosine similarity, inner product, L2 distance, top-k retrieval) qui seront utilisées par tous les modules ML aval (Cycles 2.2-2.4 encoders, Cycle 3 classifieurs, Cycle 4 FAISS, Cycle 7 pricing KNN).

## Livrables

- `src/encoders/similarity_utils.py` — module importable (5 fonctions : `l2_normalize`, `cosine_similarity`, `inner_product`, `l2_distance`, `top_k_similar`)
- `tests/test_similarity_utils.py` — 22 tests d'invariants mathématiques (norme=1, cosine ∈ [-1,1], symétrie, triangle, équivalences L2 ↔ cosine sur normalisés…)
- `notebooks/03_embeddings_concept.ipynb` — démo pédagogique en 6 sections (concept 2D → 3 métriques → normalisation → t-SNE → top-k retrieval)

## Décisions techniques

| Décision | Justification |
|---|---|
| Module `similarity_utils.py` sans préfixe numéroté | Module **importable** (R1 réservé aux scripts exécutables avec `main()`) |
| `eps=1e-12` pour guard normalisation | Tolérance numérique float64 standard ; pour float16 utiliser ~1e-4 |
| Vecteur nul → vecteur nul (pas NaN) | R11 — pas de NaN propagé silencieusement, à logger en prod si rencontré |
| Toutes les fonctions stateless | R3 anti-leakage — pas d'état accumulé entre appels |
| Pas de mutation in-place | Fonctions pures, l'input n'est jamais modifié |
| Conventions shape : 1D vs 2D | Compatible avec usage retrieval (1 query × M corpus) ET pairwise (B_a × B_b) |
| `top_k_similar` Python pur (pas FAISS) | Utile pour < 100k vecteurs, évite la dépendance FAISS au Cycle 2 ; FAISS arrive en Cycle 4 |

## Invariants vérifiés (22 tests)

| Catégorie | Tests |
|---|---:|
| `l2_normalize` (norme=1, guard zéro, immutabilité, direction) | 5 |
| `cosine_similarity` (self=1, orthog=0, opposé=-1, range, symétrie, shapes 1D/2D) | 7 |
| `inner_product` (équivalence cosine après normalize) | 1 |
| `l2_distance` (self=0, symétrie, triangle, relation L2²=2-2cos sur normalisés) | 4 |
| `top_k_similar` (shapes, ordre descendant cosine/asc L2, self=top1, raise sur metric invalide) | 5 |

**Total : 22/22 passent en ~0,2 sec.**

## Pour aller plus loin

- **Cycle 2.2** consommera `l2_normalize` pour pré-normaliser les embeddings SigLIP avant écriture .npy
- **Cycle 2.3** idem pour Arctic Embed
- **Cycle 2.4** consommera `top_k_similar` pour le sanity check (vérifier que des produits similaires ont des cosines proches)
- **Cycle 4** : `top_k_similar` est remplacé par FAISS HNSW dès que le corpus > 100k vecteurs

## Annexes

- Stack : `numpy 1.26+`, `scikit-learn 1.5+` (pour t-SNE dans le notebook)
- Règles référencées : R3 (anti-leakage), R11 (guard L2), R20 (cleanup)
- ADR référencées : D-009 (architecture cible RAG-grounded — les encoders sont E1/E2 frozen)
