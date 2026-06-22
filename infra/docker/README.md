# Images Docker — Rakuten (Cycle 13 Infrastructure)

Toutes les images sont **multi-stage** (build isolé du runtime) et **CPU-only** :
la promesse soutenance « `make up` sur VM vierge » cible une machine sans GPU,
et l'encodage GPU vit dans un worker isolé (ADR D-022).

## Inventaire

| Image | Source | Rôle | Port (conteneur) |
|---|---|---|---|
| `rakuten/airflow:dev` | `Dockerfile.airflow` | Orchestration (DAGs retrain + drift) | 8080 (mappé 8088) |
| `rakuten/api:dev` | `Dockerfile.api` | API FastAPI (`/identify`, `/price`, `/describe`) | 8000 |
| `rakuten/frontend:dev` | `Dockerfile.frontend` | SPA React (Vite) + proxy `/api` → backend | 80 |

> Les services Compose qui les orchestrent (volumes, réseaux, profiles dev/prod) =
> Cycle 13.2. Gateway Traefik (TLS + middlewares) = Cycle 13.3.

## Build

Depuis la **racine du repo** (le contexte de build = racine, pour accéder à
`pyproject.toml` + `src/` + `frontend/`) :

```bash
docker build -f infra/docker/Dockerfile.api      -t rakuten/api:dev      .
docker build -f infra/docker/Dockerfile.frontend -t rakuten/frontend:dev .
docker build -f infra/docker/Dockerfile.airflow  -t rakuten/airflow:dev  .
```

Cibles Makefile équivalentes : `make api-build`, `make frontend-build`.

## Dockerfile.api — détails

**Stage 1 (builder)** : `python:3.12-slim` + `build-essential` + `git`. Crée un
venv `/opt/venv` et y installe `pip install ".[api,ml]"`. Torch en CPU explicite
via `--extra-index-url https://download.pytorch.org/whl/cpu` (sinon Linux tirerait
le wheel CUDA de ~3 Go, inutile sur la VM cible).

**Stage 2 (runtime)** : `python:3.12-slim` + `curl` (pour le healthcheck). Copie
le venv prêt-à-l'emploi du builder + le code source. Pas de toolchain de compil
dans le runtime → image finale plus petite et surface d'attaque réduite.

Healthcheck : `curl /health` (l'endpoint `src/api/main.py` expose l'état des
services chargés — utilisable par Traefik 13.3 et k8s 13.5 sans modif de code).

## Dockerfile.frontend — détails

**Stage 1 (builder)** : `node:20-alpine` + `npm ci` (lockfile reproductible) +
`vite build` → `dist/` optimisé (hash de cache sur les assets, gzip-friendly).

**Stage 2 (runtime)** : `nginx:1.27-alpine` qui sert `dist/` avec :
- **SPA fallback** (`try_files ... /index.html`) : toute route React routée client-side.
- **Proxy `/api/`** → `http://api:8000/` (nom de service Compose). Strip du
  préfixe `/api`, identique au proxy Vite de dev (`vite.config.ts`).
- **SSE-friendly** : `proxy_buffering off` + `proxy_read_timeout 300s` pour
  `/identify/stream` (cf. Cycle 9).

## Données / volumes (à monter en Compose 13.2)

L'API a besoin des artefacts ML produits hors image (le repo Git ne les contient
pas) :

| Chemin conteneur | Contenu | Origine |
|---|---|---|
| `/opt/rakuten/data/embeddings/text` | embeddings Arctic (~3 Go) | encodage hôte/worker |
| `/opt/rakuten/data/index` | index FAISS HNSW (~13 Go) | `python -m src.retrieval.01_faiss_indices` |
| `/opt/rakuten/data/models` | classifieurs joblib | retrain (DAG `rakuten_retrain`) |
| `/opt/rakuten/mlflow.db` + `/opt/rakuten/mlartifacts` | tracking MLflow | usage hôte / Cycle 13.4 (MinIO+server) |

Sans ces volumes, l'image démarre et répond `200` sur `/health` mais `/identify`
échoue à l'initialisation des services (FAISS introuvable). Honnête et attendu :
ce sont les VOLUMES qui rendent l'API fonctionnelle, pas l'image seule.

## Note premier load API sous Windows Docker Desktop

L'API charge au démarrage l'index FAISS HNSW (~**13,8 Go**) monté en read-only.
Sous **Windows + Docker Desktop (WSL2)**, le bind-mount lit séquentiellement
via la traduction NTFS↔ext4 → premier `faiss.read_index` prend **5 à 15 min**
(pas un bug, caractéristique connue). Sous **Linux natif (VM soutenance)** :
mmap direct, **quasi-instantané**.

Le `start_period` du healthcheck API est calé à 5 min pour tolérer ce cas
sans marquer le conteneur `unhealthy` à tort. Cf. les notes d'apprentissage du projet
(`bind-mount-RO-docker-desktop-windows-tres-lent-sur-gros-fichiers`).

## Pourquoi pas de variante CUDA ?

L'API ne fait que de l'inférence légère (FAISS CPU + un classifieur sklearn).
Les opérations lourdes GPU sont :
- l'**encodage** des embeddings → fait à part (script `src/encoders/`) sur la
  machine de dev avec GPU, ou un worker dédié (différé).
- le **fine-tuning VLM** → différé (D-014).

Une image GPU CUDA serait inutilement lourde (~6-8 Go) pour rien : la soutenance
tournerait moins bien sur la VM sans GPU. Cf. principe D-022 (« l'orchestrateur
orchestre, il ne calcule pas le GPU »).
