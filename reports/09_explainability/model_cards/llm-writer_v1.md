# Model Card — llm-writer_v1

**Type** : LLM frontier rédacteur grounded (Gemini Flash via OpenRouter)
**Tâche** : Génération titre + description annonce vendeur particulier

## Inputs / Outputs
- **Input** : (product_meta, top-N grounding sentences from reviews)
- **Output** : JSON {title, description}

## Données / Source
- Source : google/gemini-2.0-flash-exp via OpenRouter

## Limitations
- Risque hallucination si grounding pauvre. Stub mock en Cycle 6.2.

## Source de vérité métriques

`reports/04_classifiers_bench/llm-writer_v1.json`