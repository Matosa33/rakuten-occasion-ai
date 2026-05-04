# FAISS indices bench — Cycle 4.1

> Mesure recall@k et latence sur 1_000 queries du val 
> contre un index de 3_156_705 vecteurs × 1024 dim.

## Comparaison

| Index | Recall@1 | Recall@5 | Recall@10 | Latence p99 (ms) | Taille fichier |
|---|---:|---:|---:|---:|---:|
| FLAT | 1.0000 | 1.0000 | 1.0000 | 23.03 | 12330.9 MB |
| HNSW | 0.9480 | 0.9722 | 0.9755 | 0.29 | 13150.1 MB |
| IVFPQ | 0.4150 | 0.4428 | 0.4426 | 0.19 | 125.4 MB |

## Décision

Pour le serving (Cycle 9 API) : **HNSW** (rapide + recall ≥ 95 %).
Pour la référence d'évaluation : **Flat IP** (recall 100 %).
Pour scale-up futur (>20 M vecteurs) : envisager **IVF_PQ** si recall acceptable (>0.85).