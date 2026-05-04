# Model Card — m3_rf_v1

**Type** : RandomForest (300 estimators, max_depth=20)
**Tâche** : Classification multi-cat (4 cat D-011)

## Inputs / Outputs
- **Input** : Embeddings Arctic Embed L v2 (1024 dim, FP16)
- **Output** : P(catégorie | embedding) via vote arbres

## Données / Source
- Training data : Arctic embed du train

## Limitations
- RAM-intensive (~2 GB). Pas le meilleur F1 mais explicable via SHAP.

## Source de vérité métriques

`reports/04_classifiers_bench/m3_rf_v1.json`