# Bench classifieurs Cycle 3 — M1-M6

> Synthèse comparative des 6 modèles entraînés en Cycle 3 (P04, C12-C15).
> Tri par F1_weighted_test décroissant. Vainqueur en haut → MLflow alias `@Production` (Cycle 11).

## Comparaison

| Rang | Modèle | Type | F1_w test | F1_w val | F1_macro test | Acc test | Top-3 test | ECE test | Train (s) |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | **m1_knn_v1** | k-NN via FAISS HNSW (cosine, weighted by similarity) | **0.9537** | 0.9532 | 0.9415 | 0.9537 | 0.9881 | 0.0069 | 0 |
| 2 | **m6_fusion_v1** | Fusion adaptive | **0.9522** | 0.9514 | 0.9418 | 0.9522 | 0.9990 | 0.0230 | 0 |
| 3 | **m5_tfidf_linsvc_v1** | TF-IDF + LinearSVC + Platt | **0.9503** | 0.9496 | 0.9375 | 0.9503 | 0.9985 | 0.0092 | 956 |
| 4 | **m4_mlp_v1** | MLP head 1024→512→256→C | **0.9489** | 0.9485 | 0.9382 | 0.9489 | 0.9989 | 0.0013 | 514 |
| 5 | **m2_svm_v1** | LinearSVC + Platt sur embeddings text Arctic | **0.9311** | 0.9309 | 0.9193 | 0.9312 | 0.9977 | 0.0145 | 924 |

## Lecture

- **Vainqueur** : `m1_knn_v1` avec F1_weighted test = **0.9537**
- **Calibration la mieux** : modèle avec ECE test minimum (cible < 0.05)
- **Latence inférence** : non mesurée ici (à mesurer en Cycle 11 quand on serve via API)

## Décision

Pour MLflow Registry (Cycle 11), promouvoir `m1_knn_v1` au stage `@Production`. 
Les autres modèles restent disponibles via alias `@Latest` pour A/B test futur.

## Fusion adaptive

- M6 fusion (`m6_fusion_v1`) F1_w test = 0.9522
- Meilleur modèle individuel : `m1_knn_v1` à 0.9537
- **Gain fusion vs best individual : -0.0015**
  - Si gain > +0,02 : la fusion vaut son coût computationnel (predict 4-5 modèles)
  - Si gain < +0,02 : préférer le modèle individuel le plus rapide

## Annexes

- Scripts : `src/classifiers/01..06_*.py`
- Module métriques : `src/classifiers/metrics.py`
- JSON détaillés : `reports/04_classifiers_bench/m{1..6}_*.json`
- ADR référencées : D-009 (RAG-grounded), D-011 (4 cat MVP)
- Règle R3 : anti-leakage strict (fit train, predict val/test)