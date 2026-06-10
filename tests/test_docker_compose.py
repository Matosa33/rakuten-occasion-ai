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


# ─────────────────────────────────────────────────────────────────────────────
# Cycle 13.3 — Traefik gateway (D-026).
# Tests qui catchent des régressions réelles (pas de padding) :
#   1. service traefik présent
#   2. routing host-based déclaré pour les 3 backends
#   3. middlewares sec-headers + api-ratelimit définis et référencés par l'api
# ─────────────────────────────────────────────────────────────────────────────


def _labels(service: dict) -> list[str]:
    """Renvoie les labels d'un service comme liste (Compose accepte liste OU dict)."""
    lbls = service.get("labels") or []
    if isinstance(lbls, dict):
        return [f"{k}={v}" for k, v in lbls.items()]
    return list(lbls)


def test_traefik_service_declare():
    """Le reverse proxy Traefik est présent + monte le socket Docker (D-026)."""
    services = _load(COMPOSE)["services"]
    assert "traefik" in services, "service `traefik` manquant (D-026)"
    tk = services["traefik"]
    # Image v3.x (pas v2 ; v2 a une syntaxe middleware différente).
    assert str(tk.get("image", "")).startswith("traefik:v3"), "Traefik doit être en v3"
    # Socket Docker en RO (sinon le provider Docker n'a pas la liste des services).
    vols = tk.get("volumes", [])
    assert any("docker.sock" in v and ":ro" in v for v in vols), (
        "Traefik doit monter /var/run/docker.sock en RO"
    )


def test_routing_host_based_pour_chaque_backend():
    """Chaque backend public a un routeur Traefik avec sa règle Host(...) (D-026)."""
    services = _load(COMPOSE)["services"]
    expected = {
        "api": "api.localhost",
        "frontend": "rakuten.localhost",
        "airflow-webserver": "airflow.localhost",
    }
    for svc_name, host in expected.items():
        labels = _labels(services[svc_name])
        assert any(f"Host(`{host}`)" in lab for lab in labels), (
            f"Service `{svc_name}` doit router sur Host(`{host}`)"
        )
        # Doit traverser l'entrypoint `web` (pas un autre)
        assert any("entrypoints=web" in lab for lab in labels), (
            f"Service `{svc_name}` doit utiliser entrypoints=web"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cycle 13.4 — MinIO + MLflow tracking server (D-027).
# 2 tests qui catchent les vraies régressions de D-027 (sans padding).
# ─────────────────────────────────────────────────────────────────────────────


def test_services_C134_present_pour_rembourser_D023():
    """MinIO + Postgres dédié MLflow + serveur MLflow + init des buckets (D-027)."""
    services = _load(COMPOSE)["services"]
    for name in ("minio", "minio-init", "postgres-mlflow", "mlflow-server"):
        assert name in services, f"service C13.4 manquant : {name} (D-027)"
    # mlflow-server doit attendre Postgres + buckets MinIO créés.
    mlflow_deps = services["mlflow-server"].get("depends_on") or {}
    assert "postgres-mlflow" in mlflow_deps, "mlflow-server doit dépendre de postgres-mlflow"
    assert "minio-init" in mlflow_deps, "mlflow-server doit dépendre de minio-init"


def test_airflow_pointe_sur_mlflow_server_http_pas_sqlite():
    """Régression D-023 : les tâches Airflow doivent pousser au serveur MLflow HTTP
    (et donc artifacts dans MinIO S3), plus jamais en SQLite local hôte."""
    raw = COMPOSE.read_text(encoding="utf-8")
    # Le bloc anchor x-airflow-env défini une fois et réutilisé par les 3 services.
    assert "MLFLOW_TRACKING_URI: http://mlflow-server:5000" in raw, (
        "Airflow doit pointer sur le serveur MLflow HTTP (D-027), pas SQLite"
    )
    assert "MLFLOW_S3_ENDPOINT_URL: http://minio:9000" in raw, (
        "Airflow doit savoir où est l'endpoint S3 (MinIO) pour les artifacts"
    )
    # Pas de double config conflictuelle : aucune ligne sqlite:////opt/rakuten/mlflow.db ailleurs.
    assert raw.count("sqlite:////opt/rakuten/mlflow.db") == 0, (
        "Plus de tracking SQLite hôte dans le compose (D-027 supersede)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cycle 14.2 — Prometheus + Grafana (D-030).
# Sans padding : chaque test attrape une régression réelle observable LIVE.
# ─────────────────────────────────────────────────────────────────────────────


def test_services_prometheus_grafana_declares():
    """Les services obs C14.2 sont présents + montent leur config en RO (D-030)."""
    services = _load(COMPOSE)["services"]
    for name in ("prometheus", "grafana"):
        assert name in services, f"service C14.2 manquant : {name} (D-030)"

    # Prometheus charge le fichier scrape attendu.
    prom_vols = services["prometheus"].get("volumes", [])
    assert any("monitoring/prometheus/prometheus.yml" in v and ":ro" in v for v in prom_vols), (
        "prometheus doit bind-mounter monitoring/prometheus/prometheus.yml en RO"
    )

    # Grafana charge provisioning + dashboards en RO.
    g_vols = services["grafana"].get("volumes", [])
    assert any("monitoring/grafana/provisioning" in v and ":ro" in v for v in g_vols), (
        "grafana doit bind-mounter monitoring/grafana/provisioning en RO"
    )
    assert any("monitoring/grafana/dashboards" in v and ":ro" in v for v in g_vols), (
        "grafana doit bind-mounter monitoring/grafana/dashboards en RO"
    )

    # Grafana dépend de Prometheus (sinon datasource en erreur au boot).
    g_deps = services["grafana"].get("depends_on") or {}
    assert "prometheus" in g_deps, "grafana doit depends_on prometheus"


def test_traefik_active_metrics_prometheus():
    """Sans `--metrics.prometheus=true`, le job traefik dans prometheus.yml reste DOWN."""
    services = _load(COMPOSE)["services"]
    cmd = services["traefik"].get("command", [])
    assert any("metrics.prometheus=true" in str(c) for c in cmd), (
        "Traefik doit exposer ses métriques Prometheus (sinon scrape job traefik DOWN)"
    )


def test_dashboard_datasource_uid_match_le_provisioning():
    """Régression silencieuse : si on change l'UID d'un côté sans l'autre, les
    panels Grafana affichent 'Datasource not found' (visible seulement en UI)."""
    import json

    ds = yaml.safe_load(
        (ROOT / "monitoring/grafana/provisioning/datasources/prometheus.yml").read_text()
    )
    ds_uid = ds["datasources"][0]["uid"]

    dashboard = json.loads(
        (ROOT / "monitoring/grafana/dashboards/golden_signals.json").read_text(encoding="utf-8")
    )
    panel_uids = {p["datasource"]["uid"] for p in dashboard["panels"]}
    target_uids = {
        t["datasource"]["uid"]
        for p in dashboard["panels"]
        for t in p.get("targets", [])
        if isinstance(t.get("datasource"), dict)
    }

    # Tous les UIDs (panels + targets) doivent matcher l'UID du datasource provisionné.
    all_uids = panel_uids | target_uids
    assert all_uids == {ds_uid}, (
        f"UIDs dashboard {all_uids} ne matchent pas datasource provisionné {ds_uid!r}"
    )


def test_dashboard_couvre_4_golden_signals():
    """4 panels obligatoires (Latency, Traffic, Errors, Saturation) — sans ça
    la D-030 n'est pas honorée (SRE book § Monitoring distributed systems)."""
    import json

    dashboard = json.loads(
        (ROOT / "monitoring/grafana/dashboards/golden_signals.json").read_text(encoding="utf-8")
    )
    assert len(dashboard["panels"]) == 4, (
        "Dashboard doit avoir exactement 4 panels (golden signals)"
    )

    titles = " ".join(p["title"].lower() for p in dashboard["panels"])
    for signal in ("latency", "traffic", "error", "saturation"):
        assert signal in titles, f"signal '{signal}' absent des titres de panels"


# ─────────────────────────────────────────────────────────────────────────────
# Finding test interface (post-C14.99) — vrais bugs détectés en smoke E2E :
#   1. .env hôte non propagé au container API → /describe en mock silencieux
#   2. nginx `proxy_pass http://$var/;` ne strip pas /api/ (variable désactive
#      le rewrite auto) → frontend /api/health → 404 silencieux
# ─────────────────────────────────────────────────────────────────────────────


def test_api_compose_propage_env_file_hote():
    """Sans `env_file: .env`, le container API ne reçoit pas OPENROUTER_API_KEY
    → /describe dégrade en mock (D-013) sans warning. Régression silencieuse."""
    services = _load(COMPOSE)["services"]
    api = services["api"]
    env_file = api.get("env_file")
    assert env_file is not None, (
        "service `api` doit déclarer `env_file: .env` (sinon OPENROUTER_API_KEY perdue)"
    )
    # Compose accepte string, list[str] ou list[dict{path, required}].
    if isinstance(env_file, list):
        sources = []
        for ef in env_file:
            sources.append(ef["path"] if isinstance(ef, dict) else ef)
    else:
        sources = [env_file]
    assert ".env" in sources, f"api.env_file doit inclure .env (vu : {sources})"


def test_nginx_strip_api_prefix_avec_rewrite_explicite():
    """Régression bug critique frontend : `proxy_pass http://$var/;` avec variable
    désactive le path-rewrite auto de nginx → `/api/health` arrive tel quel au
    backend → 404. Le `rewrite ^/api/(.*) /$1 break;` est obligatoire."""
    nginx_conf = (ROOT / "infra" / "docker" / "nginx.conf").read_text(encoding="utf-8")
    assert "rewrite ^/api/(.*)" in nginx_conf, (
        "nginx.conf doit contenir le `rewrite ^/api/(.*)` pour strip /api/ avant proxy"
    )
    assert "break;" in nginx_conf, "le rewrite nginx doit utiliser le flag `break`"


def test_identify_request_image_url_optional():
    """Le MVP text-only (D-014) doit accepter un body sans `image_url`. Régression :
    `Field(...)` rendait le champ obligatoire mais l'endpoint l'ignore."""
    from src.api.schemas import IdentifyRequest

    # Construction sans image_url → ne doit pas lever
    req = IdentifyRequest(text_hint="iPhone 13")
    assert req.image_url == "", "image_url default doit être '' (MVP text-only)"
    assert req.text_hint == "iPhone 13"


# ─────────────────────────────────────────────────────────────────────────────
# Cycle 15.3 (D-034) — garde-fou command base ↔ overlay prod.
# L'audit 15.0 a trouvé que le command Traefik prod (C13.3) avait perdu les
# flags metrics ajoutés en C14.2 au command de base : un `command:` overlay
# REMPLACE (ne merge pas) → régression d'observabilité invisible en prod.
# ─────────────────────────────────────────────────────────────────────────────


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader qui tolère les tags Compose custom (`!reset`, `!override`) —
    PyYAML pur lèverait ConstructorError sur l'overlay prod."""


_ComposeLoader.add_multi_constructor(
    "!",
    lambda loader, suffix, node: None,  # les valeurs taguées ne nous servent pas
)


def _load_prod() -> dict:
    return yaml.load(PROD.read_text(encoding="utf-8"), Loader=_ComposeLoader)  # noqa: S506 — loader dérivé de SafeLoader


def test_traefik_command_overlay_prod_garde_les_flags_critiques():
    """Tout flag critique du command Traefik de base doit exister dans l'overlay
    prod (sauf ceux retirés VOLONTAIREMENT : dashboard insecure, log level)."""
    base = _load(COMPOSE)["services"]["traefik"]["command"]
    prod = _load_prod()["services"]["traefik"]["command"]

    # Flags retirés volontairement en prod (documentés dans l'overlay).
    intentionally_dropped = {"--api.dashboard=true", "--api.insecure=true", "--log.level=INFO"}

    missing = [flag for flag in base if flag not in prod and flag not in intentionally_dropped]
    assert not missing, (
        f"Flags du command Traefik de base absents de l'overlay prod : {missing}. "
        "Un command overlay REMPLACE le command de base — resynchroniser "
        "docker-compose.prod.yml (cf. erreur compose-overlay-command-remplace)."
    )


def test_prod_overlay_couvre_tous_les_services_long_running():
    """Chaque service long-running du compose de base doit avoir un restart
    policy en prod (l'audit 15.0 a trouvé 6 services oubliés de l'overlay)."""
    base_services = _load(COMPOSE)["services"]
    prod_services = _load_prod()["services"]

    # One-shot exclus : init containers (restart: "no" voulu).
    one_shot = {"minio-init", "airflow-init"}
    long_running = set(base_services) - one_shot

    missing_restart = [
        name
        for name in sorted(long_running)
        if prod_services.get(name, {}).get("restart") != "unless-stopped"
    ]
    assert not missing_restart, (
        f"Services sans `restart: unless-stopped` dans l'overlay prod : {missing_restart}"
    )


def test_middlewares_securite_et_ratelimit_appliques():
    """sec-headers global + api-ratelimit appliqués à l'API (D-026)."""
    services = _load(COMPOSE)["services"]
    # Middlewares déclarés sur le service traefik (point unique).
    tk_labels = _labels(services["traefik"])
    assert any("middlewares.sec-headers." in lab for lab in tk_labels), (
        "middleware sec-headers manquant"
    )
    assert any("middlewares.api-ratelimit." in lab for lab in tk_labels), (
        "middleware api-ratelimit manquant"
    )
    # L'API consomme les deux (en référençant @docker).
    api_labels = _labels(services["api"])
    api_mw = next((lab for lab in api_labels if "routers.api.middlewares=" in lab), "")
    assert "sec-headers@docker" in api_mw and "api-ratelimit@docker" in api_mw, (
        f"L'API doit appliquer sec-headers + api-ratelimit ; vu : {api_mw}"
    )
