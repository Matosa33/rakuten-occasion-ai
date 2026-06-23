# Rakuten AI — Assistant de mise en vente d'occasion

![tests](https://img.shields.io/badge/tests-326%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.11-blue)
![lint](https://img.shields.io/badge/lint-ruff-orange)
![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20React%2019-0aa)
![license](https://img.shields.io/badge/license-MIT-green)

**À partir de quelques photos d'un objet, l'application produit une fiche de vente d'occasion complète : catégorie exacte, attributs structurés, titre, description et prix conseillé.** Cas d'usage fondateur : le vendeur particulier qui « mitraille » son grenier un jour de déménagement et veut des annonces propres en quelques secondes — sans rien saisir à la main.

Le cœur ML est un **pipeline d'identification *grounded*** (ADR D-009, règle d'or R19) : on **récupère** le produit réel dans un catalogue de ~4,5 M références (index FAISS de **3,16 M vecteurs**, le split train) **avant** de laisser un modèle génératif rédiger. Les modèles génératifs **valident et rédigent — ils n'identifient jamais sans ancre catalogue**. Anti-hallucination par construction.

> **État au 2026-06-13** : pipeline **photo-first complet et fonctionnel** (D-035). Cycles 0 → 17 livrés (data, retrieval, classifieurs, pricing, explainability, API, frontend, MLOps de bout en bout, sécurité, CI/CD). 326 tests verts. Différés assumés et documentés : indexation vision SigLIP du catalogue (test gated, D-014) et fine-tuning VLM QLoRA (conditionnel à un gain mesuré, F8). Détail honnête en bas de page.

---

## Le pipeline en un coup d'œil

```
                        PHOTO(S) du vendeur  ──►  preuve d'achat + entrée du pipeline
                              │
              ┌───────────────┴────────────────┐
              ▼                                 ▼
   VLM extraction (Gemma)              Checklist état guidée
   titre + attributs JSON              (vues conseillées par type
   {marque, modèle, couleur…}           d'objet + « bābā » de l'état)
              │
              ▼
   RETRIEVAL GROUNDED                  ◄── cœur identification (R19)
   Arctic Embed → FAISS HNSW
   sur ~4,5 M produits (4 catégories)
              │
              ▼
   Désambiguation « Akinator »         ◄── lève l'ambiguïté par observation
   (facette la plus discriminante,         dirigée, jamais par hallucination
    par entropie × couverture)
              │
              ▼
   VLM validateur (F0.4)               ◄── photo vendeur × image catalogue
   {match, confidence, reason}             → badge de correspondance visuelle
              │
       ┌──────┴───────┐
       ▼              ▼
   PRICING        LLM rédacteur
   transparent    grounded (Gemma)
   (cascade       description ancrée
    L1→L4,        sur la fiche réelle
    USD→EUR)      (zéro invention)
       │              │
       └──────┬───────┘
              ▼
   ANNONCE MARKETPLACE-GRADE
   breadcrumb catégorie · galerie photos · prix + badge état
   caractéristiques structurées · description éditable
```

> **Entrée** : la **photo est la seule donnée obligatoire** (preuve pour l'acheteur + point de
> départ). Les **métadonnées sont optionnelles** et améliorent le résultat : une *précision
> texte* (ex. « iPhone 13 128 Go ») affine la recherche, l'*état général* ajuste le prix et le
> titre, la *checklist guidée par type* enrichit la description.

Deux modes d'usage côté frontend : **🎯 Un objet** (flow guidé pas à pas) et **📦 Déménagement** (« mitrailler » N objets à la chaîne, analyses en arrière-plan, tableau de bord des annonces prêtes).

---

## Démo en 30 secondes (tout en CLI)

Pré-requis : **Docker Desktop** démarré. Les images sont multi-stage et la stack est unifiée en un seul `docker-compose.yml` (14 services).

```bash
git clone <url-du-repo> rakuten_de_zero
cd rakuten_de_zero

cp .env.example .env          # puis renseigner OPENROUTER_API_KEY + générer JWT_SECRET
docker compose up -d          # démarre toute la stack
docker compose ps             # attendre que l'API soit "healthy" (chargement FAISS)
```

| Service | URL locale (ports par défaut, customisables via `.env`) |
|---|---|
| **Application vendeur** (login `demo` / `demo`) | http://localhost:8082 |
| API FastAPI (OpenAPI docs) | http://localhost:8010/docs |
| MLflow (tracking + Model Registry) | http://localhost:5000 |
| Grafana (golden signals MLOps) | http://localhost:3000 |
| Airflow (DAG de retrain) | http://localhost:8088 |
| Traefik (entrée unifiée `*.localhost`) | http://localhost:8090 |

Tout se rééteint proprement avec `docker compose down` (les volumes de données sont préservés). Cibles raccourcies dans le `Makefile` : `make up`, `make down`, `make ps`, `make logs`, `make smoke`.

---

## Tester sans les données lourdes

Les artefacts lourds (index FAISS ~14 Go, embeddings, modèles, dumps catalogue) sont **volontairement absents du dépôt** (gitignorés — un repo Git n'héberge pas 60 Go de données). Sans eux, on peut néanmoins **tout vérifier sauf l'inférence live** :

```bash
python3.11 -m venv .venv && .venv\Scripts\activate    # (Linux : source .venv/bin/activate)
pip install -e ".[dev,data,ml,api,monitoring,mlops]"   # mêmes extras que la CI

pytest tests/                  # 326 tests — contrats, parsing, sécurité, cascade prix, compose…
ruff check src/ tests/         # lint 0 erreur
ruff format --check src/ tests/

docker compose build           # les images se construisent end-to-end
```

Les tests **ne dépendent pas des artefacts lourds** : ils valident la logique (parsing VLM tolérant, anti-path-traversal des uploads, cascade de pricing, cohérence devise, garde-fous OOD, contrats Docker/compose…) avec des mocks et fixtures. La CI GitHub Actions rejoue exactement cela (`.github/workflows/ci.yml`).

---

## Stack technique (état réel)

| Couche | Composant | Statut |
|---|---|---|
| Encodeur texte (frozen) | Snowflake **Arctic Embed L v2** | ✅ |
| Retrieval (cœur identification) | **FAISS HNSW** 3,16 M vecteurs + RRF + OOD 3 niveaux | ✅ |
| Désambiguation | **Akinator** multi-facette par entropie (Python pur) | ✅ |
| Extraction photo + validateur | **VLM Gemma** via OpenRouter (extraction attributs + match visuel F0.4) | ✅ |
| Classifieurs benchmark | k-NN, SVM, MLP, TF-IDF+LinSVC, Fusion (M1-M6) — garde-fou L1 | ✅ |
| LLM rédacteur grounded | **Gemma** via OpenRouter + RAG sur fiche catalogue réelle | ✅ |
| Pricing transparent | cascade algorithmique déterministe L1→L4 + conversion USD→EUR | ✅ |
| Explainability | SHAP + t-SNE + 12 Model Cards | ✅ |
| Backend API | **FastAPI** + Pydantic v2 + SSE + JWT HS256 | ✅ |
| Frontend | **React 19** + Vite + Tailwind v4 + Framer Motion | ✅ |
| Expériences & modèles | **MLflow** tracking + Model Registry (`@Production`) | ✅ |
| Données versionnées | **DVC** (DAG `dvc.yaml`) | ✅ |
| Orchestration retrain | **Airflow** (boucle fermée champion/challenger) | ✅ |
| Serving modèle | **BentoML** (import depuis Registry) | ✅ |
| Infra | **Docker Compose** (14 services) + Traefik + MinIO + manifests **k8s** (kind) | ✅ |
| Observabilité | **structlog** JSON + **Prometheus** + **Grafana** + Evidently (drift) | ✅ |
| CI/CD | **GitHub Actions** (lint, tests, pip-audit, docker-build) + **GHCR** semver | ✅ |
| Indexation vision catalogue | SigLIP multi-vues — **gated** (test 1 nuit, D-014) | ⏸️ |
| Fine-tuning VLM | QLoRA — **conditionnel** à un gain mesuré > +0.05 F1 (F8) | ⏸️ |

---

## Métriques clés (mesurées, voir `reports/`)

| Métrique | Valeur | Source |
|---|---|---|
| F1 pondéré classification (M1 FAISS k-NN, vainqueur bench) | **0.954** | `reports/04_classifiers_bench/` |
| Recall@1 retrieval HNSW | **0.948** @ 0.29 ms | `reports/05_retrieval/` |
| Catégorie top-1 (RRF) | **94.2 %** | `reports/05_retrieval/` |
| Seuil OOD (mode dégradé) | 0.600 (P=0.953 / R=0.988) | `reports/05_retrieval/` |
| Calibration (ECE meilleur modèle) | 0.0013 | `reports/04_classifiers_bench/` |

> Toutes les comparaisons de modèles suivent R4 (≥ 3 modèles benchmarkés) et R5 (tout run tracké MLflow). Les biais des PoC (espace de recherche réduit, studio→studio) sont **documentés explicitement** dans les rapports — pas de chiffre vanity.

---

## Architecture du dépôt

```
rakuten/
├── documentation/          # TOUTE la doc : cadrage + 1 rapport par thème + glossaire
│   ├── PROJECT.md          # Cadrage produit (besoin, hypothèses, hors-scope)
│   ├── 00_vue_ensemble.md  # Le système en un coup d'œil (pipeline)
│   ├── 01..16_*.md         # Un rapport par thème (data, modèles, retrieval, MLOps, infra…)
│   ├── exigences_*.md       # Traçabilité exigences F0-F8 + couverture
│   └── GLOSSAIRE.md        # Tout le jargon en une ligne
├── src/
│   ├── data/               # Audit → cleaning → split → validation (Pandera)
│   ├── encoders/           # Arctic Embed (+ SigLIP gated)
│   ├── classifiers/        # M1-M6 + TF-IDF + fusion
│   ├── retrieval/          # FAISS HNSW + RRF + OOD + Akinator
│   ├── vlm/                # Extraction photo + validateur F0.4
│   ├── llm/                # Prompts + rédacteur RAG grounded
│   ├── pricing/            # Cascade algorithmique transparente
│   ├── explain/            # SHAP + t-SNE + Model Cards
│   ├── api/                # FastAPI + SSE + uploads + auth JWT
│   ├── auth/               # JWT HS256 (bcrypt)
│   ├── mlops/              # MLflow / promotion champion-challenger
│   ├── serving/            # BentoML
│   ├── monitoring/         # Drift Evidently + push metrics
│   └── observability/      # structlog + Prometheus
├── frontend/               # React 19 (8 composants : flow unitaire + mode batch)
├── infra/                  # docker/ (Dockerfiles, nginx, traefik) · airflow/ · k8s/
├── monitoring/             # prometheus/ · grafana/ · evidently/
├── reports/                # 11 phases : audit → … → PoC photo (rapports + métriques)
├── tests/                  # 33 fichiers, 326 tests (pytest)
├── .github/workflows/      # ci.yml + ghcr.yml
├── docker-compose.yml      # Stack unifiée (14 services) + overlay .prod.yml
├── Makefile                # 27 cibles standardisées
├── dvc.yaml · bentofile.yaml · pyproject.toml
└── .env.example            # Gabarit de configuration (aucun secret réel)
```

---

## MLOps — le cycle de vie, pas juste un modèle

- **Tracking** : chaque entraînement loggé dans MLflow (params / métriques / artefacts).
- **Registry** : le modèle servi est *registered* avec alias `@Production` — promotion par **gate champion/challenger** (`make promote-gate`).
- **Boucle fermée** : DAG Airflow `rakuten_retrain` (`make airflow-trigger`) → réentraînement → comparaison → promotion conditionnelle (de vrais retrains ont produit des versions v4/v5 en Registry).
- **Drift** : rapports Evidently (`make drift-check`).
- **Observabilité** : 4 golden signals Prometheus + dashboards Grafana, logs structurés JSON corrélés par `request_id`.
- **Livraison** : images Docker construites en CI, publiées sur GHCR avec tag semver.

---

## Sécurité

- **Zéro secret dans le code** (R2) : tout en `.env` (gitignoré). `.env.example` ne contient que des gabarits.
- **JWT HS256** sur les endpoints sensibles ; `JWT_SECRET` généré, jamais committé.
- **Uploads** : whitelist de types, limite de taille, garde **anti-path-traversal** stricte, photos vendeur gitignorées (vie privée).
- **URLs capability** (uuid4 non devinable) pour servir les photos.
- CI : `pip-audit` sur les dépendances + tests de contrat sur les images Docker.

---

## Documentation

Toute la documentation est dans **[`documentation/`](documentation/)** (un seul dossier) :
le **cadrage produit** ([PROJECT.md](documentation/PROJECT.md)), la **vue d'ensemble**
([00_vue_ensemble.md](documentation/00_vue_ensemble.md)), puis **un rapport par thème technique**
(data engineering, embeddings, retrieval, MLflow, drift, infra…). Chaque rapport suit la même
structure : *la techno et son rôle → notre implémentation → résultats mesurés → critique et
limites → références*. Un [GLOSSAIRE](documentation/GLOSSAIRE.md) décode tout le jargon.

> Pour découvrir : commencer par [PROJECT.md](documentation/PROJECT.md) puis
> [00_vue_ensemble.md](documentation/00_vue_ensemble.md).

---

## Différés assumés (transparence)

Un projet honnête nomme ce qu'il n'a *pas* fait et pourquoi :

- **Indexation vision SigLIP du catalogue** (D-014) : l'entrée photo fonctionne aujourd'hui via **extraction VLM** (le VLM lit la photo → titre/attributs → retrieval texte). L'indexation visuelle directe du catalogue (recherche image→image sur 4,5 M produits) exige ~73 h de téléchargement CDN ; elle est **gated derrière un test de mesure d'une nuit** (PoC `reports/11_poc_photo/`) qui décidera GO/NO-GO sur preuve, pas sur intuition (induction, pas déduction).
- **Fine-tuning VLM QLoRA** (F8) : déclenché **uniquement** si un benchmark montre un gain > +0.05 F1 macro vs le zero-shot grounded. Non déclenché à ce jour faute de bénéfice démontré — la sur-ingénierie est un anti-pattern (R15).

---

## Licence

MIT
