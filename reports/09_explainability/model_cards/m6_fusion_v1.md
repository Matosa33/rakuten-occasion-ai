# Model Card — m6_fusion_v1

**Type** : Fusion adaptive (moyenne pondérée probas)
**Tâche** : Classification multi-cat (4 cat D-011)

## Inputs / Outputs
- **Input** : Probas calibrées de M2/M3/M4/M5
- **Output** : P(catégorie | inputs) fusionnée par α appris

## Données / Source
- Training data : Probas val M2-M5, grid search α

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

`reports/04_classifiers_bench/m6_fusion_v1.json`