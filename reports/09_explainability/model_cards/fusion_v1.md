# Model Card — fusion_v1

**Type** : Fusion adaptive (moyenne pondérée probas)
**Tâche** : Classification multi-catégories (4 catégories)

## Inputs / Outputs
- **Input** : Probas calibrées de svm-embed/rf-embed/mlp-embed/tfidf-svm
- **Output** : P(catégorie | inputs) fusionnée par α appris

## Données / Source
- Training data : Probas val svm-embed à tfidf-svm, grid search α

## Limitations
- Coût inférence = 4× modèle individuel. À adopter uniquement si gain > +0.02 F1_w.

## Métriques mesurées (test split)

- **f1_weighted** : 0.9522
- **f1_macro** : 0.9418
- **accuracy** : 0.9522
- **top_1_accuracy** : 0.9522
- **top_3_accuracy** : 0.9990
- **ece** : 0.0230

## Source de vérité métriques

`reports/04_classifiers_bench/fusion_v1.json`