# Phase 2 — richesse d'entrée (1 photo < N photos < N + métadonnée)

- **92 produits réels** d'éval · extraction VLM Gemma 4 31B · retrieval + vote A2.
- C3=métadonnée brute FR (sans traduction) ; C3t=métadonnée traduite FR→EN (production)

| Condition | macro_acc | fine_overlap | confiance |
|---|---|---|---|
| C1 — 1 photo | 0.815 | 0.315 | 0.628 |
| C2 — N photos | 0.891 | 0.361 | 0.667 |
| C3 — N + métadonnée brute (FR) | 0.902 | 0.371 | 0.648 |
| **C3t — N + métadonnée traduite (prod)** | 0.848 | 0.340 | 0.651 |

## Gain C3t−C2 (métadonnée traduite) par qualité de métadonnée (`metadata_quality` /5)

| Qualité /5 | gain fine_overlap (C3t−C2) | n |
|---|---|---|
| 0 | +0.000 | 9 |
| 1 | -0.016 | 18 |
| 2 | -0.025 | 14 |
| 3 | -0.036 | 30 |
| 4 | +0.003 | 19 |
| 5 | -0.125 | 2 |

> Lecture : `fine_overlap` = recouvrement breadcrumb réel ↔ prédit. C1→C2 = apport des photos multiples ; C2→C3t = apport de la métadonnée (traduite, conditions production). Le gain stratifié montre si la métadonnée aide ∝ sa qualité.
