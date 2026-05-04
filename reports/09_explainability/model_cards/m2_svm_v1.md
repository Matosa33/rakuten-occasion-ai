# Model Card — m2_svm_v1

**Type** : LinearSVC + Platt calibration
**Tâche** : Classification multi-cat (4 cat D-011)

## Inputs / Outputs
- **Input** : Embeddings Arctic Embed L v2 (1024 dim, FP16)
- **Output** : P(catégorie | embedding) calibré Platt

## Données / Source
- Training data : Arctic embed du train

## Limitations
- Hyperparamètre C non tuné (default). Linéaire — pas d'interactions.

## Source de vérité métriques

`reports/04_classifiers_bench/m2_svm_v1.json`