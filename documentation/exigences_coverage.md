# Couverture du projet face aux exigences attendues

Cette page répond d'un coup d'oeil à une seule question : « le projet couvre-t-il bien tout ce qui
était demandé ? ». Elle confronte ce que le cahier des charges attendait, organisé en quatre grandes
phases, avec ce qui est réellement présent et fonctionnel dans le dépôt de code.

Pour comprendre le projet en une phrase : il s'agit d'un assistant qui aide un vendeur de produits
d'occasion (électronique) à créer une annonce de qualité à partir d'une simple photo. À partir de
l'image, le système identifie le produit, propose une catégorie précise, pré-remplit les
caractéristiques, rédige un titre et une description, et suggère un prix avec une fourchette. Tout le
reste de ce document décrit comment chaque brique technique a été construite, vérifiée et mesurée.

Un mot de vocabulaire utile pour la suite : « MLOps » désigne l'ensemble des pratiques qui permettent
de faire vivre un modèle d'intelligence artificielle en production de façon fiable (le suivre,
le versionner, le ré-entraîner automatiquement, le surveiller et le remplacer sans interruption).
C'est l'équivalent, pour les modèles, de ce que les bonnes pratiques de développement logiciel sont
pour le code ordinaire.

---

## 1. Couverture des quatre phases du cahier des charges

Le cahier des charges découpait le travail en quatre phases successives. Pour chaque étape attendue,
le tableau indique si elle est livrée et où la trouver dans le dépôt. Les chemins de fichiers sont
donnés tels qu'ils existent réellement, pour qu'un examinateur puisse les ouvrir directement.

### Phase 1 : fondations et mise en conteneur

Cette première phase pose les bases : cadrer le besoin, préparer un environnement de travail
reproductible, nettoyer les données, entraîner de premiers modèles, et exposer une première interface
de programmation (une « API », c'est-à-dire une porte d'entrée par laquelle un autre programme envoie
une requête et reçoit une réponse).

| Étape attendue | Statut | Où c'est livré dans le dépôt |
|---|---|---|
| Cadrage du projet et indicateurs clés de succès | Livré | `documentation/PROJECT.md` (besoin, hypothèses, objectifs chiffrés) |
| Environnement de développement reproductible | Livré | `pyproject.toml` (liste des dépendances), environnement Python `.venv`, `Makefile` (commandes prêtes à l'emploi), mêmes versions rejouées automatiquement à chaque intégration |
| Collecte puis traitement des données | Livré | dossier `src/data/` (audit, puis nettoyage, puis découpage en jeux d'apprentissage et de test) |
| Entraînement et évaluation des modèles | Livré | dossier `src/classifiers/` (apprentissage) et `src/classifiers/metrics.py` (mesure de la qualité) |
| Interface de programmation pour les prédictions | Livré | `src/api/main.py`, construite avec la bibliothèque FastAPI (un outil qui transforme du code Python en service web) |

### Phase 2 : micro-services, suivi des expériences et versionnement

Cette phase fait passer le projet d'un script unique à un système composé de plusieurs petits
services indépendants qui coopèrent. Elle introduit aussi la traçabilité : garder une trace de chaque
expérience d'entraînement, et conserver une version datée des données comme des modèles.

| Étape attendue | Statut | Où c'est livré dans le dépôt |
|---|---|---|
| Suivi des expériences avec MLflow | Livré | dossier `src/mlops/`. MLflow est un outil qui enregistre, pour chaque entraînement, les réglages utilisés, les résultats obtenus et les fichiers produits, afin de pouvoir tout comparer et tout retrouver |
| Versionnement des données et des modèles | Livré | DVC (décrit dans le fichier `dvc.yaml`) pour les données ; le registre de modèles de MLflow pour les modèles. DVC est un outil qui, comme un gestionnaire de versions pour fichiers volumineux, garde l'historique exact des jeux de données |
| Découpage en micro-services et orchestration | Livré | `docker-compose.yml`, qui décrit 14 services tournant ensemble (base de données, stockage, serveur de suivi, interface, etc.) |

### Phase 3 : orchestration et déploiement

Cette phase automatise les enchaînements et prépare la mise en production : un pipeline qui
ré-entraîne les modèles tout seul de bout en bout, une chaîne d'intégration continue qui vérifie le
code à chaque modification, une interface de programmation sécurisée, et la capacité de monter en
charge sur plusieurs machines.

| Étape attendue | Statut | Où c'est livré dans le dépôt |
|---|---|---|
| Pipeline de ré-entraînement complet avec Airflow | Livré | dossier `infra/airflow/dags/`, une chaîne de cinq étapes enchaînées. Airflow est un chef d'orchestre qui lance des tâches dans le bon ordre et au bon moment |
| Chaîne d'intégration continue et tests automatisés | Livré | `.github/workflows/ci.yml` : vérification du style de code, exécution de 352 tests automatisés, analyse des failles de sécurité connues, et fabrication des images logicielles |
| Interface de programmation optimisée et sécurisée | Livré | jeton d'authentification JWT, protection contre la traversée de chemin, adresses imprévisibles pour les photos, traitement non bloquant des requêtes (détaillés en section 5) |
| Capacité de montée en charge avec Docker et Kubernetes | Livré | dossier `infra/k8s/` (déclarations de déploiements, de services à état, de point d'entrée réseau, et mise à l'échelle automatique des copies de l'API : de 2 à 5 copies dès que l'usage processeur dépasse 70 %). Kubernetes est un système qui répartit et gère automatiquement des conteneurs sur un ensemble de machines |

### Phase 4 : surveillance et maintenance

La dernière phase garde le système en bonne santé une fois en service : surveiller les performances,
détecter quand les données d'entrée changent de nature, mettre à jour les modèles automatiquement, et
documenter le tout pour la présentation.

| Étape attendue | Statut | Où c'est livré dans le dépôt |
|---|---|---|
| Surveillance des performances (Prometheus et Grafana) | Livré | quatre indicateurs fondamentaux (latence, trafic, erreurs, saturation) et trois tableaux de bord. Prometheus collecte les mesures, Grafana les affiche sous forme de graphiques |
| Détection de dérive avec Evidently | Livré | `src/monitoring/drift_detection.py` et une chaîne Airflow dédiée. La « dérive » survient quand les nouvelles données diffèrent assez des données d'apprentissage pour menacer la fiabilité du modèle ; Evidently est l'outil qui mesure cet écart |
| Pipelines de mise à jour automatisés | Livré | la boucle de ré-entraînement Airflow, le mécanisme de remplacement de modèle (décrit en section 3), et la publication d'images logicielles datées |
| Documentation technique et présentation | Livré | ce dossier `documentation/` (17 rapports numérotés) et une démonstration via une interface web écrite en React (une technologie de construction d'interfaces utilisateur) |

Deux choix à assumer ouvertement en présentation :

1. Les scripts de données et d'entraînement sont numérotés (par exemple `01_load_full.py`,
   `01_tfidf_linsvc.py`) plutôt que nommés d'après leur action (`collect.py`, `train.py`). La
   convention retenue est : « le pipeline se lit dans l'ordre des numéros de fichiers ». Le résultat
   est fonctionnellement identique, seul le nommage diffère.
2. La démonstration s'appuie sur une interface web React (une vraie interface produit) plutôt que sur
   Streamlit (l'outil de démonstration cité en exemple dans le cahier des charges). Ce choix se
   rapproche davantage d'un produit réel.

---

## 2. Couverture détaillée des exigences MLOps

Le tableau ci-dessous reprend chaque exigence de fiabilité en production demandée, explique comment
elle est satisfaite, et indique l'outil concerné. Chaque outil est expliqué en une phrase à sa
première apparition.

| Exigence | Comment elle est couverte | Outil et emplacement |
|---|---|---|
| Suivi des expériences | Enregistrement systématique des réglages, des résultats et des fichiers produits à chaque entraînement | MLflow, dossier `src/mlops/` |
| Versionnement des modèles | Registre de modèles avec une étiquette `@Production` désignant la version actuellement en service | Registre MLflow |
| Versionnement des données | Pipeline reproductible décrivant comment les données ont été préparées | DVC, fichier `dvc.yaml` |
| Orchestration des tâches | Chaîne automatique de ré-entraînement déclenchée selon un calendrier | Airflow |
| Mise à disposition des modèles et mesures associées | Service dédié qui répond aux requêtes et expose ses propres mesures | BentoML (un outil qui empaquette un modèle en service web), couplé à Prometheus |
| Boucle automatique fermée | Enchaînement complet : détection de dérive, puis ré-entraînement, puis évaluation, puis remplacement du modèle, puis redéploiement | Airflow et Evidently |
| Mise en conteneur | Construction d'images logicielles en plusieurs étapes pour rester légères | Docker |
| Orchestration locale et de production | Une configuration de base et une surcouche dédiée à la production | Docker Compose |
| Point d'entrée réseau unique | Routage des requêtes vers le bon service et limitation du débit | Traefik (un répartiteur de trafic placé devant les services) |
| Stockage des gros fichiers | Conservation des fichiers produits par MLflow et des données suivies par DVC | MinIO (un stockage de fichiers compatible avec le standard d'Amazon S3) |
| Orchestration de conteneurs | Déploiement multi-machine avec mise à l'échelle automatique | Kubernetes, testé sur un cluster local créé avec l'outil kind |
| Journaux structurés | Messages au format JSON, chacun marqué d'un identifiant de requête pour suivre une demande de bout en bout | bibliothèque structlog |
| Mesures et tableaux de bord | Quatre indicateurs fondamentaux visualisés en continu | Prometheus et Grafana |
| Détection de dérive | Comparaison statistique entre les données récentes et les données de référence | Evidently |
| Intégration et livraison continues | Vérifications automatiques à chaque modification, puis publication d'images datées selon le standard de numérotation sémantique | GitHub Actions, registre d'images GHCR |
| Tests et contrôle de sécurité | 352 tests automatisés et une analyse des failles connues des dépendances | pytest et l'outil pip-audit |

---

## 3. Les modèles surveillés en production

Le système ne repose pas sur un seul modèle, mais sur un ensemble de modèles complémentaires. Le
tableau récapitule, pour chacun, ce qu'on mesure pour vérifier qu'il fonctionne bien, l'outil de
surveillance utilisé, et ce qu'on fait si sa qualité se dégrade.

Le mécanisme de remplacement repose sur un principe simple appelé « champion contre challenger ». Le
champion est le modèle qui travaille actuellement en production. Le challenger est un nouveau candidat
fraîchement entraîné. On ne bascule la production sur le challenger que s'il fait clairement mieux que
le champion, et ce basculement se fait juste en déplaçant l'étiquette `@Production`, sans copier de
fichiers, ce qui rend le retour en arrière immédiat.

Quelques sigles utiles : « F1 » est un score entre 0 et 1 qui mesure la justesse d'une
classification (plus il est proche de 1, mieux c'est) ; « MAPE » est l'erreur moyenne en pourcentage
d'une prédiction de prix ; « ECE » mesure si la confiance affichée par un modèle est honnête (une
confiance de 90 % devrait correspondre à 90 % de bonnes réponses).

| Modèle | Ce qu'on mesure | Surveillance | Action si la qualité baisse |
|---|---|---|---|
| Classifieur par plus proches voisins (recherche FAISS) | Score F1, temps de réponse | MLflow et Prometheus | ré-entraînement via Airflow |
| Classifieur à vecteurs de support et perceptron multicouche | Score F1, honnêteté de la confiance (ECE) | MLflow | ré-entraînement via Airflow |
| Classifieur TF-IDF (celui réellement mis en service) | Score F1, honnêteté de la confiance (ECE) | MLflow | ré-entraînement |
| Modèle de fusion combinant plusieurs classifieurs | Score F1 de la combinaison | MLflow | réajustement des poids de combinaison |
| Recherche par similarité FAISS pour retrouver le produit | Taux de bonnes réponses, temps de réponse au 95e centile | Prometheus et Grafana | reconstruction de l'index de recherche |
| Estimateur de prix | Erreur moyenne en pourcentage par tranche, couverture | Prometheus et Grafana | recalibrage de la dépréciation |
| Encodeur de texte Arctic | Dérive des représentations produites | Evidently | fixer une nouvelle référence |
| Validateur visuel (modèle vision-langage) | Taux de réponses correctement interprétables, hallucinations | journaux et MLflow | changer de fournisseur |
| Rédacteur de texte (grand modèle de langage) | Qualité de la rédaction | journaux, MLflow et retours d'usage | changer de fournisseur |

Précisions sur les modèles cités, pour le lecteur technique :

- FAISS est une bibliothèque qui retrouve très vite les éléments les plus proches d'un point parmi des
  millions, en comparant des vecteurs de nombres. Le classifieur par plus proches voisins atteint un
  score F1 pondéré de 0,9537 et répond quasi instantanément, car il réutilise l'index déjà construit.
- L'index de recherche servi en production est de type HNSW (un graphe de navigation rapide entre
  voisins) ; il pèse environ 13,2 gigaoctets et répond en quelques dixièmes de milliseconde.
- Le classifieur réellement mis en service est le modèle TF-IDF associé à une machine à vecteurs de
  support (score F1 pondéré de 0,9503). Il a été préféré au plus proches voisins, légèrement meilleur,
  parce qu'il constitue un vrai modèle versionnable et promouvable, mieux adapté à la chaîne MLOps.
- L'encodeur de texte est le modèle `Snowflake/snowflake-arctic-embed-l-v2.0`, multilingue, utilisé
  gelé (sans ré-entraînement). Il transforme chaque produit en un vecteur de 1024 nombres.

---

## 4. Ce qui est volontairement hors du périmètre

Certaines fonctionnalités ont été écartées en connaissance de cause, et non par oubli. Les écarter est
un choix d'ingénierie assumé, justifié par la durée du projet (trois mois) ou par son cadre scolaire.

- Pas d'estimation de prix par apprentissage automatique opaque. Le prix est calculé par une méthode
  algorithmique transparente (on regarde les prix des produits les plus ressemblants, puis on applique
  une dépréciation selon la catégorie et l'état), pour que le vendeur comprenne d'où vient le chiffre.
  L'erreur moyenne mesurée est d'environ 62 %, ce qui est assumé : un prix transparent assorti d'une
  fourchette vaut mieux qu'un nombre faussement précis sorti d'une boîte noire.
- Pas de ré-entraînement de l'encodeur d'images. Le modèle de vision SigLIP est utilisé gelé, comme
  simple extracteur de caractéristiques.
- Pas d'application mobile native. Une interface web qui s'adapte à la taille de l'écran couvre le
  besoin de démonstration.
- Pas d'intégration à l'interface de programmation réelle de Rakuten. Le projet utilise le jeu de
  données public Amazon Reviews 2023 comme catalogue de remplacement pour identifier les produits.
- Pas d'interface multilingue. L'interface est en français uniquement, même si l'encodeur de texte est
  multilingue pour absorber le fait que les avis de la source sont en anglais.
- Pas d'authentification d'entreprise. Le jeton JWT est en mode démonstration, signé avec l'algorithme
  HS256 et un secret partagé.
- Pas d'indexation visuelle directe du catalogue (recherche image vers image avec SigLIP). Cette
  fonctionnalité est différée : elle ne sera lancée que si une mesure réelle prouve son intérêt.
- Pas d'affinage fin du modèle vision-langage. Cette option n'a pas été déclenchée, faute de preuve
  d'un gain mesurable, par souci d'éviter la sur-ingénierie.

---

## 5. Détail de la sécurité de l'interface de programmation

La porte d'entrée du système est protégée par plusieurs mécanismes complémentaires :

- Authentification par jeton JWT. Un JWT est un jeton numérique signé qu'un utilisateur présente à
  chaque requête pour prouver son identité. Ici, il est signé avec l'algorithme HS256, le secret de
  signature étant lu dans la variable d'environnement `JWT_SECRET`, et sa durée de validité est
  réglable. Le code se trouve dans le dossier `src/auth/`.
- Protection contre la traversée de chemin, une attaque où un nom de fichier malicieux tente de
  remonter l'arborescence pour lire des fichiers interdits.
- Adresses imprévisibles pour servir les photos : chaque image est accessible via une adresse
  contenant une suite de caractères impossible à deviner, de sorte qu'on ne peut accéder qu'aux
  fichiers dont on possède déjà le lien.
- Traitement non bloquant des requêtes, pour que le service reste réactif sous charge.

---

## Verdict pour la présentation

Les quatre phases du cahier des charges sont couvertes et démontrables. Le projet livre un pipeline
complet, de la photo jusqu'à l'annonce, avec une chaîne MLOps fermée : suivi des expériences,
versionnement des données et des modèles, ré-entraînement automatique, surveillance des performances,
détection de dérive et remplacement de modèle sans interruption. Les seuls écarts par rapport au
périmètre initial sont des choix assumés et justifiés, jamais des oublis.

Phrase de défense : « Chaque exigence des quatre phases est livrée dans le dépôt et vérifiable
fichier par fichier ; les rares écarts sont des décisions d'ingénierie documentées, pas des manques. »
