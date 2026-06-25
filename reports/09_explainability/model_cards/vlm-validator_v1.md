# Model Card — vlm-validator_v1

**Type** : VLM frontier zero-shot (Gemini 2.0 Flash via OpenRouter)
**Tâche** : Validation matching produit (image vendeur ↔ candidat retrieval)

## Inputs / Outputs
- **Input** : (query_image, candidate_image, candidate_meta)
- **Output** : JSON {match: bool, confidence: 0-1, reason: str}

## Données / Source
- Source : google/gemini-2.0-flash-exp via OpenRouter

## Limitations
- Coût API ~ $0.0001/call. Latence ~ 1-3 s. Stub mock en attendant Cycle 9.

## Source de vérité métriques

`reports/04_classifiers_bench/vlm-validator_v1.json`