# Bench des index FAISS

> Mesure du recall@k et de la latence sur 1 000 requêtes du jeu de validation,
> contre un index de 3 156 705 vecteurs × 1024 dimensions.

## Comparaison

| Index | Recall@1 | Recall@5 | Recall@10 | Latence p99 (ms) | Taille fichier |
|---|---:|---:|---:|---:|---:|
| FLAT | 1.0000 | 1.0000 | 1.0000 | 23.03 | 12330.9 MB |
| HNSW | 0.9480 | 0.9722 | 0.9755 | 0.29 | 13150.1 MB |
| IVFPQ | 0.4150 | 0.4428 | 0.4426 | 0.19 | 125.4 MB |

## Décision

Pour la mise en service via l'API : **HNSW** (rapide et recall ≥ 95 %).
Pour la référence d'évaluation : **Flat IP** (recall 100 %).
Pour un passage à l'échelle futur (plus de 20 M de vecteurs) : envisager **IVF_PQ** si le recall reste acceptable (> 0,85).