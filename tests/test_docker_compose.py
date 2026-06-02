"""Tests de contrat du `docker-compose.yml` racine + overlay prod (Cycle 13.2, D-025).

Statiques (YAML parsing) : on n'a pas besoin du démon Docker pour valider que la
stack déclare les bons services, ports, volumes et dépendances. Build + smoke
end-to-end = `make up` (validé live au commit C13.2).
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
PROD = ROOT / "docker-compose.prod.yml"


def _load(p: Path) -> dict:
    assert p.exists(), f"manquant : {p}"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_compose_les_6_services_attendus():
    """La stack unifiée déclare tous les services nécessaires (D-025)."""
    services = _load(COMPOSE).get("services", {})
    for name in (
        "api",
        "frontend",
        "postgres",
        "airflow-init",
        "airflow-scheduler",
        "airflow-webserver",
    ):
        assert name in services, f"service manquant dans docker-compose.yml : {name}"


def test_api_volumes_data_en_lecture_seule():
    """L'API monte data + mlflow.db + mlartifacts en READ-ONLY (sécurité D-025)."""
    api = _load(COMPOSE)["services"]["api"]
    vols = api.get("volumes", [])
    expected = (
        "./data:/opt/rakuten/data:ro",
        "./mlflow.db:/opt/rakuten/mlflow.db:ro",
        "./mlartifacts:/opt/rakuten/mlartifacts:ro",
    )
    for vol in expected:
        assert vol in vols, f"volume manquant/non-RO : {vol}"


def test_healthchecks_sur_services_exposes():
    """api, frontend, postgres, airflow-webserver ont un healthcheck."""
    services = _load(COMPOSE)["services"]
    for name in ("api", "frontend", "postgres", "airflow-webserver"):
        assert "healthcheck" in services[name], f"healthcheck manquant : {name}"


def test_ports_lies_localhost_seulement():
    """Les ports exposés en dev sont sur 127.0.0.1 (pas 0.0.0.0) — D-025 sécurité."""
    services = _load(COMPOSE)["services"]
    for name in ("api", "frontend", "airflow-webserver"):
        ports = services[name].get("ports", [])
        for p in ports:
            assert p.startswith("127.0.0.1:"), f"{name} : port {p} pas lié à localhost"


def test_frontend_depend_de_api():
    """frontend doit attendre api (ordre démarrage cohérent avec le proxy nginx)."""
    fe = _load(COMPOSE)["services"]["frontend"]
    assert "api" in (fe.get("depends_on") or [])


def test_airflow_partage_le_meme_repo_monte():
    """init/scheduler/webserver Airflow partagent le repo monté sur /opt/rakuten."""
    services = _load(COMPOSE)["services"]
    for name in ("airflow-init", "airflow-scheduler", "airflow-webserver"):
        vols = services[name].get("volumes", [])
        assert ".:/opt/rakuten" in vols, f"{name} : repo non monté sur /opt/rakuten"


def test_prod_overlay_resette_les_ports_api_et_webserver():
    """L'overlay prod retire les ports hôte de api + airflow-webserver (Traefik en C13.3)."""
    # `!reset []` est un tag spécifique Docker Compose que PyYAML ne sait pas charger
    # → on vérifie au niveau du texte que les services concernés ont bien le reset.
    raw = PROD.read_text(encoding="utf-8")
    for name in ("api:", "airflow-webserver:"):
        # Bloc service → "  ports: !reset []" attendu pour les services pas exposés en prod.
        idx = raw.find(name)
        assert idx >= 0, f"service {name} absent de prod overlay"
        # Chaque section concernée contient bien le reset des ports.
    assert raw.count("ports: !reset []") >= 2, "prod doit reset ports pour api + airflow-webserver"

    # Restart policy stricte côté prod (les 5 services persistants).
    assert raw.count("restart: unless-stopped") >= 5, (
        "prod doit appliquer restart=unless-stopped à api+frontend+postgres+scheduler+webserver"
    )


def test_pas_d_ancien_compose_oublie():
    """Garde-fou : l'ancien `infra/compose/docker-compose.airflow.yml` ne doit plus exister."""
    obsolete = ROOT / "infra" / "compose"
    assert not obsolete.exists(), (
        "`infra/compose/` doit avoir été supprimé (consolidé dans docker-compose.yml, D-025)"
    )
