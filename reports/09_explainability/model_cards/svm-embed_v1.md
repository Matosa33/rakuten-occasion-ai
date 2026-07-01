# Model Card - svm-embed_v1

**Type** : LinearSVC + Platt calibration
**Tâche** : Classification multi-catégories (4 catégories)

## Inputs / Outputs
- **Input** : Embeddings Arctic Embed L v2 (1024 dim, FP16)
- **Output** : P(catégorie | embedding) calibré Platt

## Données / Source
- Training data : Arctic embed du train

## Limitations
- Hyperparamètre C non tuné (default). Linéaire - pas d'interactions.

## Métriques mesurées (test split)

- **f1_weighted** : 0.9311
- **f1_macro** : 0.9193
- **accuracy** : 0.9312
- **top_1_accuracy** : 0.9312
- **top_3_accuracy** : 0.9977
- **ece** : 0.0145
- **duration_eval_sec** : 23.88 (test)

## Source de vérité métriques

`reports/04_classifiers_bench/m2_svm_v1.json`