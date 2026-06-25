# Model Card — arctic_v1

**Type** : Snowflake Arctic Embed L v2 (frozen, 1024 dim, multilingue XLM-RoBERTa-large)
**Tâche** : Encodage texte → embedding L2-normalized

## Inputs / Outputs
- **Input** : Texte (titre + description), max_seq=256 tokens
- **Output** : Embedding 1024 dim FP16

## Données / Source
- Source : Snowflake/snowflake-arctic-embed-l-v2.0

## Limitations
- Frozen. max_seq=256 = trade-off vitesse (4× plus rapide que 512).

## Source de vérité métriques

`reports/04_classifiers_bench/arctic_v1.json`