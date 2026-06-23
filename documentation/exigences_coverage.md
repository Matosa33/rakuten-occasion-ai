# Couverture du projet vs les exigences attendues

> Cette page répond en un coup d'œil à : *« le projet couvre-t-il bien tout ce qui est
> attendu ? »*. Elle croise les **4 phases** du cahier des charges avec **ce qui est réellement
> livré dans le dépôt** (fichiers + rapport détaillé correspondant).

Pour la traçabilité **fonctionnelle** (besoins produit F0-F8), voir
[exigences_fonctionnelles.md](exigences_fonctionnelles.md).

---

## 1. Couverture des 4 phases

### Phase 1 — Fondations & conteneurisation
| Étape attendue | Statut | Où c'est livré |
|---|---|---|
| Cadrage du projet + indicateurs clés | ✅ | [PROJECT.md](PROJECT.md) (besoin, hypothèses, KPIs) |
| Environnement de dev reproductible | ✅ | `pyproject.toml` (extras), `.venv`, `Makefile`, mêmes versions rejouées en CI |
| Collecte + traitement des données | ✅ | `src/data/` (audit → nettoyage → split) — rapport [01](01_data_engineering.md) |
| Entraînement + évaluation des modèles | ✅ | `src/classifiers/` (train) + `metrics.py` (éval) — rapport [03](03_classification_benchmark.md) |
| API d'inférence | ✅ | `src/api/main.py` (FastAPI) — rapport [14](14_api_orchestration.md) |

### Phase 2 — Microservices, tracking & versionnement
| Étape attendue | Statut | Où c'est livré |
|---|---|---|
| Suivi des expériences (MLflow) | ✅ | `src/mlops/`, runs + Registry — rapport [07](07_mlflow_suivi.md) |
| Versionnement des **données** et des **modèles** | ✅ | DVC (`dvc.yaml`) pour les données + MLflow Registry pour les modèles — rapports [07](07_mlflow_suivi.md)/[08](08_registry_champion_challenger.md) |
| Décomposition en micro-services + orchestration | ✅ | `docker-compose.yml` (14 services) — rapport [12](12_infra.md) |

### Phase 3 — Orchestration & déploiement
| Étape attendue | Statut | Où c'est livré |
|---|---|---|
| Pipeline de ré-entraînement de bout en bout (Airflow) | ✅ | `infra/airflow/dags/` (boucle 5 étapes) — rapport [09](09_airflow_retrain.md) |
| Pipeline CI + tests unitaires | ✅ | `.github/workflows/ci.yml` (lint, 326 tests, audit, build) — rapport [13](13_cicd_securite.md) |
| API optimisée et **sécurisée** | ✅ | JWT, anti-path-traversal, capability-URL, async — rapports [13](13_cicd_securite.md)/[14](14_api_orchestration.md) |
| Scalabilité Docker / Kubernetes | ✅ | `infra/k8s/` (Deployments, StatefulSets, ingress, **HPA**, kind) — rapport [12](12_infra.md) |

### Phase 4 — Monitoring & maintenance
| Étape attendue | Statut | Où c'est livré |
|---|---|---|
| Monitoring perfs (Prometheus / Grafana) | ✅ | 4 golden signals + 3 dashboards — rapport [11](11_observabilite.md) |
| Détection de dérive (Evidently) | ✅ | `src/monitoring/drift_detection.py` + DAG drift — rapport [10](10_drift_evidently.md) |
| Pipelines de mise à jour automatisées | ✅ | boucle Airflow retrain + champion/challenger + publication d'images versionnées — rapports [08](08_registry_champion_challenger.md)/[09](09_airflow_retrain.md)/[13](13_cicd_securite.md) |
| Documentation technique + présentation/démo | ✅ | ce dossier `documentation/` (17 rapports) + **démo via le frontend React** — rapport [15](15_frontend_ux.md) |

> **Deux nuances à assumer en présentation** :
> 1. Les scripts de données et d'entraînement sont **numérotés** (`01_load_full.py`,
>    `01_tfidf_linsvc.py`…) plutôt que nommés `collect.py`/`train.py` — convention « le pipeline
>    se lit dans l'ordre des fichiers », fonctionnellement équivalent.
> 2. La présentation/démo s'appuie sur un **frontend React** (vraie UI produit) plutôt que sur
>    Streamlit (cité comme exemple dans le cahier des charges) — choix plus proche d'un produit réel.

---

## 2. Couverture MLOps détaillée

| Exigence MLOps | Comment on la couvre | Preuve |
|---|---|---|
| Suivi des expériences | MLflow (runs : paramètres, métriques, artefacts) | rapport [07](07_mlflow_suivi.md) |
| Versionnement des modèles | MLflow Registry + alias `@Production` | rapport [08](08_registry_champion_challenger.md) |
| Versionnement des données | DVC (pipeline reproductible) | `dvc.yaml` |
| Orchestration | Airflow (DAG de ré-entraînement) | rapport [09](09_airflow_retrain.md) |
| Serving + métriques | BentoML + Prometheus | rapports [08](08_registry_champion_challenger.md)/[11](11_observabilite.md) |
| Boucle fermée automatique | dérive → ré-entraînement → évaluation → promotion → re-déploiement | rapports [09](09_airflow_retrain.md)/[10](10_drift_evidently.md) |
| Conteneurisation | Docker multi-stage | rapport [12](12_infra.md) |
| Orchestration locale + prod | Docker Compose (base + overlay prod) | rapport [12](12_infra.md) |
| Reverse proxy | Traefik (gateway + rate-limit) | rapport [12](12_infra.md) |
| Stockage objet | MinIO (artefacts MLflow, remote DVC) | rapport [12](12_infra.md) |
| Orchestration conteneurs | Kubernetes (Deployments + HPA, sur kind) | rapport [12](12_infra.md) |
| Logs structurés | structlog (JSON + `request_id`) | rapport [11](11_observabilite.md) |
| Métriques + dashboards | Prometheus + Grafana (4 golden signals) | rapport [11](11_observabilite.md) |
| Détection de dérive | Evidently (`DataDriftPreset`) | rapport [10](10_drift_evidently.md) |
| CI/CD | GitHub Actions + publication GHCR (semver) | rapport [13](13_cicd_securite.md) |
| Tests d'intégration + sécurité | 326 tests + `pip-audit` | rapport [13](13_cicd_securite.md) |

---

## 3. Modèles surveillés en production

| Modèle | Métriques suivies | Stack de monitoring | Action en cas de dérive |
|---|---|---|---|
| M1 k-NN | F1, latence | MLflow + Prometheus | ré-entraînement Airflow |
| M2 SVM / M4 MLP | F1, calibration (ECE) | MLflow | ré-entraînement Airflow |
| M5 TF-IDF (servi) | F1, calibration (ECE) | MLflow | ré-entraînement |
| M6 Fusion | F1 de fusion | MLflow | re-réglage des poids |
| M7 FAISS (retrieval) | recall, latence p95 | Prometheus + Grafana | reconstruction de l'index |
| M8 Pricing | MAPE par niveau, couverture | Prometheus + Grafana | recalibrer la dépréciation |
| E2 Arctic (texte) | dérive des embeddings | Evidently | re-figer la référence |
| E3 VLM (validateur) | taux de parsing, hallucinations | logs MLflow | changer de fournisseur VLM |
| E4 LLM (rédacteur) | qualité de rédaction | logs MLflow + retours | changer de fournisseur LLM |

---

## 4. Ce qui est explicitement hors-scope (assumé, pas oublié)

Voir [PROJECT.md](PROJECT.md) pour le détail. Rappel :

- ❌ Pricing par ML supervisé (on fait de l'algorithmique transparente, cf. rapport [06](06_pricing.md))
- ❌ Ré-entraînement de l'encodeur vision (SigLIP utilisé gelé)
- ❌ Application mobile native (web responsive)
- ❌ Intégration à l'API Rakuten réelle (on utilise Amazon comme proxy)
- ❌ Interface multilingue (FR uniquement)
- ❌ Authentification d'entreprise (JWT en mode démo)
- ❌ Indexation visuelle directe du catalogue (SigLIP) — différée
- ❌ Fine-tuning du VLM (optionnel, non déclenché)
