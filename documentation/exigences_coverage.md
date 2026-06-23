# Couverture des exigences — Rakuten AI

> Version 2.0 — 2026-06-13 (resync photo-first + cycles 11-17,.4)
> Statut: matrice de référence pour la soutenance et la planification.
> Croise les **exigences pédagogiques** (51 cours répartis en 16 phases du
> cursus DataScientest) et les **cycles d'implémentation** du projet.

Ce document permet de répondre en une page à: *"Quel cycle du projet livre tel cours ?"* (et inversement). Il est à maintenir à jour quand un cycle change ou qu'un cours est révisé.

---

## 1. Tableau de couverture cours × cycle

| Phase | Cours | Titre | Cycle projet | Statut implémentation |
|---|---|---|---|---|
| **P01 Cadrage + env** | | Le projet en une page | 0.1 | ✅ done (PROJECT.md v2) |
| | | Le poste de dev prêt | 0.2 | 🟡 à valider humain |
| | | Le repo bien né | 0.3 | ✅ done |
| | | système de mémoire projet (optionnel) | 0.4 | ✅ done (9 fichiers + 32 tests) |
| **P02 Données** | | Auditer un dataset brut | **1.1** | ✅ done (puis 4 cat MVP) |
| | | Cleaning + features + split | **1.2** | ✅ done (4d2509b puis b338555 sur 4 cat) |
| | | Anti-leakage 5 patterns | **1.3** | ✅ done (2107cb8) |
| | | Validation Pandera | **1.4** | ✅ done (6ed4393) |
| **P03 Représentations** | | Embeddings concept + similarité | **2.1** | ✅ done |
| | | Vision encoders CLIP/SigLIP | **2.2** | ⏸️ différé (CDN throttling) |
| | | Text encoders Arctic | **2.3** | ✅ done (E2 Arctic, 3,16M vec) |
| **P04 Classification** | | Benchmark 4 classifieurs | **3.1** | ✅ done (M1,M2,M4; M3 skippé) |
| | | TF-IDF + LinearSVC + Platt | **3.2** | ✅ done (M5 F1_w=0.950) |
| | | Métriques évaluation | **3.3** | ✅ done (metrics.py) |
| | | Fusion adaptive multimodale | **3.4** | ✅ done (M6) |
| **P05 Retrieval** | | FAISS vector search | **4.1** | ✅ done (M7 HNSW recall@1=0.948) |
| | | Multi-view + RRF | **4.2** | ✅ done (RRF, top-1 cat %) |
| | | OOD guardrails | **4.3** | ✅ done (3-niveaux + Akinator) |
| **P06 VLM** | | VLM zero-shot | **5.1** | ✅ done (validateur réel `validator.py` + extraction photo) |
| | | Fine-tuning VLM QLoRA | **5.2** (OPTIONNEL F8) | ⏸️ conditional (non déclenché) |
| **P07 LLM/RAG** | | LLMs prompt engineering | **6.1** | ✅ done (prompt templates) |
| | | RAG grounding | **6.2** | ✅ done (E4 Gemma, grounding description) |
| **P08 Pricing** | | Pricing algorithmique | **7.1** | ✅ done (M8 cascade L1-L4) |
| **P09 Explainability** | | SHAP + t-SNE + Model Cards | **8.1** | ✅ done (12 cards + t-SNE) |
| **P10 API** | | FastAPI async | **9.1** | ✅ done |
| | | Pydantic v2 | **9.2** | ✅ done |
| | | Async I/O patterns | **9.3** | ✅ done (OpenRouter + to_thread) |
| | | SSE streaming | **9.4** | ✅ done (/identify/stream) |
| | | SQLAlchemy sessions | **9.5** | ✅ done (persistence + /history) |
| **P11 Frontend** | | React Vite Tailwind | **10.1** | ✅ done |
| | | UX progressive neuro-marketing | **10.2** | ✅ done (Zeigarnik/Hick/Anchoring/IKEA) |
| | | Mode batch queue localStorage | **10.3** | ✅ done (mode « mitrailler ») |
| **P12 MLOps tracking** | | MLflow tracking | **11.1** | ✅ done (7 runs M1-M8) |
| | | MLflow Registry + hot reload | **11.2** | ✅ done (@Production=M5) |
| | | DVC pipelines | **11.3** | ✅ done (dvc.yaml DAG 4 stages) |
| **P13 MLOps orchestration** | | Airflow DAGs | **12.1** | ✅ done (DAG rakuten_retrain) |
| | | BentoML serving | **12.2** | ✅ done (import Registry @Production) |
| | | Boucle MLOps fermée | **12.3** | ✅ done (champion/challenger, retrains réels v4/v5) |
| **P14 Infra** | | Docker multi-stage CUDA | **13.1** | ✅ done (API + Frontend multi-stage) |
| | | Docker Compose profiles | **13.2** | ✅ done (stack unifiée 14 services) |
| | | Traefik gateway | **13.3** | ✅ done (entrée *.localhost) |
| | | MinIO S3 | **13.4** | ✅ done (artefacts MLflow) |
| | | Kubernetes core | **13.5** | ✅ done (kind + ingress-nginx) |
| **P15 Observabilité** | | structlog logging | **14.1** | ✅ done (JSON + request_id) |
| | | Prometheus + PromQL | **14.2** | ✅ done (4 golden signals) |
| | | Grafana dashboards | **14.3** | ✅ done (3 dashboards) |
| | | Evidently drift | **14.4** | ✅ done (drift D1-D4) |
| **P16 Production-grade** | | JWT auth + rate limit | **15.1** | ✅ done (JWT HS256) |
| | | GitHub Actions + GHCR | **15.2** | ✅ done (2 workflows) |
| | | Tests intégration + sécurité | **15.3** | ✅ done (326 tests, pip-audit) |
| | | Soutenance défense | **15.4** | ✅ done (script + slides + checklist + feuille de test) |

**51 cours / 51 répartis sur 16 cycles. Statut global: ~48 / 51 implémentés (~94 %)** au 2026-06-13 (Cycles 0-17 faits, pipeline photo-first complet). **Restent**: poste dev (validation humaine), indexation visuelle SigLIP (gated), fine-tuning QLoRA (conditionnel F8). Différés assumés, pas oubliés.

> ⚠️ Cette table (cours pédagogiques -) est secondaire. **Sources de vérité du statut**:
> le plan projet (table d'ensemble des 16 cycles) + `exigences_fonctionnelles.md` (état réel F0-F8).
> Statuts cours détaillés ci-dessous re-synchronisés au fil des RESTIT.

---

## 2. Couverture inverse — Cycle × cours livrés

| Cycle | Phase projet | Cours couverts | Livrables principaux |
|---|---|---|---|
| 0 | Bootstrap | - | repo + mémoire projet + conventions |
| 1 | Données (P02) | - | audit + cleaning + anti-leakage + Pandera |
| 2 | Encoders (P03) | - | SigLIP + Arctic + indices |
| 3 | Classification (P04) | - | M1-M6 + métriques |
| 4 | Retrieval (P05) | - | M7 FAISS + RRF + OOD + Akinator |
| 5 | VLM (P06) | - | E3 + M9 optionnel |
| 6 | LLM/RAG (P07) | - | E4 prompt + RAG grounding |
| 7 | Pricing (P08) | | M8 algorithmique |
| 8 | Explain (P09) | | SHAP + t-SNE + Model Cards M1-M8 |
| 9 | API (P10) | - | FastAPI complet |
| 10 | Frontend (P11) | - | React + UX + batch |
| 11 | MLOps tracking (P12) | - | MLflow + DVC |
| 12 | MLOps orchestration (P13) | - | Airflow + BentoML + closed loop |
| 13 | Infra (P14) | - | Docker + Compose + Traefik + MinIO + K8s |
| 14 | Observabilité (P15) | - | structlog + Prometheus + Grafana + Evidently |
| 15 | Production-grade (P16) | - | JWT + CI/CD + tests + soutenance |

**Vérification: aucun cours orphelin, aucun cycle sans cours associé.** ✅

---

## 3. Couverture par exigence MLOps explicite

> Le cursus DataScientest exige une couverture complète des "MLOps sprints 17-20" (cf. `PROJECT.md` §8 stakeholders). Cette section vérifie chaque exigence MLOps.

| Exigence MLOps | Cours couvrants | Cycle projet | Modèle / artefact |
|---|---|---|---|
| **Tracking expériences** | MLflow tracking | 11.1 | tous M1-M9 + métadonnées encodage E1-E2 |
| **Versioning modèles** | MLflow Registry | 11.2 | M1-M8 alias `@Production` |
| **Versioning données** | DVC pipelines | 11.3 | data/raw/full + processed + embeddings |
| **Orchestration** | Airflow DAGs | 12.1 | retrain hebdo cleaning→encoders→train→eval |
| **Serving + métriques** | BentoML | 12.2 | API M1-M8 avec Prometheus natif |
| **Closed-loop auto** | Boucle MLOps | 12.3 | drift → retrain → register → promote → reload |
| **Containerisation** | Docker multi-stage | 13.1 | Dockerfile.api + Dockerfile.frontend (CUDA) |
| **Compose dev/prod** | Docker Compose | 13.2 | services + profiles |
| **Reverse proxy + TLS** | Traefik | 13.3 | gateway + middlewares + rate-limit |
| **Object storage** | MinIO | 13.4 | DVC remote + MLflow artifacts |
| **Orchestration container** | Kubernetes | 13.5 | Pod + Deployment + Service + HPA |
| **Logs structurés** | structlog | 14.1 | JSON + correlation IDs |
| **Métriques infra** | Prometheus | 14.2 | 4 golden signals |
| **Dashboards** | Grafana | 14.3 | dashboards par modèle + golden signals |
| **Drift détection** | Evidently | 14.4 | D1 cat / D2 emb / D3 conf / D4 MAPE |
| **CI/CD** | GitHub Actions GHCR | 15.2 | build + tests + push GHCR |
| **Tests E2E + sécu** | tests intégration | 15.3 | pytest E2E + bandit/safety |

**Total: 17 exigences MLOps couvertes par 17 cours répartis sur les cycles 11-15.** ✅

---

## 4. Modèles ML monitorés en production

> Référencer `03_classification_benchmark.md` pour les fiches détaillées. Cette section liste juste **ce qui sera monitoré en prod**.

| Modèle | Métriques monitorées | Stack monitoring | Action si dérive |
|---|---|---|---|
| M1 k-NN | F1, latence | MLflow + Prometheus | retrain Airflow |
| M2-M4 | F1, ECE | MLflow | retrain Airflow |
| M5 TF-IDF | F1, ECE | MLflow | retrain |
| M6 Fusion | F1 fusion | MLflow + ablation | re-grid α |
| M7 FAISS | Recall@5, latence P95 | Prometheus + Grafana | rebuild index |
| M8 Pricing | MAPE par niveau, couverture | Prometheus + Grafana | recalibrer dépréciation |
| E1 SigLIP | drift D2 embeddings | Evidently | re-snapshot baseline |
| E2 Arctic | drift D2 (texte) | Evidently | re-snapshot baseline |
| E3 VLM | parse rate, taux hallu | MLflow logs | switch VLM provider |
| E4 LLM | BLEU drift | MLflow + feedback | switch LLM provider |

**Total: 10 modèles avec drift monitoring continu.** ✅

---

## 5. Ce qui est explicitement HORS-SCOPE

> Référencer `PROJECT.md` §6 pour le détail. Rappel rapide:

- ❌ Pricing par ML supervisé (algorithmique seul, M8)
- ❌ Fine-tuning LLM texte pur
- ❌ Re-entraînement vision encoder (SigLIP frozen)
- ❌ App mobile native (React responsive web)
- ❌ Intégration API Rakuten réelle
- ❌ Multi-langue UI (FR uniquement)
- ❌ Auth IAM réelle (JWT stub démo)
- ❌ Scraping Rakuten/Vinted/Leboncoin (proxy Amazon)
- ❌ Live video stream temps réel (mode "stable shot" + photo statique)
- ❌ Fine-tuning VLM dans scope nominal (F8 OPTIONNEL conditionné)

---

## 6. Convention de mise à jour

Quand un cycle est complété:
1. Cocher le statut dans la colonne "Statut implémentation" de la table §1.
2. Référencer le commit hash dans l'état du projet historique.
3. Si un cours change de cycle (refactoring), mettre à jour les §1 et §2.
4. Si une exigence MLOps n'est pas couverte, lever une alerte dans l'état du projet "Blockers".

Ce document est **maintenu par l'agent IA** lors des phases RESTIT (. les du projet règle 9).
