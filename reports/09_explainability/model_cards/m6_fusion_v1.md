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

## Source de vérité métriques

`reports/04_classifiers_bench/m6_fusion_v1.json`