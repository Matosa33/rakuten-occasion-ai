# Model Card — m1_knn_v1

**Type** : k-NN cosine weighted
**Tâche** : Classification multi-cat (4 cat D-011)

## Inputs / Outputs
- **Input** : Embeddings Arctic Embed L v2 (1024 dim, FP16)
- **Output** : P(catégorie | embedding) via vote pondéré k voisins

## Données / Source
- Training data : Arctic embed du train (3,16M items, 4 cat D-011)

## Limitations
- Lent en inférence (k voisins par query). Pas de calibration native.

## Métriques mesurées (test split)

- **f1_weighted** : 0.9537
- **f1_macro** : 0.9415
- **accuracy** : 0.9537
- **top_1_accuracy** : 0.9537
- **top_3_accuracy** : 0.9881
- **ece** : 0.0069
- **duration_eval_sec** : 142.4000

## Source de vérité métriques

`reports/04_classifiers_bench/m1_knn_v1.json`