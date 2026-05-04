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

## Métriques mesurées (test split)

- **f1_weighted** : 0.9489
- **f1_macro** : 0.9382
- **accuracy** : 0.9489
- **top_1_accuracy** : 0.9489
- **top_3_accuracy** : 0.9989
- **ece** : 0.0013
- **duration_eval_sec** : 18.8800

## Source de vérité métriques

`reports/04_classifiers_bench/m4_mlp_v1.json`