# 12 — Infrastructure (Docker, Compose, Kubernetes)

> Empaqueter l'application pour qu'elle tourne **partout à l'identique**, orchestrer ses
> nombreux services, et pouvoir la déployer/scaler.

---

## 1. La technologie : qu'est-ce que c'est ?

- **Docker** : met une application + ses dépendances dans un **conteneur** isolé → « ça marche
  sur ma machine » devient « ça marche partout pareil ».
- **Build multi-stage** : on construit dans une image « atelier » (avec les outils de build),
  puis on ne copie que le **strict nécessaire** dans une image finale légère → plus petit, plus
  sûr.
- **Docker Compose** : décrit et lance **plusieurs conteneurs ensemble** (l'API, la base, MinIO,
  MLflow, Grafana…) en une commande.
- **Kubernetes (k8s)** : pour la production à grande échelle — gère, redémarre et **scale**
  automatiquement les conteneurs sur plusieurs machines.

---

## 2. État de l'art

- **Multi-stage = standard** : sépare l'environnement de build de l'exécution → images plus
  petites (déploiement plus rapide, surface d'attaque réduite), base minimale, étapes nommées
  (`AS builder`), copie ordonnée pour profiter du **cache de couches**.
- **Compose** pour l'orchestration **locale** multi-conteneurs.
- **Kubernetes** : **Deployments** pour les services sans état, **StatefulSets** pour les bases
  (stockage persistant), **limites de ressources** par pod, **HPA** (autoscaling horizontal)
  selon CPU/mémoire.

---

## 3. Notre implémentation

| Brique | Où | Détail |
|---|---|---|
| Images | `infra/docker/Dockerfile.{api,frontend,airflow,mlflow}` | **multi-stage** (ex. API : `builder` → `runtime` sur `python:3.12-slim`) ; frontend : Node → **nginx** |
| Stack locale | `docker-compose.yml` (+ `.prod.yml`) | **14 services** unifiés + overlay production |
| Kubernetes | `infra/k8s/` | namespace, configmap, secrets (gabarit), MinIO, Postgres, MLflow, API, frontend, **ingress**, **HPA** (sur l'API), `kind-cluster`, `kustomization` |
| Outils | `Makefile` | `make up/down`, `make k8s-up/deploy/smoke` (cluster local **kind**) |

Choix : **une seule stack Compose** (source unique, overlay prod qui durcit), **images
multi-stage légères**, et des **manifestes k8s** réels (Deployments + StatefulSets + ingress +
autoscaling) déployables sur un cluster local **kind** pour la démonstration.

---

## 4. Résultats (mesurés)

- **14 services** orchestrés en une commande (`docker compose up -d`), tous *healthy*.
- **Images multi-stage** : build de l'API en `builder` → `runtime` slim (venv copié, pas les
  outils de build).
- **Manifestes k8s** appliqués sur **kind** + **ingress** (3 hôtes `*.localhost`) + **HPA** sur
  l'API → `make k8s-up && make k8s-deploy && make k8s-smoke`.
- **Tests de contrat infra** : `test_docker_compose.py`, `test_docker_images.py`,
  `test_k8s_manifests.py` (vérifient la cohérence des fichiers d'infra).

> 📊 **Chiffres slide** : « 14 services orchestrés », « images multi-stage », « k8s : Deployments
> + StatefulSets + ingress + HPA sur kind ». 📸 **Capture** : `docker compose ps` (tout healthy)
> + le schéma de la stack (1 boîte par service) + `kubectl get pods` sur kind.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Multi-stage + base slim** → conforme aux bonnes pratiques (taille/sécurité).
- ✅ **Compose unifié** + overlay prod → orchestration locale propre.
- ✅ **k8s réel** (pas juste un YAML jouet) : Deployments, StatefulSets, ingress, **HPA** →
  démontre la scalabilité.
- ✅ **Tests de contrat** sur l'infra → non-régression.

**Limites assumées (dont un fix transverse) :**
- ⚠️ **Image MLflow figée en 2.22.5** alors que le client est en 3.12 → incompatibilité qui
  bloque l'enregistrement de modèles vers le serveur conteneur (cf. thèmes MLflow/Registry).
  **Fix infra à faire** : bumper `Dockerfile.mlflow` vers une 3.x alignée. *(Backlog, repasse.)*
- **Conteneurs en root** : durcissement `USER` non-root prévu (post-MVP).
- **k8s en local (kind)** : prouve l'architecture, mais ce n'est pas un vrai cluster cloud.
- **Secrets = gabarits dev** (`secrets.example`, `minioadmin`) : à remplacer par de vrais
  secrets en prod (déjà garde-fou sur `prod-up`).

---

## 6. Références
- Docker Docs — *Multi-stage builds* — https://docs.docker.com/build/building/multi-stage/
- Northflank — *Docker build & buildx best practices* — https://northflank.com/blog/docker-build-and-buildx-best-practices-for-optimized-builds
- Kubegrade — *Kubernetes and microservices* — https://kubegrade.com/kubernetes-microservices/
- CloudOptimo — *Kubernetes for CI/CD (2025)* — https://www.cloudoptimo.com/blog/kubernetes-for-ci-cd-a-complete-guide-for-2025/

---

### En une phrase (pour la défense)
*« L'application est empaquetée en images Docker multi-stage légères, orchestrée en 14 services
via Compose, et déployable sur Kubernetes (Deployments, StatefulSets, ingress, autoscaling HPA)
sur un cluster local kind — le tout couvert par des tests de contrat d'infra. »*
