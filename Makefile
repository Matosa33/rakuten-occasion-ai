# === Commandes standardisées Rakuten AI ===
# Pour lister : make help

.PHONY: help install install-data lint lint-fix test test-cov audit audit-load audit-quality audit-dist audit-bias clean

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
