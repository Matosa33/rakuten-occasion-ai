# Documentation

**Toute la documentation du projet est ici, dans ce seul dossier.**

## Par où commencer
1. **[PROJECT.md](PROJECT.md)** — le **cadrage produit** : besoin, hypothèses, exigences F0-F8, hors-scope.
2. **[00_vue_ensemble.md](00_vue_ensemble.md)** — le **système en un coup d'œil** (le pipeline).
3. Puis les **rapports par thème** ci-dessous (lisibles indépendamment).

> 📖 Bloqué sur un terme ? Le **[GLOSSAIRE](GLOSSAIRE.md)** définit tout le jargon en une ligne.

Chaque rapport thématique suit la même structure : **la techno et son rôle → état de l'art →
notre implémentation (fichiers, paramètres réels) → résultats mesurés → critique et limites →
références**.

## Sommaire — rapports par thème

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
| 12 | [Infrastructure (Docker, Compose, Kubernetes)](12_infra.md) | ✅ |
| 13 | [CI/CD & sécurité](13_cicd_securite.md) | ✅ |
| 14 | [API & orchestration runtime](14_api_orchestration.md) | ✅ |
| 15 | [Frontend & UX vendeur](15_frontend_ux.md) | ✅ |
| 16 | [Explainability & interprétabilité](16_explainability.md) | ✅ |

> **Couches applicatives** (14-16) : l'API qui câble le pipeline, le frontend vendeur et
> l'explainability — chacune avec son rapport dédié.

## Cadrage & traçabilité
| Document | Rôle |
|---|---|
| [PROJECT.md](PROJECT.md) | Cadrage produit : besoin, hypothèses, exigences F0-F8, hors-scope |
| [exigences_fonctionnelles.md](exigences_fonctionnelles.md) | Traçabilité exigence F0-F8 → état réel → gap |
| [exigences_coverage.md](exigences_coverage.md) | Traçabilité compétences/cours → implémentation |
| [GLOSSAIRE.md](GLOSSAIRE.md) | Tout le jargon en une ligne |
