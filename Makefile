# === Commandes standardisées Rakuten AI ===
# Pour lister : make help

.PHONY: help install install-data lint lint-fix test test-cov audit audit-load audit-quality audit-dist audit-bias clean up down logs ps stack-build airflow-trigger bento-import bento-serve drift-check promote-gate api-build frontend-build prod-up prod-down k8s-up k8s-load k8s-deploy k8s-smoke k8s-down

KIND := ./.local/bin/kind.exe
KIND_VERSION := v0.24.0
KIND_URL := https://kind.sigs.k8s.io/dl/$(KIND_VERSION)/kind-windows-amd64
K8S_INGRESS_PORT ?= 8095

# Stack Compose unifiée à la racine (D-025). Override prod via `-f`.
COMPOSE := docker compose
PROD := -f docker-compose.yml -f docker-compose.prod.yml

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Installe le projet en mode editable + deps dev + pre-commit hooks
	pip install --upgrade pip
	pip install -e ".[dev]"
	pre-commit install

install-data:  ## Installe les deps Phase P02 (pandas, datasets, matplotlib, jupyter)
	pip install -e ".[dev,data]"

lint:  ## Lint + format check (sans modifier)
	ruff check src/ tests/
	ruff format --check src/ tests/

lint-fix:  ## Lint + format avec corrections automatiques
	ruff check --fix src/ tests/
	ruff format src/ tests/

test:  ## Lance les tests pytest (sans gpu/slow)
	pytest tests/ -v --tb=short -m "not gpu and not slow"

test-cov:  ## Tests avec rapport de couverture HTML
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

audit-load:  ## P02 - télécharge les 3 cat FULL (~35 GB, hf_hub_download avec resume)
	python -m src.data.audit.01_load_full

audit-quality:  ## P02 - audit qualité (NaN, types, doublons, longueurs)
	python -m src.data.audit.02_audit_qualite

audit-dist:  ## P02 - audit distributions (catégories, prix, ratings, temporel)
	python -m src.data.audit.03_audit_distributions

audit-bias:  ## P02 - audit biais et leakages potentiels
	python -m src.data.audit.04_audit_biais_leakage

audit:  ## P02 - chaîne audit complète (load → qualité → dist → biais)
	$(MAKE) audit-load
	$(MAKE) audit-quality
	$(MAKE) audit-dist
	$(MAKE) audit-bias

clean:  ## Nettoie les caches Python/pytest/ruff
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# === Cycle 12 — Orchestration Airflow (D-022) ===

# === Cycle 13.2 — Stack unifiée (D-025) ===

up:  ## C13.2 - build + démarre TOUTE la stack (api, frontend, airflow, postgres)
	$(COMPOSE) up -d --build

down:  ## C13.2 - arrête la stack (préserve les volumes Postgres + data)
	$(COMPOSE) down

logs:  ## C13.2 - suit les logs (ex: make logs SVC=api ou tous par défaut)
	$(COMPOSE) logs -f $(SVC)

ps:  ## C13.2 - état des services de la stack
	$(COMPOSE) ps

stack-build:  ## C13.2 - rebuild toutes les images de la stack sans démarrer
	$(COMPOSE) build

prod-up:  ## C13.2 - démarre la stack avec overlay prod (restart strict, ports internes)
	$(COMPOSE) $(PROD) up -d --build

prod-down:  ## C13.2 - arrête la stack prod
	$(COMPOSE) $(PROD) down

airflow-trigger:  ## C12 - déclenche manuellement le DAG rakuten_retrain
	$(COMPOSE) exec airflow-scheduler airflow dags trigger rakuten_retrain

# === Cycle 12.2 — Serving BentoML (D-022) ===

bento-import:  ## C12.2 - importe le modèle @Production MLflow dans le store BentoML
	BENTOML_DO_NOT_TRACK=1 python -m src.serving.import_model

bento-serve:  ## C12.2 - sert le classifieur (API :8500, métriques Prometheus /metrics)
	BENTOML_DO_NOT_TRACK=1 bentoml serve src/serving/service.py:RakutenClassifier --port 8500

# === Cycle 12.3 — Boucle fermée (D-024) ===

drift-check:  ## C12.3 - détection de drift Evidently (rapport HTML monitoring/evidently/reports/)
	python -m src.monitoring.drift_detection

promote-gate:  ## C12.3 - champion/challenger : bouge @Production si nouveau modèle meilleur
	python -m src.mlops.promote_gate

# === Cycle 13.1 — Images Docker API + Frontend ===

api-build:  ## C13.1 - build image API (multi-stage CPU, ~quelques min)
	docker build -f infra/docker/Dockerfile.api -t rakuten/api:dev .

frontend-build:  ## C13.1 - build image Frontend (Node→nginx, ~1-2 min)
	docker build -f infra/docker/Dockerfile.frontend -t rakuten/frontend:dev .

# === Cycle 13.5 — Kubernetes (kind cluster local) — D-028 ===

$(KIND):  ## Télécharge le binaire kind si absent (idempotent)
	@mkdir -p $(dir $(KIND))
	@if [ ! -x "$(KIND)" ]; then echo "Téléchargement kind $(KIND_VERSION)..."; curl -fsSL -o $(KIND) $(KIND_URL); fi

k8s-up: $(KIND)  ## C13.5 - crée le cluster kind + installe ingress-nginx
	$(KIND) create cluster --config infra/k8s/kind-cluster.yaml --name rakuten
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/kind/deploy.yaml
	@echo "Attente readiness ingress-nginx (max 90s)..."
	kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s

k8s-load: $(KIND)  ## C13.5 - charge les images locales dans le cluster (pas de registry)
	$(KIND) load docker-image rakuten/api:dev --name rakuten
	$(KIND) load docker-image rakuten/frontend:dev --name rakuten
	$(KIND) load docker-image rakuten/mlflow:dev --name rakuten

k8s-deploy:  ## C13.5 - applique les manifests (copie secrets.yaml si absent)
	@if [ ! -f infra/k8s/secrets.yaml ]; then cp infra/k8s/02-secrets.example.yaml infra/k8s/secrets.yaml; echo "secrets.yaml créé depuis le gabarit (dev defaults)"; fi
	kubectl apply -k infra/k8s/
	@echo "Attente readiness API (max 180s)..."
	kubectl -n rakuten wait deployment/api --for=condition=available --timeout=180s || true

k8s-smoke:  ## C13.5 - curl via ingress sur les 3 hôtes (.localhost:$(K8S_INGRESS_PORT))
	@echo "→ rakuten.localhost:" && curl -s -o /dev/null -w "HTTP %{http_code}\n" -H "Host: rakuten.localhost" http://localhost:$(K8S_INGRESS_PORT)/
	@echo "→ api.localhost/health:" && curl -s -o /dev/null -w "HTTP %{http_code}\n" -H "Host: api.localhost" http://localhost:$(K8S_INGRESS_PORT)/health
	@echo "→ mlflow.localhost/health:" && curl -s -o /dev/null -w "HTTP %{http_code}\n" -H "Host: mlflow.localhost" http://localhost:$(K8S_INGRESS_PORT)/health

k8s-down: $(KIND)  ## C13.5 - supprime le cluster kind (idempotent)
	$(KIND) delete cluster --name rakuten 2>/dev/null || true
