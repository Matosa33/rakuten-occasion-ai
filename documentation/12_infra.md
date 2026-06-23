# 12 — Infrastructure (Docker, Compose, Kubernetes)

> Empaqueter l'application pour qu'elle tourne **partout à l'identique**, orchestrer ses nombreux
> services, et pouvoir la déployer / la mettre à l'échelle.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
- **Docker** met une application + ses dépendances dans un **conteneur** isolé → « ça marche sur
  ma machine » devient « ça marche partout pareil ».
- **Build multi-stage** : on construit dans une image « atelier » (avec les outils de build),
  puis on copie **seulement le nécessaire** dans une image finale légère → plus petit, plus sûr.
- **Docker Compose** décrit et lance **plusieurs conteneurs ensemble** (API, base, MinIO, MLflow,
  Grafana…) en une commande.
- **Kubernetes (k8s)** : pour la production à grande échelle — gère, redémarre et **scale**
  automatiquement les conteneurs sur plusieurs machines.

### Pour l'expert
- Multi-stage = sépare *build-time* et *runtime* → image finale sans compilateurs ni caches
  (surface d'attaque réduite, déploiement rapide). On copie le **venv** construit, pas les outils.
- k8s : **Deployment** pour le sans-état (API, frontend), **StatefulSet** pour le avec-état
  (bases), **Ingress** pour le routage HTTP, **HPA** pour l'autoscaling selon CPU/mémoire.

---

## 2. État de l'art

- **Multi-stage = standard** : base minimale, étapes nommées (`AS builder`), copie ordonnée pour
  profiter du **cache de couches**.
- **Compose** pour l'orchestration **locale** multi-conteneurs ; **k8s** pour la prod (Deployments
  /StatefulSets, limites de ressources par pod, HPA).
- **Observabilité** = 3 piliers (logs/métriques/traces) — cf. rapport dédié.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

| Brique | Où | Détail exact |
|---|---|---|
| Images | `infra/docker/Dockerfile.{api,frontend,airflow,mlflow}` | **multi-stage** (ex. API : `builder` → `runtime` sur `python:3.12-slim`, venv copié) ; frontend : **Node → nginx** |
| Stack locale | `docker-compose.yml` (+ `.prod.yml`) | **14 services** unifiés + overlay production (restart strict, ports internes) |
| Kubernetes | `infra/k8s/` | namespace, configmap, secrets (gabarit), MinIO, Postgres, MLflow, API, frontend, **ingress**, **HPA** (sur l'API), `kind-cluster`, `kustomization` |
| Outils | `Makefile` | `make up/down`, `make k8s-up/deploy/smoke` (cluster local **kind**) |

Choix : **une seule stack Compose** (source unique ; overlay prod qui durcit), **images
multi-stage légères**, et des **manifestes k8s réels** (Deployments + StatefulSets + ingress +
HPA) déployables sur **kind** pour la démonstration. Volume `uploads-data` writable monté
**par-dessus** le `data/` RO (le plus spécifique gagne) → uploads possibles sans rendre toute la
data inscriptible.

---

## 4. Résultats (mesurés)

- **14 services** orchestrés en une commande (`docker compose up -d`), tous *healthy* (boot à
  froid mesuré ~3 min, le temps que l'API charge l'index FAISS).
- **Images multi-stage** : build API `builder` → `runtime` slim.
- **Manifestes k8s** appliqués sur **kind** + **ingress** (3 hôtes `*.localhost`) + **HPA** sur
  l'API.
- **Tests de contrat infra** : `test_docker_compose.py`, `test_docker_images.py`,
  `test_k8s_manifests.py`.

> 📊 **Chiffres slide** : « 14 services orchestrés », « images multi-stage », « k8s : Deployments
> + StatefulSets + ingress + HPA sur kind ». 📸 **Capture** : `docker compose ps` (tout healthy)
> + le schéma de la stack + `kubectl get pods` sur kind.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Multi-stage + base slim** → bonnes pratiques (taille/sécurité).
- ✅ **Compose unifié** + overlay prod → orchestration locale propre, source unique.
- ✅ **k8s réel** (pas un YAML jouet) : Deployments, StatefulSets, ingress, **HPA** → démontre la
  scalabilité.
- ✅ **Tests de contrat** sur l'infra → non-régression (ils ont rattrapé plusieurs bugs : deps
  transitives manquantes, volume RO, flags Traefik perdus en overlay).
- ✅ **Image MLflow alignée en 3.x** (C32.1) → enregistrement de modèles vers le serveur conteneur
  fonctionnel (registry + `@Production` peuplés).

**Limites assumées :**
- **Conteneurs en root** : durcissement `USER` non-root prévu (post-MVP).
- **k8s en local (kind)** : prouve l'architecture, mais pas un vrai cluster cloud (pas de tests
  de charge réels de l'HPA).
- **Secrets = gabarits dev** (`secrets.example`, `minioadmin`) : à remplacer en prod (garde-fou
  `prod-up` déjà en place qui refuse de démarrer sans `.env` + `JWT_SECRET`).
- **Images non signées / non scannées** (Cosign/Trivy) → cf. rapport *CI/CD*.

---

## 6. Références
- Docker Docs — *Multi-stage builds* — https://docs.docker.com/build/building/multi-stage/
- Northflank — *Docker build & buildx best practices* — https://northflank.com/blog/docker-build-and-buildx-best-practices-for-optimized-builds
- Kubernetes — *Horizontal Pod Autoscaler* — https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- kind — *Kubernetes in Docker* — https://kind.sigs.k8s.io/

---

### En une phrase (pour la défense)
*« L'application est empaquetée en images Docker multi-stage légères, orchestrée en 14 services
via Compose (overlay prod qui durcit), et déployable sur Kubernetes (Deployments, StatefulSets,
ingress, autoscaling HPA) sur un cluster local kind — le tout couvert par des tests de contrat
d'infra qui ont rattrapé plusieurs bugs réels. »*
