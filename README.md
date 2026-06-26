# Rakuten AI — Assistant de mise en vente d'occasion

![tests](https://img.shields.io/badge/tests-406%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.11-blue)
![lint](https://img.shields.io/badge/lint-ruff-orange)
![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20React%2019-0aa)
![license](https://img.shields.io/badge/license-MIT-green)

**À partir de quelques photos d'un objet, l'application produit une fiche de vente d'occasion complète : catégorie exacte, attributs structurés, titre, description et prix conseillé.** Cas d'usage fondateur : le vendeur particulier qui « mitraille » son grenier un jour de déménagement et veut des annonces propres en quelques secondes — sans rien saisir à la main.

Le cœur ML est un **pipeline d'identification *grounded*** (ADR D-009, règle d'or R19) : on **récupère** le produit réel dans un catalogue de ~4,5 M références (index FAISS de **3,16 M vecteurs**, le split train) **avant** de laisser un modèle génératif rédiger. Les modèles génératifs **valident et rédigent — ils n'identifient jamais sans ancre catalogue**. Anti-hallucination par construction.

Depuis le Cycle 36, ce principe se prolonge par une **identification raisonnée** : le **retriever apporte la connaissance** (les 15 fiches catalogue réelles les plus proches) et le **VLM/LLM apporte le jugement** (lequel de ces 15 candidats correspond vraiment à la photo, faut-il poser une question, quel est le prix neuf de référence). Le modèle génératif **ne peut jamais introduire un produit hors des 15 candidats** : un ASIN halluciné est ignoré et l'on retombe sur le top-1 du retrieval. Le retrieval seul pouvait laisser un *accessoire* en tête (une coque d'iPhone affichée comme « le produit ») ; la passe raisonnée **réordonne** le bon candidat en tête, et c'est sur lui que portent ensuite la fiche, le prix et la validation.

> **État au 2026-06-26** : pipeline **photo-first complet et fonctionnel** (D-035), enrichi par l'**identification raisonnée** du Cycle 36 (jugement LLM du top-15 grounded, texte vendeur autoritaire, ancre prix neuf estimée par IA, fiche exhaustive sourcée, parcours vendeur refondu). Cycles 0 → 36 livrés (data, retrieval, classifieurs, pricing, explainability, API, frontend, MLOps de bout en bout, sécurité, CI/CD). **406 tests verts.** Le Cycle 36 vit sur la branche `feat/cycle34-listing-quality-bench` (non encore mergée), vérifié *en live* sur de vraies photos. Différés assumés et documentés : indexation vision SigLIP du catalogue (test gated, D-014) et fine-tuning VLM QLoRA (conditionnel à un gain mesuré, F8). Détail honnête en bas de page.

---

## Le pipeline en un coup d'œil

```
                        PHOTO(S) du vendeur  ──►  preuve d'achat + entrée du pipeline
                              │
              ┌───────────────┴────────────────┐
              ▼                                 ▼
   VLM extraction (Gemma)              Checklist état UNIVERSELLE
   titre + attributs JSON              (les « bābā » de l'état ;
   {marque, modèle, couleur…}           la checklist SPÉCIFIQUE au
                                        type vient après l'identif., C36)
              │
              ▼
   RETRIEVAL GROUNDED                  ◄── cœur identification (R19)
   Arctic Embed → FAISS HNSW               le retriever apporte la CONNAISSANCE
   sur ~4,5 M produits (4 catégories)      (top-15 candidats réels)
              │
              ▼
   IDENTIFICATION RAISONNÉE (C36)      ◄── le VLM/LLM apporte le JUGEMENT :
   1 appel LLM sur le top-15 (texte)       famille + bon candidat (réordonné)
   {famille, candidat choisi, ancre         + ancre prix NEUF + question
    prix neuf, catalog-miss, question}       discriminante. Grounded : jamais
              │                              hors des 15 fiches.
              ▼
   TEXTE VENDEUR AUTORITAIRE            ◄── si le vendeur NOMME un produit
   (déterministe, ≥2 tokens, ≥50 %)         présent dans les candidats, il fait
              │                              FOI (indépendant du LLM rapide)
              ▼
   Désambiguation « Akinator »         ◄── lève l'ambiguïté par observation
   (facette la plus discriminante,         dirigée, jamais par hallucination
    par entropie × couverture)
              │
              ▼
   VLM validateur (F0.4)               ◄── photo vendeur × image catalogue
   {match, confidence, reason}             → badge de correspondance visuelle
              │                              (sauté si la passe raisonnée est
       ┌──────┴───────┐                      déjà confiante — économie latence)
       ▼              ▼
   PRICING        LLM rédacteur
   transparent    grounded (Gemma)
   (cascade       description ancrée
    L1→L1.5→      sur la fiche réelle
    L2→L3→L4,     (zéro invention)
    USD→EUR)
       │              │
       └──────┬───────┘
              ▼
   ANNONCE MARKETPLACE-GRADE
   breadcrumb catégorie · galerie photos · prix + badge état
   caractéristiques structurées sourcées (5 provenances) · description éditable
   bandeaux honnêtes : « Modèle à confirmer » · « Produit estimé, absent du
   catalogue » · « Prix neuf estimé par IA » (L1.5)
```

> **Entrée** : la **photo est la seule donnée obligatoire** (preuve pour l'acheteur + point de
> départ). Les **métadonnées sont optionnelles** et améliorent le résultat : une *précision
> texte* (ex. « iPhone 13 128 Go ») affine la recherche et **fait foi** si elle nomme un produit
> du catalogue (texte vendeur autoritaire, C36), l'*état général* (dont « Pour pièces / HS »)
> ajuste le prix et le titre, l'*année d'achat* (option) affine la décote par âge. Depuis le
> Cycle 36, le **type d'objet n'est plus saisi à la main** : il est **dérivé de la catégorie
> identifiée**, et la *checklist d'état spécifique* (batterie/écran d'un téléphone, clavier d'un
> portable, manettes d'une console…) s'affiche **après l'identification**, au bon moment, pour
> enrichir la description.

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

pytest tests/                  # 406 tests — contrats, parsing, sécurité, cascade prix, identification raisonnée, texte vendeur, compose…
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
| Identification raisonnée (C36) | **1 appel VLM/LLM** qui juge le top-15 (famille + candidat réordonné + ancre prix neuf + catalog-miss + question) — grounded, non bloquant | ✅ |
| Texte vendeur autoritaire (C36) | match déterministe (≥2 tokens, ≥50 %, numéros de modèle gardés) → fixe le produit indépendamment du LLM | ✅ |
| Désambiguation | **Akinator** multi-facette par entropie (Python pur) | ✅ |
| Extraction photo + validateur | **VLM Gemma** via OpenRouter (extraction attributs + match visuel F0.4) | ✅ |
| Classifieurs benchmark | k-NN, SVM, MLP, TF-IDF+LinSVC, Fusion (M1-M6) — garde-fou L1 | ✅ |
| LLM rédacteur grounded | **Gemma** via OpenRouter + RAG sur fiche catalogue réelle | ✅ |
| Pricing transparent | cascade algorithmique déterministe L1→L1.5→L2→L3→L4 + garde-fous anti sous-évaluation / cohérence / outlier + conversion USD→EUR | ✅ |
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

**Qualité de fiche (Cycle 36)** — mesure reproductible sur le **panel réel de 94 produits** (`data/photos_eval/`, photo seule sans précisions, noms de dossiers = vérité-terrain) :

| Métrique | Valeur | Source |
|---|---|---|
| Identification (≥ 50 % des tokens clés retrouvés) | **90.3 %** (rappel moyen **78 %**) | `reports/09_fiche_quality/` |
| Complétude de fiche | **0.84** moyenne / **0.83** médiane | `reports/09_fiche_quality/` |
| Passe raisonnée déclenchée | **100 %** | `reports/09_fiche_quality/` |
| Catalog-miss détecté | **28 %** | `reports/09_fiche_quality/` |
| Question discriminante posée | **11 %** | `reports/09_fiche_quality/` |
| Niveaux de prix utilisés | **L1 = 42**, **L1.5 = 51** | `reports/09_fiche_quality/` |

> Toutes les comparaisons de modèles suivent R4 (≥ 3 modèles benchmarkés) et R5 (tout run tracké MLflow). Les biais des PoC (espace de recherche réduit, studio→studio) sont **documentés explicitement** dans les rapports — pas de chiffre vanity. La mesure de fiche remplace l'anecdote par un chiffre défendable (doctrine R21 : mesurer sur de **vraies sorties**) : 9 produits sur 94 ne sont pas identifiés, et chacun est **expliqué** (perception du modèle exact limitée sur photo — RTX 4080 Super → 3080, Xbox Series S, Sennheiser Momentum → Philips ; catalog-miss SSD/dock ; ou nom de dossier ambigu, artefact de mesure).

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
│   ├── vlm/                # Extraction photo + validateur F0.4 + identification raisonnée (C36)
│   ├── llm/                # Prompts + rédacteur RAG grounded
│   ├── pricing/            # Cascade algorithmique transparente (L1→L1.5→L2→L3→L4)
│   ├── explain/            # SHAP + t-SNE + Model Cards
│   ├── api/                # FastAPI + SSE + uploads + auth JWT + texte vendeur autoritaire (C36)
│   ├── auth/               # JWT HS256 (bcrypt)
│   ├── mlops/              # MLflow / promotion champion-challenger
│   ├── serving/            # BentoML + assemblage de fiche exhaustive sourcée (listing_fill, D-041/C36)
│   ├── monitoring/         # Drift Evidently + push metrics
│   └── observability/      # structlog + Prometheus
├── frontend/               # React 19 (flow unitaire « Un objet » + mode batch « Déménagement »)
├── scripts/                # mesure_qualite_fiche.py (protocole panel réel, C36) …
├── infra/                  # docker/ (Dockerfiles, nginx, traefik) · airflow/ · k8s/
├── monitoring/             # prometheus/ · grafana/ · evidently/
├── reports/                # 11 phases : audit → … → PoC photo + qualité de fiche (rapports + métriques)
├── tests/                  # 46 fichiers, 406 tests (pytest)
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
- **Observabilité** : 4 golden signals Prometheus + dashboards Grafana, logs structurés JSON corrélés par `request_id`. **Logs métier inspectables (C36)** : `identify_done` (status, candidats, score top-1, catégorie fine, passe raisonnée, réordonnancement, catalog-miss, ancre prix, question, complétude, timings extraction/raison) et `price_done` (niveau de cascade réellement utilisé, méthode, prix suggéré, présence d'ancre IA) — on LIT ce que fait le pipeline (taux de catalog-miss, usage de L1.5, où part la latence), rien de décoratif.
- **Livraison** : images Docker construites en CI, publiées sur GHCR avec tag semver.

---

## Sécurité

- **Zéro secret dans le code** (R2) : tout en `.env` (gitignoré). `.env.example` ne contient que des gabarits.
- **JWT HS256** sur les endpoints sensibles ; `JWT_SECRET` généré, jamais committé.
- **Uploads** : whitelist de types, limite de taille, garde **anti-path-traversal** stricte, photos vendeur gitignorées (vie privée).
- **URLs capability** (uuid4 non devinable) pour servir les photos.
- **Durcissement Cycle 36** (revue adverse 5 dimensions, corrections appliquées) : bornes Pydantic sur les prix (`gt=0`, `le=1e6`, `allow_inf_nan=False`) et sur les listes/textes d'entrée (anti-DoS du prompt LLM) ; **texte vendeur délimité comme donnée non fiable** dans le prompt (anti prompt-injection : il n'est jamais interprété comme une consigne).
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

### Limites honnêtes de l'identification raisonnée (Cycle 36)

On les nomme telles quelles plutôt que de survendre :

- **Photo seule, modèle exact** : la perception du **modèle précis** est limitée pour un produit dont le marquage n'est **pas visible** sur les photos envoyées (ex. un Sennheiser Momentum 3 dont le logo est sur l'étui). Le VLM peut alors choisir un sosie avec aplomb. C'est **mitigé** par trois garde-fous : (a) le **texte vendeur autoritaire** (la métadonnée fixe le produit quand il EST au catalogue), (b) le flag **« Modèle à confirmer »**, (c) le bouton **« Ce n'est pas le bon ? »** sur la fiche.
- **Sous-déclenchement du catalog-miss** : le modèle rapide (`qwen3.5-flash`) colle parfois à un sosie d'une autre génération au lieu de signaler l'absence (iPhone 14 → 13, RTX 4080 → 3080). Un modèle jugé plus fort (variable `PHOTO_VLM_IDENTIFY_MODEL`) ferait mieux — option **non câblée par défaut**.
- **Garde-fou anti sous-évaluation surtout défensif** : c'est le niveau **L1.5** (ancre prix neuf estimée par IA) qui fait le vrai travail face aux médianes de voisins polluées par accessoires/coques/bundles ; le plancher anti sous-évaluation n'est qu'un filet de sécurité.

> Important : l'ancre prix L1.5 est une **estimation** explicitement étiquetée « Prix neuf estimé par IA », jamais affirmée comme un fait catalogue ; la **décote** appliquée (état + dépréciation d'âge) reste **100 % déterministe et transparente** — « pas de pricing ML opaque » demeure vrai.

---

## Licence

MIT
