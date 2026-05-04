# Model Card — m8_pricing_v1

**Type** : Algorithmique cascade L1-L4 (transparent, pas de ML)
**Tâche** : Suggestion prix indicatif + niveau confiance

## Inputs / Outputs
- **Input** : (catalog_price, knn_neighbors_prices, category_median, condition, age, category)
- **Output** : PricingResult{suggested_price, confidence_level, range_low/high, explanation}

## Données / Source
- Training data : Médianes catégorie calculées sur train

## Limitations
- Dépréciation linéaire (vs réelle = courbe). Pas d'effets temporels (saisonnalité).

## Source de vérité métriques

`reports/04_classifiers_bench/m8_pricing_v1.json`