# Phase 2 — richesse d'entrée (1 photo < N photos < N + métadonnée)

- **92 produits réels** d'éval · extraction VLM Gemma 4 31B · retrieval + vote knn-vote.
- multi-photo-meta=métadonnée brute FR (sans traduction) ; multi-photo-meta-fr-en=métadonnée traduite FR→EN (production)

| Condition | macro_acc | fine_overlap | confiance |
|---|---|---|---|
| one-photo — 1 photo | 0.815 | 0.315 | 0.628 |
| multi-photo — N photos | 0.891 | 0.361 | 0.667 |
| multi-photo-meta — N + métadonnée brute (FR) | 0.902 | 0.371 | 0.648 |
| **multi-photo-meta-fr-en — N + métadonnée traduite (prod)** | 0.848 | 0.340 | 0.651 |

## Gain multi-photo-metat−multi-photo (métadonnée traduite) par qualité de métadonnée (`metadata_quality` /5)

| Qualité /5 | gain fine_overlap (multi-photo-metat−multi-photo) | n |
|---|---|---|
| 0 | +0.000 | 9 |
| 1 | -0.016 | 18 |
| 2 | -0.025 | 14 |
| 3 | -0.036 | 30 |
| 4 | +0.003 | 19 |
| 5 | -0.125 | 2 |

> Lecture : `fine_overlap` = recouvrement breadcrumb réel ↔ prédit. one-photo→multi-photo = apport des photos multiples ; multi-photo→multi-photo-meta-fr-en = apport de la métadonnée (traduite, conditions production). Le gain stratifié montre si la métadonnée aide ∝ sa qualité.
