# Comparaison d'extracteurs VLM — condition C2 (N photos)

- **93 produits** · métriques dures · cache keyé par modèle.

| Extracteur | entity_match | leaf_exact | completeness | macro_acc | mean_latency_s | price_usd_per_mtok_in |
|---|---|---|---|---|---|---|
| google/gemma-4-31b-it | 0.8065 | 0.2151 | 0.7015 | 0.8817 | 6.71 | 0.12 |
| xiaomi/mimo-v2.5 | 0.8065 | 0.2151 | 0.7236 | 0.8602 | 2.25 | 0.105 |
| google/gemini-2.5-flash-lite | 0.8387 | 0.2043 | 0.6729 | 0.8495 | 2.13 | 0.1 |
| qwen/qwen3.5-flash-02-23 | 0.8172 | 0.2043 | 0.7452 | 0.871 | 4.1 | 0.065 |

> `entity_match` = identification du bon produit ; `completeness` = remplissage ;
> `mean_latency_s` = latence moyenne d'extraction ; prix = $/Mtok entrée.
