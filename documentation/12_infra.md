# 12. Infrastructure (Docker, Docker Compose, Kubernetes)

> But du composant : empaqueter l'application pour qu'elle tourne partout à l'identique,
> lancer ses nombreux services ensemble en une seule commande, et savoir la déployer et la
> dimensionner sur plusieurs machines si la charge augmente.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre en partant de zéro

Une application moderne n'est pas un seul programme : c'est une base de données, un serveur
web, un moteur de calcul, des outils de surveillance, etc. Les faire fonctionner ensemble,
sur la machine du développeur comme sur un serveur de production, est un problème en soi.
Trois outils résolvent ce problème, du plus simple au plus avancé.

- **Docker** met une application et tout ce dont elle a besoin (les bibliothèques de code,
  les réglages) dans une boîte étanche appelée un conteneur. Résultat : la phrase « ça marche
  sur ma machine » devient « ça marche partout pareil », car la boîte emporte son
  environnement avec elle.

- **Le build multi-étapes** (multi-stage) est une façon de fabriquer cette boîte en deux
  temps. On construit d'abord dans une image atelier qui contient les gros outils de
  compilation, puis on recopie uniquement le strict nécessaire dans une image finale, plus
  petite. L'image livrée est donc plus légère et plus sûre, car elle ne traîne ni
  compilateur ni fichiers temporaires.

- **Docker Compose** décrit et lance plusieurs conteneurs ensemble (le serveur applicatif,
  les bases de données, le stockage de fichiers, les tableaux de bord, etc.) à partir d'un
  seul fichier texte et d'une seule commande.

- **Kubernetes** (souvent abrégé en k8s) est l'outil de la production à grande échelle. Il
  gère des conteneurs répartis sur plusieurs machines : il les redémarre quand ils tombent,
  et il en ajoute ou en retire automatiquement selon la charge (cette capacité à grossir ou
  rétrécir tout seul s'appelle l'autoscaling).

### Pour aller plus loin (lecteur technique)

- Le build multi-étapes sépare le moment de la construction (build-time, avec compilateurs et
  caches) du moment de l'exécution (runtime). On copie dans l'image finale uniquement
  l'environnement Python prêt à l'emploi (un dossier isolé appelé venv, ou environnement
  virtuel, qui contient toutes les bibliothèques installées), pas les outils qui l'ont
  produit. Bénéfices : surface d'attaque réduite, image plus petite, déploiement plus rapide.

- Côté Kubernetes, on distingue deux types de composants. Un **Deployment** sert les services
  sans mémoire propre, c'est-à-dire interchangeables (le serveur applicatif, le frontend) :
  on peut en lancer plusieurs copies identiques. Un **StatefulSet** sert les services avec
  mémoire, qui possèdent leurs propres données (les bases de données, le stockage de
  fichiers), et qui ont besoin d'une identité réseau stable et d'un disque dédié. Le routage
  du trafic web entrant passe par un **Ingress** (l'aiguilleur d'entrée), et l'autoscaling
  par un **HPA** (Horizontal Pod Autoscaler, le composant qui ajoute ou retire des copies
  selon le CPU ou la mémoire).

---

## 2. Ce que fait l'état de l'art

- Le build multi-étapes est la pratique standard : on part d'une image de base minimale, on
  nomme chaque étape (par exemple `AS builder`), et on ordonne les copies pour profiter du
  cache de couches. Concrètement, Docker garde en mémoire les étapes qui n'ont pas changé,
  ce qui évite de tout reconstruire à chaque modification.

- Docker Compose est le standard pour orchestrer plusieurs conteneurs en local, sur le poste
  du développeur. Kubernetes est le standard pour la production : Deployments et StatefulSets,
  limites de ressources fixées pour chaque conteneur, autoscaling par HPA.

- La surveillance d'une application en production repose sur trois piliers : les journaux
  d'événements (logs), les mesures chiffrées (métriques), et le suivi du parcours d'une
  requête à travers les services (traces). Notre stack intègre les deux premiers piliers via
  des conteneurs dédiés décrits ci-dessous (Prometheus collecte les mesures, Grafana les
  affiche).

---

## 3. Notre implémentation (précisément ce qui a été fait)

### 3.1 Les images Docker (quatre recettes de construction)

Quatre fichiers de construction (les Dockerfiles) sont rangés dans `infra/docker/`.

| Image | Fichier | Construction exacte |
|---|---|---|
| Serveur applicatif (API) | `infra/docker/Dockerfile.api` | Multi-étapes sur la base `python:3.12-slim` : une étape `builder` installe tout dans un environnement virtuel isolé, une étape `runtime` ne reprend que cet environnement plus l'outil `curl`. La version processeur de la bibliothèque de calcul PyTorch est imposée explicitement, pour éviter de télécharger la variante carte graphique (environ 3 Go inutiles sur une machine sans GPU). |
| Frontend (site web) | `infra/docker/Dockerfile.frontend` | Multi-étapes : l'étape `node:20-alpine` compile le site (commande `npm ci` puis `npm run build`), l'étape finale `nginx:1.27-alpine` sert les fichiers produits et redirige les appels vers l'API. |
| Orchestrateur de ré-entraînement (Airflow) | `infra/docker/Dockerfile.airflow` | Part de l'image officielle `apache/airflow:2.10.5-python3.12`, ajoute `git`, puis installe le code du projet. Cet orchestrateur planifie les tâches de calcul mais n'utilise jamais la carte graphique. |
| Serveur de suivi des modèles (MLflow) | `infra/docker/Dockerfile.mlflow` | Part de `python:3.12-slim` et installe MLflow en version 3.x, plus les pilotes pour parler à la base PostgreSQL et au stockage de fichiers. La version 3.x est imposée pour rester alignée avec le client : un serveur en version 2.x renverrait une erreur sur la nouvelle façon d'enregistrer les modèles. |

Le serveur applicatif et le site web n'embarquent que la version processeur des
bibliothèques, sans rien de lié à la carte graphique. C'est un choix assumé : la promesse de
démonstration vise une machine sans GPU, et l'encodage d'images sur carte graphique est isolé
ailleurs, hors de l'API.

### 3.2 La stack locale : quatorze services en une commande

Un unique fichier, `docker-compose.yml` à la racine du dépôt, décrit quatorze services qui
démarrent ensemble avec `docker compose up -d`. Les voici, regroupés par rôle.

- **Servir l'utilisateur** : `api` (le serveur applicatif qui répond aux demandes
  d'identification de produit, d'estimation de prix et de génération de description),
  `frontend` (le site web), et `traefik` (l'aiguilleur d'entrée qui répartit le trafic, voir
  plus bas).
- **Stocker et suivre les modèles** : `minio` (un stockage de fichiers compatible avec le
  standard du cloud, qui héberge deux espaces nommés `mlflow-artifacts` et `dvc`),
  `minio-init` (une tâche jetable qui crée ces deux espaces au démarrage), `postgres-mlflow`
  (la base de données du suivi des modèles), et `mlflow-server` (le serveur de suivi
  lui-même).
- **Orchestrer le ré-entraînement** : `postgres` (la base de données d'Airflow),
  `airflow-init` (tâche jetable qui prépare cette base et crée le compte administrateur),
  `airflow-scheduler` (qui déclenche les tâches planifiées) et `airflow-webserver`
  (l'interface de pilotage).
- **Surveiller** : `prometheus` (qui collecte régulièrement les mesures chiffrées de l'API,
  de l'aiguilleur et de lui-même), `pushgateway` (un point de collecte pour les mesures des
  tâches ponctuelles, par exemple les contrôles de dérive des données), et `grafana` (les
  tableaux de bord qui affichent tout cela).

Détail de sécurité : en mode développement, chaque port est lié à `127.0.0.1`, c'est-à-dire
n'écoute que la machine locale et n'est pas exposé au réseau extérieur.

### 3.3 Deux façons d'accéder à l'application en local

L'aiguilleur d'entrée s'appelle Traefik (version 3.2). Il lit la liste des conteneurs via une
connexion en lecture seule au démon Docker, et route les requêtes selon le nom de domaine
demandé. Deux modes d'accès coexistent.

- **Accès direct** à chaque service, pratique pour le débogage. Par défaut : le site sur le
  port 8082, l'API sur 8010, l'interface Airflow sur 8088, le serveur MLflow sur 5000, la
  console de stockage MinIO sur 9011. Tous ces ports sont personnalisables via un fichier de
  configuration `.env` si un autre logiciel les occupe déjà.
- **Accès unifié** derrière l'aiguilleur, proche de la production : `rakuten.localhost` mène
  au site, `api.localhost` à l'API, `airflow.localhost` à Airflow, `mlflow.localhost` au
  serveur MLflow, le tout sur le port 8090. Les adresses en `.localhost` se résolvent
  automatiquement sans toucher aux réglages réseau de la machine.

L'aiguilleur applique deux protections à l'API : des en-têtes de sécurité standard, et une
limite de débit (en moyenne 100 requêtes, avec une tolérance de pointe de 50) pour éviter la
surcharge ou les abus.

### 3.4 Le mode production : un calque qui durcit la stack

Un second fichier, `docker-compose.prod.yml`, se superpose au premier sans le réécrire. Il
applique trois changements : une politique de redémarrage stricte (`unless-stopped`, qui fait
survivre les services aux pannes et aux redémarrages de la machine), la fermeture des ports
directs (en production, seul l'aiguilleur reçoit le trafic), et l'unique exception du site
web qui reste exposé puisque c'est le point d'entrée de l'utilisateur final.

Un garde-fou empêche un démarrage dangereux : la commande de lancement en production refuse de
partir s'il manque un fichier `.env`, ou si la clé secrète de signature des jetons
d'authentification (`JWT_SECRET`) n'y figure pas. Sans cela, la stack tournerait avec les
identifiants de démonstration publics, ce qui serait une faille.

### 3.5 Le détail délicat : un dossier d'envoi inscriptible par-dessus des données en lecture seule

Le serveur applicatif monte les données du projet en lecture seule, car il ne doit jamais
modifier les fichiers de modèles. Mais les photos envoyées par un vendeur, elles, doivent
pouvoir s'écrire. La solution : un volume nommé et inscriptible (`uploads-data`) est monté
exactement par-dessus le sous-dossier `uploads`. La règle de Docker veut que le montage le
plus précis l'emporte : le sous-dossier devient inscriptible, tout le reste reste protégé.
Sans cette astuce, l'envoi d'une photo échouait avec une erreur de système de fichiers en
lecture seule.

Note sur le temps de démarrage : la vérification de bonne santé du serveur applicatif tolère
jusqu'à 300 secondes au premier lancement. C'est le temps nécessaire pour charger l'index de
recherche FAISS, un fichier de 13,8 Go. FAISS est une bibliothèque qui retrouve très vite,
parmi des millions d'éléments, ceux qui ressemblent le plus à une image donnée. Sous Windows,
le chargement de ce gros fichier à travers Docker Desktop peut prendre de 5 à 15 minutes ;
sous Linux il est quasi instantané.

### 3.6 Le déploiement Kubernetes (manifestes réels)

Le dossier `infra/k8s/` contient des manifestes Kubernetes complets et fonctionnels, pas une
maquette. Ils sont conçus pour tourner sur un cluster local appelé kind (Kubernetes in
Docker, un outil qui simule un vrai cluster Kubernetes à l'intérieur de conteneurs Docker, ce
qui permet de démontrer l'architecture sans louer de serveurs cloud).

Les éléments présents, dans l'ordre :

- un espace de noms dédié (`rakuten`) qui isole tous les objets du projet ;
- un dictionnaire de réglages non secrets (ConfigMap) et un gabarit de secrets (le vrai
  fichier de secrets n'est jamais versionné, il se crée à partir du gabarit) ;
- le stockage de fichiers MinIO en StatefulSet, avec une tâche jetable qui crée les deux
  espaces de stockage ;
- la base de données PostgreSQL de MLflow en StatefulSet ;
- le serveur de suivi MLflow en Deployment ;
- le serveur applicatif (API) en Deployment, lancé en deux copies, accompagné de son
  autoscaler ;
- le site web (frontend) en Deployment, lui aussi en deux copies ;
- l'aiguilleur d'entrée (Ingress) qui route trois noms de domaine : `rakuten.localhost` vers
  le site, `api.localhost` vers l'API, `mlflow.localhost` vers le serveur MLflow.

Paramètres exacts du serveur applicatif : chaque copie demande au minimum 200 millicpu (soit
un cinquième de cœur de processeur) et 512 Mo de mémoire, avec un plafond de 1 cœur entier et
2 Go de mémoire. L'autoscaler maintient entre 2 et 5 copies, et en ajoute une nouvelle dès que
l'usage moyen du processeur dépasse 70 %. Le site web demande 50 millicpu et 64 Mo de mémoire
par copie, plafonné à 200 millicpu et 256 Mo.

Comme les images sont locales (chargées dans le cluster avec `kind load`, sans passer par un
entrepôt d'images distant), la règle de récupération est fixée à `IfNotPresent` : Kubernetes
utilise l'image déjà présente au lieu d'aller la télécharger, ce qui éviterait sinon un échec.

### 3.7 Les commandes prêtes à l'emploi (Makefile)

Le fichier `Makefile` à la racine fournit des raccourcis. Pour la stack locale : `make up`
(construit et démarre tout), `make down` (arrête en préservant les données), `make ps`
(affiche l'état), `make prod-up` (lance le calque de production avec ses garde-fous). Pour
Kubernetes : `make k8s-up` (crée le cluster kind et installe l'aiguilleur d'entrée),
`make k8s-load` (charge les images locales dans le cluster), `make k8s-deploy` (applique tous
les manifestes), `make k8s-smoke` (teste les trois adresses), `make k8s-down` (supprime le
cluster).

---

## 4. Résultats mesurés

- Quatorze services s'orchestrent en une seule commande (`docker compose up -d`), tous en bon
  état de santé. Le démarrage à froid mesuré avoisine trois minutes, le temps que le serveur
  applicatif charge l'index de recherche FAISS.
- Les images du serveur applicatif et du site web sont bien construites en deux étapes
  (atelier puis image finale légère).
- Les manifestes Kubernetes s'appliquent sans erreur sur le cluster local kind, avec
  l'aiguilleur d'entrée routant trois adresses en `.localhost`, et l'autoscaler actif sur le
  serveur applicatif.
- Trois fichiers de tests automatiques vérifient le contrat de l'infrastructure :
  `tests/test_docker_compose.py` (les services, ports, volumes et dépendances de la stack),
  `tests/test_docker_images.py` (la bonne forme des recettes de construction), et
  `tests/test_k8s_manifests.py` (la cohérence des manifestes Kubernetes, par exemple les
  bornes de l'autoscaler et les adresses de l'aiguilleur).

> Drapeau slide. Chiffres à montrer : « 14 services orchestrés en une commande »,
> « images Docker en deux étapes, légères », « Kubernetes : Deployments + StatefulSets +
> Ingress + autoscaler sur le serveur applicatif, démontré sur cluster local kind ».
> Captures : `docker compose ps` (tous les services en bonne santé), le schéma de la stack,
> et `kubectl get pods` sur le cluster kind.

---

## 5. Regard critique (état de l'art comparé à notre travail)

### Points solides

- Construction en deux étapes sur une base minimale : conforme aux bonnes pratiques de taille
  et de sécurité.
- Une seule description de stack pour le développement, durcie par un calque de production :
  source unique, pas de risque de divergence entre les deux versions.
- Du Kubernetes réel et non un fichier jouet : Deployments, StatefulSets, aiguilleur d'entrée
  et autoscaler, ce qui démontre concrètement la capacité à monter en charge.
- Des tests de contrat sur l'infrastructure, qui ont rattrapé plusieurs vrais défauts : des
  bibliothèques nécessaires mais oubliées dans une image, le problème du dossier d'envoi en
  lecture seule, et des réglages de l'aiguilleur perdus lors du passage en mode production.
- Le serveur de suivi MLflow est aligné en version 3.x, ce qui rend l'enregistrement des
  modèles vers le serveur conteneurisé pleinement fonctionnel.

### Limites assumées

- Les conteneurs tournent sous le compte administrateur interne (root). Le passage à un compte
  non privilégié est une amélioration prévue après cette première version.
- Le déploiement Kubernetes se fait sur un cluster local kind : il prouve l'architecture, mais
  ce n'est pas un vrai cluster cloud, et l'autoscaler n'a donc pas été éprouvé par de vrais
  tests de charge.
- Les secrets fournis sont des valeurs de démonstration (par exemple le couple
  `minioadmin`/`minioadmin`), à remplacer impérativement en production. Le garde-fou évoqué
  plus haut empêche déjà un démarrage en production sans secrets réels.
- Les images ne sont ni signées ni passées au scanner de vulnérabilités. Signer une image
  prouve son origine, et la scanner détecte les failles connues de ses composants : ces deux
  étapes restent à ajouter dans la chaîne d'intégration et de livraison automatisée.

---

## 6. Références

- Docker Docs, *Multi-stage builds* : https://docs.docker.com/build/building/multi-stage/
- Northflank, *Docker build & buildx best practices* : https://northflank.com/blog/docker-build-and-buildx-best-practices-for-optimized-builds
- Kubernetes, *Horizontal Pod Autoscaler* : https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- kind, *Kubernetes in Docker* : https://kind.sigs.k8s.io/

---

### En une phrase (pour la défense)

> L'application est empaquetée en images Docker construites en deux étapes, donc légères ;
> elle s'orchestre en quatorze services via Docker Compose (avec un calque de production qui
> durcit les réglages), et elle est déployable sur Kubernetes (Deployments, StatefulSets,
> aiguilleur d'entrée, autoscaler) sur un cluster local kind, le tout couvert par des tests
> automatiques d'infrastructure qui ont rattrapé plusieurs défauts réels.
