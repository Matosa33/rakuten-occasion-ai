# Model Card — tfidf-svm_v1

**Type** : TF-IDF (word 1-2gram + char 3-5gram) + LinearSVC + Platt
**Tâche** : Classification multi-cat (4 cat D-011)

## Inputs / Outputs
- **Input** : Texte brut (titre + description)
- **Output** : P(catégorie | texte) calibré Platt

## Données / Source
- Training data : 3,16M items train, 4 cat D-011

## Performance
- F1_w test = 0.9503, F1_m = 0.9375, ECE = 0.0092

## Limitations
- Pas de sémantique (mots seuls), mais excellent baseline.

## Métriques mesurées (test split)

- **f1_weighted** : 0.9503
- **f1_macro** : 0.9375
- **accuracy** : 0.9503
- **top_1_accuracy** : 0.9503
- **top_3_accuracy** : 0.9985
- **ece** : 0.0092
- **duration_eval_sec** : 110.7000

## Source de vérité métriques

`reports/04_classifiers_bench/tfidf-svm_v1.json`