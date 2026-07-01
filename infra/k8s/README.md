# Stack Rakuten sur Kubernetes

Déploiement de la stack ML core (API + Frontend + MinIO + MLflow + Postgres) sur
**Kubernetes**, via un cluster local **kind**. Routage host-based identique à
la stack Compose (`api.localhost`, `rakuten.localhost`, `mlflow.localhost`).

## Périmètre

| Service | Présent en K8s | Notes |
|---|---|---|
| API FastAPI | ✅ Deployment 2 replicas + HPA CPU 70% (2→5) | Sans data volume → `/health` 200 (lifespan tolérant) |
| Frontend Vite/Nginx | ✅ Deployment 2 replicas | |
| MinIO | ✅ StatefulSet + PVC 5 Gi | Buckets `mlflow-artifacts` + `dvc` créés par Job init |
| postgres-mlflow | ✅ StatefulSet + PVC 2 Gi | Backend MLflow |
| MLflow server | ✅ Deployment | Backend Postgres, artifacts S3 MinIO |
| Airflow | ❌ **non porté** | Reste sur Compose. Orchestration via Compose, serving via Kubernetes. |
| Traefik | ❌ remplacé par **ingress-nginx** | Cohérence des hôtes `*.localhost` préservée. |

## Pré-requis

- Docker Desktop running.
- `kubectl` (déjà installé sur le poste : v1.34.1).
- `kind` (binaire téléchargé localement par `make k8s-up`, dans `.local/bin/`).

## Commandes

```bash
make k8s-up        # 1) crée le cluster kind ; 2) installe ingress-nginx
make k8s-load      # charge les 3 images locales (api, frontend, mlflow) dans le cluster
make k8s-deploy    # copie secrets.yaml depuis le gabarit + `kubectl apply -k`
make k8s-smoke     # curl via l'ingress sur les 3 hôtes (.localhost:8095)
make k8s-down      # supprime le cluster (idempotent)
```

## Architecture

```
                 host:8095
                     │
                     ▼
        ┌─────────────────────┐
        │  ingress-nginx      │  (Host header routing)
        └────┬────┬────┬──────┘
             │    │    │
   rakuten.  │    │    │  mlflow.
   localhost │    │    │  localhost
             │    │    │
             ▼    │    ▼
        ┌────────┐│┌──────────────┐
        │frontend│││ mlflow-server│
        │ 2 reps │││  (Postgres + │
        └────────┘││   S3 MinIO)  │
                  │└──────────────┘
       api.       │
       localhost  │
                  ▼
            ┌────────────┐
            │ api (HPA)  │
            │ 2→5 reps   │
            └────────────┘
```

Tous les services dans le namespace `rakuten`. ConfigMap (URLs internes) + Secret
(MinIO creds, Postgres password) - `secrets.yaml` est **gitignored** (jamais commité).

## Limitations

- **API sans données ML** : pas de PVC pour `data/embeddings` ni `data/index`
  (13,2 Go via `kind load` = trop lent et hors-scope). `/health` → 200 (services
  marqués `false`), `/identify` retournerait 503. Pour une vraie démo K8s,
  monter les artefacts via un PVC initialisé (hors scope actuel).
- **HPA custom metric** Prometheus = différé (volet observabilité).
- **HPA CPU `<unknown>`** par défaut dans kind : metrics-server n'est pas
  installé d'office. Le HPA est créé et accepté par K8s, mais ne scalera pas
  tant que metrics-server n'est pas là. Sur Linux, installer avec :
  `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`
  (patch `--kubelet-insecure-tls` requis sur kind).
- **TLS** sur l'ingress = différé (HTTP only en dev).
