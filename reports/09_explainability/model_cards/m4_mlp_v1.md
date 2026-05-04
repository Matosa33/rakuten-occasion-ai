# Model Card — m4_mlp_v1

**Type** : MLPClassifier hidden=(512, 256), early stopping
**Tâche** : Classification multi-cat (4 cat D-011)

## Inputs / Outputs
- **Input** : Embeddings Arctic Embed L v2 (1024 dim, FP16)
- **Output** : P(catégorie | embedding) softmax

## Données / Source
- Training data : Arctic embed du train

## Limitations
- Boîte noire (peu d'explainability native). Sensible au scaling.

## Source de vérité métriques

`reports/04_classifiers_bench/m4_mlp_v1.json`