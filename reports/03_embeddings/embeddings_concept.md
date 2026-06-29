# Rapport — Embeddings : concepts et utilitaires de similarité

> Version 1.0 — 2026-05-03
> Statut : terminé. Aucune donnée externe consommée (travail conceptuel et pédagogique).

## En une phrase

On pose les **briques mathématiques de base** (normalisation L2, similarité cosinus, produit scalaire, distance L2, recherche des k plus proches) qui seront utilisées par tous les modules ML aval : les encodeurs, les classifieurs, la recherche vectorielle FAISS et le module de pricing par plus proches voisins.

## Livrables

- `src/encoders/similarity_utils.py` — module importable (5 fonctions : `l2_normalize`, `cosine_similarity`, `inner_product`, `l2_distance`, `top_k_similar`)
- `tests/test_similarity_utils.py` — 22 tests d'invariants mathématiques (norme=1, cosine ∈ [-1,1], symétrie, triangle, équivalences L2 ↔ cosine sur normalisés…)
- `notebooks/03_embeddings_concept.ipynb` — démo pédagogique en 6 sections (concept 2D → 3 métriques → normalisation → t-SNE → top-k retrieval)

## Décisions techniques

| Décision | Justification |
|---|---|
| Module `similarity_utils.py` sans préfixe numéroté | Module **importable** (le préfixe numéroté est réservé aux scripts exécutables dotés d'un `main()`) |
| `eps=1e-12` pour le guard de normalisation | Tolérance numérique float64 standard ; pour float16 utiliser ~1e-4 |
| Vecteur nul → vecteur nul (pas NaN) | On évite de propager silencieusement un NaN ; un tel cas doit être journalisé en production s'il se présente |
| Toutes les fonctions sans état | Anti-fuite de données : aucun état accumulé entre les appels |
| Pas de mutation en place | Fonctions pures, l'entrée n'est jamais modifiée |
| Conventions de forme : 1D vs 2D | Compatible avec l'usage de recherche (1 requête × M éléments du corpus) ET l'usage par paires (B_a × B_b) |
| `top_k_similar` en Python pur (pas FAISS) | Utile pour moins de 100k vecteurs, évite d'introduire la dépendance FAISS à ce stade ; FAISS est introduit plus tard pour la recherche vectorielle |

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

- L'encodeur image (SigLIP) consommera `l2_normalize` pour pré-normaliser les embeddings avant écriture `.npy`
- L'encodeur texte (Arctic Embed) fera de même
- L'étape de contrôle de cohérence consommera `top_k_similar` pour vérifier que des produits similaires présentent bien des cosinus proches
- `top_k_similar` est remplacé par FAISS HNSW dès que le corpus dépasse 100k vecteurs

## Annexes

- Stack : `numpy 1.26+`, `scikit-learn 1.5+` (pour le t-SNE dans le notebook)
- Principes appliqués : anti-fuite de données, guard de normalisation L2, nettoyage des ressources
- Architecture cible : RAG ancré sur des encodeurs gelés (SigLIP pour l'image, Arctic pour le texte)
