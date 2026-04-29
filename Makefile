# === Commandes standardisées Rakuten AI ===
# Pour lister : make help

.PHONY: help install lint lint-fix test test-cov clean

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Installe le projet en mode editable + deps dev + pre-commit hooks
	pip install --upgrade pip
	pip install -e ".[dev]"
	pre-commit install

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

clean:  ## Nettoie les caches Python/pytest/ruff
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
