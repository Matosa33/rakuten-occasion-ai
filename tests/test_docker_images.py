"""Tests de contrat des Dockerfiles API + Frontend (Cycle 13.1).

Tests statiques : on n'exige pas Docker dans la CI pour valider le contrat des
Dockerfiles. Build effectif = `make api-build` / `frontend-build` (cf. README
`infra/docker/`). Ce qu'on vérifie ici protège contre la régression silencieuse :
multi-stage, healthcheck, ports exposés, et cohérence avec le projet.
"""

from __future__ import annotations

from pathlib import Path

DOCKER_DIR = Path(__file__).resolve().parents[1] / "infra" / "docker"


def _read(name: str) -> str:
    path = DOCKER_DIR / name
    assert path.exists(), f"manquant : {path}"
    return path.read_text(encoding="utf-8")


def test_dockerfile_api_multistage_cpu():
    src = _read("Dockerfile.api")
    # Multi-stage : builder + runtime.
    assert "AS builder" in src
    assert "AS runtime" in src
    # Torch CPU explicite (sinon Linux tirerait CUDA, ~3 Go inutiles sur VM).
    assert "download.pytorch.org/whl/cpu" in src
    # Installation depuis pyproject extras (pas de liste de deps dupliquée).
    assert "[api,ml]" in src
    # Healthcheck contre /health (l'endpoint réel de src/api/main.py).
    assert "HEALTHCHECK" in src and "/health" in src
    assert "EXPOSE 8000" in src
    # Code source copié vers /opt/rakuten avec PYTHONPATH.
    assert "/opt/rakuten" in src and "PYTHONPATH=/opt/rakuten" in src


def test_dockerfile_frontend_node_nginx():
    src = _read("Dockerfile.frontend")
    assert "node:" in src and "AS builder" in src
    assert "nginx:" in src and "AS runtime" in src
    # npm ci → lockfile reproductible (pas npm install).
    assert "npm ci" in src
    assert "npm run build" in src
    # nginx config externe et bien copiée.
    assert "infra/docker/nginx.conf" in src
    assert "EXPOSE 80" in src
    assert "HEALTHCHECK" in src


def test_nginx_conf_spa_et_proxy_api():
    """nginx config : SPA fallback + proxy /api → backend (DNS Docker) + SSE-friendly."""
    src = _read("nginx.conf")
    # SPA : try_files → index.html.
    assert "try_files" in src and "/index.html" in src
    # Proxy /api/ vers le service Compose "api:8000".
    assert "location /api/" in src
    assert "api:8000" in src
    # Régression smoke C13.1 : DNS résolu À LA REQUÊTE (resolver Docker),
    # sinon nginx plante au démarrage si le service "api" n'est pas joignable.
    assert "resolver 127.0.0.11" in src
    assert "set $api_upstream" in src or "$api_upstream" in src
    # SSE : pas de bufferisation + timeout long pour /identify/stream.
    assert "proxy_buffering off" in src


def test_pyproject_api_extra_contient_polars():
    """Régression smoke C13.1 : `src/api/pipeline.py` importe polars au démarrage.
    Sans polars dans l'extra [api], l'image API plante à l'import (ModuleNotFoundError).
    """
    pyproject = (DOCKER_DIR.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    # On localise grossièrement la section [api] = ... et on vérifie polars dedans.
    api_block = pyproject.split("api = [", 1)[1].split("]", 1)[0]
    assert "polars" in api_block, "polars manquant dans pyproject extra [api]"
    assert "pyarrow" in api_block, "pyarrow manquant dans pyproject extra [api]"


def test_nginx_ecoute_ipv4_et_ipv6():
    """Régression C13.3 : healthcheck `wget http://localhost/` résout `::1` (IPv6)
    en premier dans Alpine. Si nginx n'a pas `listen [::]:80;`, connection refused
    → conteneur frontend unhealthy → Traefik v3 filtre → routing cassé.
    """
    src = _read("nginx.conf")
    assert "listen 80;" in src
    assert "listen [::]:80;" in src, (
        "nginx doit écouter IPv6 aussi (sinon healthcheck localhost casse)"
    )


def test_pricing_lazy_import_mlflow():
    """Régression smoke C13.1 : `src/api/pipeline.py` charge `01_algorithmique.py`
    via importlib pour réutiliser `suggest_price`. Si mlflow_utils est importé au
    TOP de ce module, l'image API tire mlflow inutilement (~100 Mo) et plante
    (mlflow pas dans extra [api]). L'import doit rester LAZY dans `main()`.
    """
    import ast

    src = (DOCKER_DIR.parent.parent / "src" / "pricing" / "01_algorithmique.py").read_text(
        encoding="utf-8"
    )
    for node in ast.parse(src).body:
        if isinstance(node, ast.ImportFrom) and node.module == "src.mlops.mlflow_utils":
            raise AssertionError(
                "mlflow_utils importé au top de 01_algorithmique.py — "
                "doit être LAZY dans main() (cf. smoke C13.1, D-021)"
            )


def test_readme_explicite_pour_soutenance():
    """README infra/docker présent et liste les 3 images + volumes attendus."""
    src = _read("README.md")
    for image in ("rakuten/api:dev", "rakuten/frontend:dev", "rakuten/airflow:dev"):
        assert image in src
    # Volumes documentés (pas d'image qui prétend marcher seule).
    assert "data/embeddings" in src and "data/index" in src
    # Honnêteté : pas de variante GPU surpromue.
    assert "Pourquoi pas" in src and "CUDA" in src
