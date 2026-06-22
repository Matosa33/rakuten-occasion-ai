# Documentation technique

Un **rapport par thème**. Chaque rapport suit la même structure :

1. **La technologie** — ce que c'est, son rôle dans un système ML/MLOps
2. **État de l'art** — comment l'industrie l'utilise, bonnes pratiques (sourcé)
3. **Notre implémentation** — ce que nous avons fait, où (fichiers, scripts)
4. **Résultats** — chiffres mesurés, reproductibles
5. **Critique** — ce qui est solide, les limites, les écarts vs l'état de l'art
6. **Références** — liens et sources

## Sommaire

| # | Thème | Statut |
|---|---|---|
| 00 | [Vue d'ensemble du système](00_vue_ensemble.md) | ✅ |
| 01 | [Data engineering (audit, nettoyage, split anti-fuite)](01_data_engineering.md) | ✅ |
| 02 | [Représentations vectorielles (embeddings)](02_embeddings.md) | ✅ |
| 03 | [Classification & benchmark de modèles](03_classification_benchmark.md) | ✅ |
| 04 | [Recherche par similarité (FAISS, RRF, OOD, Akinator)](04_retrieval.md) | ✅ |
| 05 | [VLM / LLM ancrés (RAG grounded)](05_vlm_llm_grounded.md) | ✅ |
| 06 | [Estimation de prix transparente](06_pricing.md) | ✅ |
| 07 | [Suivi d'entraînement (MLflow)](07_mlflow_suivi.md) | ✅ |
| 08 | [Registre de modèles & champion/challenger](08_registry_champion_challenger.md) | ✅ |
| 09 | [Orchestration & ré-entraînement (Airflow)](09_airflow_retrain.md) | ✅ |
| 10 | [Détection de dérive (Evidently)](10_drift_evidently.md) | ✅ |
| 11 | [Observabilité (Prometheus, Grafana, logs structurés)](11_observabilite.md) | ✅ |
| 12 | Infrastructure (Docker, Compose, Kubernetes) | ⏳ |
| 13 | CI/CD & sécurité | ⏳ |

> Chaque rapport est construit méthodiquement : recherche documentaire → inventaire de
> notre code → critique état-de-l'art vs réalisé → mise au propre.
