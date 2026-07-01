# Bench classifieurs - comparaison des modèles

> Synthèse comparative des modèles de classification entraînés.
> Tri par F1 pondéré (test) décroissant. Le modèle en tête est celui promu en production via l'alias `@Production` du registre MLflow.

## Comparaison

| Rang | Modèle | Type | F1_w test | F1_w val | F1_macro test | Acc test | Top-3 test | ECE test | Train (s) |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | **knn-faiss_v1** | k-NN via FAISS HNSW (cosine, weighted by similarity) | **0.9537** | 0.9532 | 0.9415 | 0.9537 | 0.9881 | 0.0069 | 0 |
| 2 | **fusion_v1** | Fusion adaptive | **0.9522** | 0.9514 | 0.9418 | 0.9522 | 0.9990 | 0.0230 | 0 |
| 3 | **tfidf-svm_v1** | TF-IDF + LinearSVC + Platt | **0.9503** | 0.9496 | 0.9375 | 0.9503 | 0.9985 | 0.0092 | 956 |
| 4 | **mlp-embed_v1** | MLP head 1024→512→256→C | **0.9489** | 0.9485 | 0.9382 | 0.9489 | 0.9989 | 0.0013 | 514 |
| 5 | **svm-embed_v1** | LinearSVC + Platt sur embeddings text Arctic | **0.9311** | 0.9309 | 0.9193 | 0.9312 | 0.9977 | 0.0145 | 924 |

## Lecture

- **Meilleur modèle** : `knn-faiss_v1` avec F1 pondéré (test) = **0.9537**
- **Meilleure calibration** : le modèle dont l'ECE (test) est minimal (cible < 0.05)
- **Latence d'inférence** : non mesurée ici (à mesurer lors de la mise en service via l'API)

## Décision

Promouvoir `knn-faiss_v1` au stage `@Production` du registre MLflow.
Les autres modèles restent disponibles via l'alias `@Latest` pour un futur test A/B.

## Fusion adaptive

- fusion fusion (`fusion_v1`) F1_w test = 0.9522
- Meilleur modèle individuel : `knn-faiss_v1` à 0.9537
- **Gain fusion vs best individual : -0.0015**
  - Si gain > +0,02 : la fusion vaut son coût computationnel (predict 4-5 modèles)
  - Si gain < +0,02 : préférer le modèle individuel le plus rapide

## Annexes

- Scripts : `src/classifiers/01..06_*.py`
- Module de métriques : `src/classifiers/metrics.py`
- JSON détaillés : `reports/04_classifiers_bench/*.json`
- Architecture : RAG ancré ; périmètre MVP restreint à 4 catégories
- Anti-fuite de données strict : ajustement sur le jeu d'entraînement, prédiction sur validation/test