# Couverture du projet face aux exigences attendues

Cette page répond d'un coup d'oeil à une seule question : « le projet couvre-t-il bien tout ce qui
était demandé ? ». Elle confronte ce que le cahier des charges attendait, organisé en quatre grandes
phases, avec ce qui est réellement présent et fonctionnel dans le dépôt de code.

Pour comprendre le projet en une phrase : il s'agit d'un assistant qui aide un vendeur de produits
d'occasion (électronique) à créer une annonce de qualité à partir d'une simple photo. À partir de
l'image, le système identifie le produit, propose une catégorie précise, pré-remplit les
caractéristiques, rédige un titre et une description, et suggère un prix avec une fourchette. Tout le
reste de ce document décrit comment chaque brique technique a été construite, vérifiée et mesurée.

Une mise à jour importante de l'identification (cycle 36) mérite d'être posée dès l'introduction,
car elle conditionne la qualité de toute la fiche. Le principe retenu sépare deux rôles : la
recherche par similarité (le « retriever ») apporte la *connaissance* (elle ramène les quinze fiches
catalogue les plus proches de la photo), tandis qu'un modèle de langage apporte le *jugement* (il
choisit, parmi ces quinze candidats réels, lequel correspond vraiment à l'objet photographié). Ce
découpage corrige un défaut concret : auparavant, le tout premier résultat de la recherche pouvait
être un accessoire (par exemple une coque d'iPhone affichée à la place de l'iPhone lui-même), et la
fiche, le prix et la validation se construisaient alors sur le mauvais produit. Désormais, le
candidat jugé correct est remonté en tête, et toute la suite porte sur le bon objet. Ce mécanisme,
ses garde-fous contre l'invention de données, et sa mesure chiffrée sont détaillés en section 6.

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
| Estimateur de prix en cascade (niveaux L1 → L1.5 → L2 → L3 → L4) | Niveau de cascade réellement utilisé, présence d'une ancre d'IA, prix suggéré | journaux métier, Prometheus et Grafana | recalibrage de la dépréciation |
| Encodeur de texte Arctic | Dérive des représentations produites | Evidently | fixer une nouvelle référence |
| Modèle vision-langage (triple rôle : extraction depuis la photo, validateur visuel, et passe d'identification raisonnée) | Taux de réponses correctement interprétables, hallucinations, taux de produits hors catalogue détectés | journaux métier et MLflow | changer de fournisseur |
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
- Le modèle vision-langage appelé via l'API externe (par défaut `qwen/qwen3.5-flash-02-23`, réglable
  par la variable d'environnement `PHOTO_VLM_IDENTIFY_MODEL`) joue désormais trois rôles distincts :
  extraire les attributs visibles sur la photo, valider visuellement que la photo correspond au
  meilleur candidat, et conduire la « passe d'identification raisonnée » introduite au cycle 36. Tous
  ses appels sont rendus reproductibles (température à zéro, graine fixée, raisonnement interne
  désactivé), ce qui permet de rejouer une décision à l'identique. Le code dédié à la passe raisonnée
  se trouve dans `src/vlm/reasoned_identification.py`.

---

## 4. Ce qui est volontairement hors du périmètre

Certaines fonctionnalités ont été écartées en connaissance de cause, et non par oubli. Les écarter est
un choix d'ingénierie assumé, justifié par la durée du projet (trois mois) ou par son cadre scolaire.

- Pas d'estimation de prix par apprentissage automatique opaque. Le prix est calculé par une cascade
  algorithmique transparente : on part d'un prix neuf de référence, puis on applique une dépréciation
  selon la catégorie et l'état, pour que le vendeur comprenne d'où vient le chiffre. Cette ligne reste
  vraie après le cycle 36 : un nouveau niveau intermédiaire (« L1.5 ») utilise désormais comme point
  de départ un prix neuf *estimé par l'IA* quand le prix catalogue réel manque, mais seule cette ancre
  est une estimation. La décote (dépréciation et état) reste à 100 % déterministe et explicable, et le
  prix obtenu est étiqueté honnêtement « prix neuf estimé par IA » dans l'interface. Le détail de la
  cascade et de ses garde-fous est donné en section 6. On assume ce parti pris de transparence : un
  prix expliqué et assorti d'une fourchette vaut mieux qu'un nombre faussement précis sorti d'une
  boîte noire.
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

Le cycle 36 a ajouté un durcissement supplémentaire, issu d'une revue de sécurité adversariale menée
sur cinq dimensions (cette revue a relevé sept points jugés importants et huit points jugés moyens,
tous corrigés) :

- Bornes strictes sur les valeurs reçues. Les champs de prix de l'interface n'acceptent plus que des
  nombres strictement positifs, plafonnés à un million, et refusent les valeurs aberrantes comme
  l'infini ou « pas un nombre ». Les indices textuels et les listes envoyées sont également bornés en
  taille, ce qui ferme une porte aux attaques par déni de service (saturer le service avec une entrée
  démesurée).
- Protection contre l'injection de consignes (« prompt injection »). Le texte libre saisi par le
  vendeur est inséré dans la requête envoyée au modèle de langage en étant explicitement délimité et
  marqué comme une *donnée non fiable, et non une instruction*. Le modèle est ainsi prévenu de ne pas
  exécuter une consigne qui s'y cacherait (par exemple « ignore les règles précédentes »).
- Maîtrise de la latence. Quand la passe d'identification raisonnée a déjà tranché avec une confiance
  suffisante, on n'ajoute pas le troisième appel au modèle de langage (le validateur visuel), puisque
  la passe raisonnée a déjà rendu un jugement de correspondance. Cela économise un appel réseau
  séquentiel sans perte d'information utile.

---

## 6. Les fonctionnalités du cycle 36 : identification raisonnée et fiche prête pour la production

Cette section décrit les évolutions du cycle 36, qui visent toutes le même objectif : rendre la fiche
fiable et défendable, même quand le produit photographié est mal capté par la recherche ou absent du
catalogue de référence. Le fil conducteur est une règle simple, héritée de la doctrine du projet : on
ne génère jamais une donnée avant de l'avoir ancrée sur une preuve réelle.

### 6.1 L'identification raisonnée : le retriever connaît, le modèle juge

Le module `src/vlm/reasoned_identification.py` introduit une seule requête supplémentaire au modèle de
langage, et cette requête est conçue pour rester bon marché. On envoie une ou deux photos du vendeur,
les quinze fiches candidates *résumées en texte* (et non leurs quinze images catalogue, ce qui
économise beaucoup de jetons), les attributs déjà observés sur la photo, et le texte du vendeur. Le
modèle renvoie un jugement structuré : la famille de produit reconnue, sa confiance, le candidat
choisi, un drapeau « absent du catalogue », un prix neuf de référence estimé avec sa confiance et les
fiches qui ont servi d'appui, une éventuelle question discriminante à poser, et des caractéristiques
chacune accompagnée de sa source.

Le point essentiel est l'ensemble des garde-fous contre l'invention de données :

- Un candidat choisi qui ne ferait pas partie des quinze proposés est rejeté : on retombe alors sur le
  premier résultat de la recherche, et on remet la confiance de famille à zéro (le modèle n'a pas
  réellement endossé ce candidat, donc la suite ne doit pas le traiter comme un fait certain). Le
  modèle ne peut donc jamais faire entrer un produit étranger à la liste réelle.
- Une caractéristique dont la source serait invalide est jetée : aucune affirmation n'est conservée si
  elle ne pointe pas vers une fiche réelle, vers une observation directe sur la photo, ou vers une
  analogie explicitement déclarée comme une estimation.
- L'ancre de prix neuf est conservée même sans preuve associée, mais elle est alors présentée comme
  une *estimation étiquetée*, jamais comme un fait catalogue. C'est volontaire : une estimation
  honnête vaut mieux que de retomber sur des médianes de prix polluées.
- L'ensemble est « au mieux » et non bloquant : en cas d'absence de clé d'accès, de modèle
  indisponible, de réponse illisible ou d'erreur, la fonction renvoie « rien » et le pipeline garde
  son classement par recherche et sa cascade de prix habituelle. Il n'y a jamais de plantage ni de
  fiche vide.

Quand un candidat est jugé correct, il est remonté en tête de liste, de sorte que la fiche, le prix et
la validation portent sur le bon produit. Cette réorganisation est ce qui empêche désormais une coque
d'apparaître à la place du téléphone.

### 6.2 Le texte du vendeur fait autorité

La fonction `_seller_text_best_match` (dans `src/api/main.py`) ajoute une règle déterministe : si le
texte du vendeur nomme un produit présent dans les candidats (au moins deux mots discriminants, au
moins la moitié des mots couverts, en gardant les numéros de modèle même à un seul chiffre pour
distinguer un « Momentum 3 » d'un « Momentum 2.0 »), ce candidat est retenu sans passer par le modèle
de langage. Cela rend l'identification robuste face au modèle rapide qui ignore parfois la consigne du
texte vendeur. En cas d'égalité entre plusieurs candidats, on choisit celui dont le prix est le plus
représentatif (le plus proche de la médiane), afin de ne pas bâtir la fiche sur une donnée corrompue
(par exemple un même produit listé par erreur à un prix absurde). Sur un texte vide, cette règle ne
fait rien du tout, ce qui garantit zéro régression.

### 6.3 La cascade de prix à cinq niveaux

Le code `src/pricing/01_algorithmique.py` organise le prix en cinq niveaux, du plus fiable au moins
fiable :

- **L1** : le prix catalogue réel du produit identifié, sur lequel on applique la décote d'état et la
  dépréciation par âge.
- **L1.5** (nouveau) : l'ancre de prix neuf estimée par l'IA lors de la passe raisonnée, à laquelle on
  applique la *même* décote déterministe. Ce niveau est placé avant les médianes parce que celles-ci
  sont polluées par les accessoires et les lots (elles donnaient par exemple six euros pour une montre
  qui en vaut cent cinquante).
- **L2 et L3** : les médianes des voisins puis de la catégorie, rétrogradées pour cette même raison.
- **L4** : repli en saisie manuelle ; l'interface n'affiche plus « 0,00 € » mais « Prix à fixer ».

Trois garde-fous complètent la cascade : un plancher anti sous-évaluation qui relève une médiane
tombée bien en dessous du prix neuf attendu décoté ; un contrôle de cohérence qui écarte un prix
catalogue ridiculement bas par rapport à l'ancre IA (signe que le premier résultat est en réalité un
accessoire mal apparié, ce qui évitait un « iPhone à 15 € ») ; et un filtre contre les prix catalogue
aberrants, très au-dessus de la médiane des voisins, qui trahissent une donnée corrompue. L'état
« pour pièces / hors service » a été ajouté, avec un multiplicateur de 0,15 ; les multiplicateurs sont
1,00 pour neuf, 0,75 pour très bon état, 0,55 pour bon état, 0,35 pour correct et 0,15 pour pièces. La
conversion des dollars vers les euros se fait à un taux fixe documenté (environ 0,92, réglable par la
variable `PRICE_USD_EUR_RATE`).

### 6.4 La fiche exhaustive et la complétude par catégorie fine

L'assemblage de la fiche (`src/serving/listing_fill.py` et l'endpoint `/identify` de
`src/api/main.py`) génère toutes les données structurées utiles : les caractéristiques attendues par
le schéma de la catégorie, mais aussi des attributs plus riches hors schéma (format, fonctionnalités,
certification, tension, puissance, connectivité…), valeurs longues tronquées pour éviter le bruit.
Chaque champ porte l'une des cinq provenances : observé sur la photo, issu du catalogue (match
fiable), typique et donc à vérifier, déduit de la catégorie, ou saisi par le vendeur. Les
caractéristiques jugées par l'IA sont fusionnées en respectant leur source : ce qui est vu sur la
photo devient « observé », ce qui pointe vers une fiche réelle devient « catalogue » (seulement si la
passe concerne bien ce produit), et ce qui n'est qu'une analogie n'est jamais affirmé comme un fait.
Le texte brut lu par reconnaissance optique (souvent un filigrane) est exclu.

Le « type de produit » affiché correspond désormais à la catégorie du produit réellement identifié, et
non plus au vote brouillé par un accessoire. La complétude de la fiche est calculée par catégorie
*fine* : on ne garde du schéma que les caractéristiques réellement présentes chez au moins un candidat
de même catégorie fine, de sorte qu'une enceinte n'est plus pénalisée pour l'absence d'une « capacité
de stockage ». L'état, qui est un choix du vendeur toujours disponible, est exclu du dénominateur pour
ne pas fausser la mesure.

### 6.5 Le parcours vendeur refondu et les signaux honnêtes

Côté interface (`frontend/src`), le choix manuel du type d'objet a été supprimé : le type est dérivé
de la catégorie identifiée (`condition.ts`, fonction `kindFromCategory`), avec une reconnaissance par
mot entier et une exclusion des accessoires, pour qu'un casque (« headphones », qui contient le mot
« phone ») ou un chargeur ne soit plus rangé parmi les téléphones. La liste de vérification de l'état
spécifique au produit (batterie et écran pour un téléphone, clavier pour un ordinateur, manettes pour
une console…) s'affiche au bon moment, après l'identification. Un état « pour pièces / hors service »
et un champ optionnel « année d'achat » ont été ajoutés ; sans année saisie, l'âge est supposé être de
deux ans, ce qui est signalé à l'écran.

Le parcours s'auto-confirme : si l'IA est sûre, la fiche s'affiche directement ; sinon, les candidats
sont proposés, et un bouton « Ce n'est pas le bon produit ? Voir les autres résultats » reste
disponible sur la fiche. Deux signaux d'honnêteté complètent l'affichage. Le pourcentage de confiance
montré correspond à la part du vote des plus proches voisins sur la catégorie fine, et il n'est
affiché que s'il est net (au moins 60 %). Un pourcentage bas reflète une fragmentation du vote (le
modèle exact est ambigu), et non un doute sur la catégorie ; dans ce cas, plutôt qu'un chiffre
trompeur, on affiche un bandeau actionnable « Modèle à confirmer » qui reprend, si elle existe, la
question discriminante de l'IA. Un autre bandeau signale les produits estimés et absents du catalogue,
et l'étiquette « prix neuf estimé par IA » accompagne explicitement le niveau L1.5.

### 6.6 L'observabilité métier

Au-delà des mesures techniques exposées à Prometheus, le cycle 36 ajoute des journaux structurés
(`structlog`) inspectables par requête, dans `src/api/main.py`. Deux événements résument ce que fait
le pipeline : `identify_done` (statut, nombre de candidats, score du premier, catégorie fine et sa
confiance, présence et résultat de la passe raisonnée, réorganisation effectuée, produit hors
catalogue, ancre de prix, question posée, confiance de famille, complétude, et durées des appels
d'extraction et de raisonnement) et `price_done` (niveau de cascade, méthode, prix suggéré, présence
d'une ancre, catégorie et état). On peut ainsi lire concrètement le taux de produits hors catalogue,
l'usage du niveau L1.5, ou l'endroit où part la latence.

### 6.7 La mesure chiffrée de la qualité de fiche

Pour remplacer les anecdotes par un chiffre défendable, le script `scripts/mesure_qualite_fiche.py`
applique un protocole reproductible sur le panel réel `data/photos_eval` (94 produits, dont le nom de
dossier sert de vérité-terrain), à partir de la photo seule, sans précisions textuelles. Les résultats
sont écrits dans `reports/09_fiche_quality/mesure_fiche.json` et son équivalent lisible. Les valeurs
mesurées sont les suivantes :

- Identification correcte (au moins la moitié des mots-clés du nom retrouvés dans la famille proposée
  par l'IA et le titre du premier candidat) : 90,3 %, avec un rappel moyen de 78 % des mots-clés.
- Complétude de la fiche : 0,84 en moyenne, 0,83 en médiane.
- Passe raisonnée déclenchée : 100 % des cas. Produit jugé absent du catalogue : 28 %. Question
  discriminante posée : environ 11 %. Répartition des niveaux de prix : 42 fiches en L1 et 51 en L1.5.
- Neuf produits n'ont pas été identifiés, et tous les cas sont expliqués : une perception imparfaite du
  modèle exact (une carte graphique RTX 4080 Super prise pour une 3080, une Xbox Series S, un casque
  Sennheiser Momentum confondu), un produit réellement absent du catalogue (un disque SSD, une station
  d'accueil), ou un nom de dossier ambigu (artefact de mesure).

### 6.8 Les limites assumées, sans survente

Trois limites sont documentées telles quelles. D'abord, avec la photo seule, la perception du modèle
exact reste difficile pour des produits sans marquage visible sur les images envoyées (par exemple un
Sennheiser Momentum 3 dont le logo se trouve sur l'étui) : le modèle peut alors choisir un sosie avec
assurance. Ce risque est atténué de trois façons : le texte du vendeur qui fait autorité (la
métadonnée fixe le produit quand il est bien au catalogue), le bandeau « Modèle à confirmer », et le
bouton « Ce n'est pas le bon ? ». Ensuite, le modèle rapide utilisé par défaut sous-déclenche la
détection « absent du catalogue » (il colle parfois à un sosie d'une autre génération, par exemple un
iPhone 14 pris pour un 13) ; un modèle jugé plus fort ferait mieux, mais cette option n'est pas câblée
par défaut. Enfin, le garde-fou anti sous-évaluation est surtout défensif : c'est bien le niveau L1.5,
l'ancre estimée par l'IA, qui fait le vrai travail de remise à niveau du prix.

### 6.9 Statut de livraison

Ces fonctionnalités du cycle 36 ont été implémentées et vérifiées en direct sur de vraies photos.
Elles vivent sur une branche de travail (`feat/cycle34-listing-quality-bench`) et ne sont pas encore
fusionnées sur la branche principale ; cette précision est utile pour qu'un examinateur sache où
trouver le code.

---

## Verdict pour la présentation

Les quatre phases du cahier des charges sont couvertes et démontrables. Le projet livre un pipeline
complet, de la photo jusqu'à l'annonce, avec une chaîne MLOps fermée : suivi des expériences,
versionnement des données et des modèles, ré-entraînement automatique, surveillance des performances,
détection de dérive et remplacement de modèle sans interruption. Les seuls écarts par rapport au
périmètre initial sont des choix assumés et justifiés, jamais des oublis.

Phrase de défense : « Chaque exigence des quatre phases est livrée dans le dépôt et vérifiable
fichier par fichier ; les rares écarts sont des décisions d'ingénierie documentées, pas des manques. »
