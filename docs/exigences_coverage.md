# Couverture des exigences — Rakuten AI

> Version 1.0 — 2026-04-30
> Statut : matrice de référence pour la soutenance et la planification.
> Croise les **exigences pédagogiques** (51 cours répartis en 16 phases du
> cursus DataScientest) et les **cycles d'implémentation** du projet.

Ce document permet de répondre en une page à : *"Quel cycle du projet livre tel cours ?"* (et inversement). Il est à maintenir à jour quand un cycle change ou qu'un cours est révisé.

---

## 1. Tableau de couverture cours × cycle

| Phase | Cours | Titre | Cycle projet | Statut implémentation |
|---|---|---|---|---|
| **P01 Cadrage + env** | C01 | Le projet en une page | 0.1 | ✅ done (PROJECT.md v2 D-010) |
| | C02 | Le poste de dev prêt | 0.2 | 🟡 à valider humain |
| | C03 | Le repo bien né | 0.3 | ✅ done |
| | C04 | BRAIN system (optionnel) | 0.4 | ✅ done (9 fichiers + 32 tests) |
| **P02 Données** | C05 | Auditer un dataset brut | **1.1** | ✅ done (D-008 puis D-011 4 cat MVP) |
| | C06 | Cleaning + features + split | **1.2** | ✅ done (4d2509b puis b338555 sur 4 cat) |
| | C07 | Anti-leakage 5 patterns | **1.3** | ✅ done (2107cb8) |
| | C08 | Validation Pandera | **1.4** | ✅ done (6ed4393) |
| **P03 Représentations** | C09 | Embeddings concept + similarité | **2.1** | ✅ done |
| | C10 | Vision encoders CLIP/SigLIP | **2.2** | ⏸️ différé D-014 (CDN throttling) |
| | C11 | Text encoders Arctic | **2.3** | ✅ done (E2 Arctic, 3,16M vec) |
| **P04 Classification** | C12 | Benchmark 4 classifieurs | **3.1** | ✅ done (M1,M2,M4 ; M3 skippé D-015) |
| | C13 | TF-IDF + LinearSVC + Platt | **3.2** | ✅ done (M5 F1_w=0.950) |
| | C14 | Métriques évaluation | **3.3** | ✅ done (metrics.py) |
| | C15 | Fusion adaptive multimodale | **3.4** | ✅ done (M6) |
| **P05 Retrieval** | C16 | FAISS vector search | **4.1** | ✅ done (M7 HNSW recall@1=0.948) |
| | C17 | Multi-view + RRF | **4.2** | ✅ done (text-only mono-view) |
| | C18 | OOD guardrails | **4.3** | ✅ done (3-niveaux D-017 + Akinator) |
| **P06 VLM** | C19 | VLM zero-shot | **5.1** | 🟡 mock (réel gated vision D-014) |
| | C20 | Fine-tuning VLM QLoRA | **5.2** (OPTIONNEL F8) | ⏸️ conditional (non déclenché) |
| **P07 LLM/RAG** | C21 | LLMs prompt engineering | **6.1** | ✅ done (prompt templates) |
| | C22 | RAG grounding | **6.2** | ✅ done (E4 Gemma, grounding description) |
| **P08 Pricing** | C23 | Pricing algorithmique | **7.1** | ✅ done (M8 cascade L1-L4) |
| **P09 Explainability** | C24 | SHAP + t-SNE + Model Cards | **8.1** | ✅ done (12 cards + t-SNE) |
| **P10 API** | C25 | FastAPI async | **9.1** | ✅ done |
| | C26 | Pydantic v2 | **9.2** | ✅ done |
| | C27 | Async I/O patterns | **9.3** | ✅ done (OpenRouter + to_thread) |
| | C28 | SSE streaming | **9.4** | ✅ done (/identify/stream) |
| | C29 | SQLAlchemy sessions | **9.5** | ✅ done (persistence + /history) |
| **P11 Frontend** | C30 | React Vite Tailwind | **10.1** | ✅ done |
| | C31 | UX progressive neuro-marketing | **10.2** | ✅ done (Zeigarnik/Hick/Anchoring/IKEA) |
| | C32 | Mode batch queue localStorage | **10.3** | ⏸️ différé D-016 (dépend vision) |
| **P12 MLOps tracking** | C33 | MLflow tracking | **11.1** | ✅ done (7 runs M1-M8) |
| | C34 | MLflow Registry + hot reload | **11.2** | ✅ done (@Production=M5, D-020) |
| | C35 | DVC pipelines | **11.3** | ✅ done (dvc.yaml DAG 4 stages) |
| **P13 MLOps orchestration** | C36 | Airflow DAGs | **12.1** | not_started |
| | C37 | BentoML serving | **12.2** | not_started |
| | C38 | Boucle MLOps fermée | **12.3** | not_started |
| **P14 Infra** | C39 | Docker multi-stage CUDA | **13.1** | not_started |
| | C40 | Docker Compose profiles | **13.2** | not_started |
| | C41 | Traefik gateway | **13.3** | not_started |
| | C42 | MinIO S3 | **13.4** | not_started |
| | C43 | Kubernetes core | **13.5** | not_started |
| **P15 Observabilité** | C44 | structlog logging | **14.1** | not_started |
| | C45 | Prometheus + PromQL | **14.2** | not_started |
| | C46 | Grafana dashboards | **14.3** | not_started |
| | C47 | Evidently drift | **14.4** | not_started (D1-D4) |
| **P16 Production-grade** | C48 | JWT auth + rate limit | **15.1** | not_started |
| | C49 | GitHub Actions + GHCR | **15.2** | not_started |
| | C50 | Tests intégration + sécurité | **15.3** | not_started |
| | C51 | Soutenance défense | **15.4** | not_started |

**51 cours / 51 répartis sur 16 cycles. Statut global : ~33 / 51 implémentés (~65 %)** au 2026-05-21 (Cycles 0-10 faits, hors différés D-014/D-015/D-016 ; Cycles 11-15 à venir).

> ⚠️ Cette table (cours pédagogiques C01-C51) est secondaire. **Sources de vérité du statut** :
> `BRAIN/to-do.md` (table d'ensemble des 16 cycles) + `docs/exigences_fonctionnelles.md` (état réel F0-F8).
> Statuts cours détaillés ci-dessous re-synchronisés au fil des RESTIT.

---

## 2. Couverture inverse — Cycle × cours livrés

| Cycle | Phase projet | Cours couverts | Livrables principaux |
|---|---|---|---|
| 0 | Bootstrap | C01-C04 | repo + BRAIN + conventions |
| 1 | Données (P02) | C05-C08 | audit + cleaning + anti-leakage + Pandera |
| 2 | Encoders (P03) | C09-C11 | SigLIP + Arctic + indices |
| 3 | Classification (P04) | C12-C15 | M1-M6 + métriques |
| 4 | Retrieval (P05) | C16-C18 | M7 FAISS + RRF + OOD + Akinator |
| 5 | VLM (P06) | C19-C20 | E3 + M9 optionnel |
| 6 | LLM/RAG (P07) | C21-C22 | E4 prompt + RAG grounding |
| 7 | Pricing (P08) | C23 | M8 algorithmique |
| 8 | Explain (P09) | C24 | SHAP + t-SNE + Model Cards M1-M8 |
| 9 | API (P10) | C25-C29 | FastAPI complet |
| 10 | Frontend (P11) | C30-C32 | React + UX + batch |
| 11 | MLOps tracking (P12) | C33-C35 | MLflow + DVC |
| 12 | MLOps orchestration (P13) | C36-C38 | Airflow + BentoML + closed loop |
| 13 | Infra (P14) | C39-C43 | Docker + Compose + Traefik + MinIO + K8s |
| 14 | Observabilité (P15) | C44-C47 | structlog + Prometheus + Grafana + Evidently |
| 15 | Production-grade (P16) | C48-C51 | JWT + CI/CD + tests + soutenance |

**Vérification : aucun cours orphelin, aucun cycle sans cours associé.** ✅

---

## 3. Couverture par exigence MLOps explicite

> Le cursus DataScientest exige une couverture complète des "MLOps sprints 17-20" (cf. `docs/PROJECT.md` §8 stakeholders). Cette section vérifie chaque exigence MLOps.

| Exigence MLOps | Cours couvrants | Cycle projet | Modèle / artefact |
|---|---|---|---|
| **Tracking expériences** | C33 MLflow tracking | 11.1 | tous M1-M9 + métadonnées encodage E1-E2 |
| **Versioning modèles** | C34 MLflow Registry | 11.2 | M1-M8 alias `@Production` |
| **Versioning données** | C35 DVC pipelines | 11.3 | data/raw/full + processed + embeddings |
| **Orchestration** | C36 Airflow DAGs | 12.1 | retrain hebdo cleaning→encoders→train→eval |
| **Serving + métriques** | C37 BentoML | 12.2 | API M1-M8 avec Prometheus natif |
| **Closed-loop auto** | C38 Boucle MLOps | 12.3 | drift → retrain → register → promote → reload |
| **Containerisation** | C39 Docker multi-stage | 13.1 | Dockerfile.api + Dockerfile.frontend (CUDA) |
| **Compose dev/prod** | C40 Docker Compose | 13.2 | services + profiles |
| **Reverse proxy + TLS** | C41 Traefik | 13.3 | gateway + middlewares + rate-limit |
| **Object storage** | C42 MinIO | 13.4 | DVC remote + MLflow artifacts |
| **Orchestration container** | C43 Kubernetes | 13.5 | Pod + Deployment + Service + HPA |
| **Logs structurés** | C44 structlog | 14.1 | JSON + correlation IDs |
| **Métriques infra** | C45 Prometheus | 14.2 | 4 golden signals |
| **Dashboards** | C46 Grafana | 14.3 | dashboards par modèle + golden signals |
| **Drift détection** | C47 Evidently | 14.4 | D1 cat / D2 emb / D3 conf / D4 MAPE |
| **CI/CD** | C49 GitHub Actions GHCR | 15.2 | build + tests + push GHCR |
| **Tests E2E + sécu** | C50 tests intégration | 15.3 | pytest E2E + bandit/safety |

**Total : 17 exigences MLOps couvertes par 17 cours répartis sur les cycles 11-15.** ✅

---

## 4. Modèles ML monitorés en production

> Référencer `docs/modeles.md` pour les fiches détaillées. Cette section liste juste **ce qui sera monitoré en prod**.

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

**Total : 10 modèles avec drift monitoring continu.** ✅

---

## 5. Ce qui est explicitement HORS-SCOPE

> Référencer `docs/PROJECT.md` §6 pour le détail. Rappel rapide :

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

Quand un cycle est complété :
1. Cocher le statut dans la colonne "Statut implémentation" de la table §1.
2. Référencer le commit hash dans `BRAIN/state.md` historique.
3. Si un cours change de cycle (refactoring), mettre à jour les §1 et §2.
4. Si une exigence MLOps n'est pas couverte, lever une alerte dans `BRAIN/state.md` "Blockers".

Ce document est **maintenu par l'agent IA** lors des phases RESTIT (cf. `BRAIN/golden_rules.md` règle 9).
