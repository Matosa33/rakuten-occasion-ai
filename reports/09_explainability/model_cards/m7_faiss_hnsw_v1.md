# Model Card — m7_faiss_hnsw_v1

**Type** : FAISS HNSW (M=32, efConstruction=200, efSearch=64)
**Tâche** : Recherche similarité produit (k-NN top-K)

## Inputs / Outputs
- **Input** : Embedding query (Arctic 1024 dim)
- **Output** : Top-K indices voisins + scores cosine

## Données / Source
- Training data : Index sur 3,16M items train

## Limitations
- Approximate (recall ~95-98 %). À comparer Flat IP en référence.

## Source de vérité métriques

`reports/04_classifiers_bench/m7_faiss_hnsw_v1.json`