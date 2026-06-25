# 14. API et orchestration : la plomberie qui relie toutes les briques

> Le chef d'orchestre du projet. C'est la couche logicielle qui reçoit les demandes
> venant de l'interface utilisateur, garde les modèles prêts en mémoire, les appelle
> dans le bon ordre (reconnaissance de la photo, recherche du produit, questions de
> précision, calcul du prix, rédaction de l'annonce), puis renvoie une réponse propre.
> Sans cette couche, les briques d'intelligence artificielle ne sont que des fichiers
> isolés sur le disque, incapables de travailler ensemble.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre en partant de zéro

Une API (sigle anglais de "Application Programming Interface", littéralement interface
de programmation) est une prise standardisée par laquelle deux programmes se parlent.
Dans notre cas, l'interface web du vendeur (le programme avec lequel l'humain
interagit, son navigateur) envoie un message au programme qui héberge nos modèles. Ce
message voyage par le protocole HTTP, le même langage que celui utilisé pour charger
n'importe quel site web. Concrètement, l'interface dit "voici une photo, identifie le
produit", le programme exécute le travail, puis renvoie une réponse au format JSON (un
format texte structuré, lisible à la fois par une machine et par un humain, fait de
paires "nom : valeur").

Le rôle de l'orchestrateur tient en une idée simple : aucune brique ne fait tout. La
recherche par similarité trouve le produit le plus ressemblant dans le catalogue. Le
modèle de vision lit la photo pour en deviner le titre. Le système de questions (que
nous appelons l'Akinator, par analogie avec le jeu où l'on devine un personnage en
posant des questions) lève les ambiguïtés. Le calcul de prix estime un montant. Le
modèle de langage rédige l'annonce. Quelqu'un doit appeler ces briques dans le bon
ordre, faire passer le résultat de l'une vers l'entrée de la suivante, et gérer les
pannes. Ce travail de coordination est réparti dans deux fichiers : `src/api/main.py`
(450 lignes, qui définit les points d'entrée de l'API) et `src/api/pipeline.py`
(515 lignes, qui contient la logique d'enchaînement des modèles).

### Pour le lecteur expert

- Le serveur est bâti sur FastAPI, un cadriciel Python asynchrone. La validation des
  données qui entrent et sortent est confiée à Pydantic version 2 : on décrit chaque
  message attendu par un schéma typé, et toute requête mal formée reçoit
  automatiquement une erreur HTTP 422 (le code standard signifiant "données reçues
  invalides"). Le serveur tourne derrière uvicorn, un serveur conforme à la norme ASGI
  (l'interface standard entre un serveur web Python et une application asynchrone).
- Le chargement se fait une seule fois au démarrage, grâce au mécanisme appelé
  "lifespan" dans FastAPI (le cycle de vie de l'application). Les artefacts lourds
  (l'index de recherche FAISS et les métadonnées des produits) sont chargés au
  démarrage du serveur, et non à chaque requête, ce qui éviterait de relire le disque
  des milliers de fois.
- L'asynchronisme est traité correctement. Les opérations de recherche FAISS,
  d'encodage par le modèle Arctic et d'appel au modèle de vision sont synchrones et
  lourdes (elles occupent le processeur sans rendre la main). On les exécute donc dans
  un fil d'exécution séparé via `asyncio.to_thread(...)`, afin de ne pas bloquer la
  boucle d'événements. Sans cette précaution, une seule requête lente gèlerait toutes
  les autres requêtes en cours.

---

## 2. État de l'art : comment fait-on habituellement ?

- Servir un modèle d'apprentissage automatique passe par une API (le plus souvent au
  style REST, parfois gRPC), avec trois bonnes pratiques : valider les données en
  entrée, charger le modèle une fois au démarrage, et prévoir une dégradation
  gracieuse. Cette dernière notion signifie que si un modèle est absent, le serveur
  renvoie une erreur claire et actionnable plutôt que de planter entièrement.
- L'observabilité, c'est-à-dire la capacité à comprendre ce qui se passe dans le
  système, commence dès l'API. On attribue à chaque requête un identifiant unique
  (pour suivre son parcours dans les journaux) et on expose des mesures de
  fonctionnement (latence, nombre de requêtes, requêtes en cours).
- La sécurité impose d'authentifier les points d'entrée métier et de ne laisser
  publics que le strict nécessaire, comme la connexion et les sondes de santé (les
  petites requêtes automatiques qui vérifient que le service est vivant).
- Le streaming, par exemple via la technique des "Server-Sent Events" (événements
  envoyés par le serveur, une connexion qui reste ouverte pour pousser des messages au
  fur et à mesure), permet d'afficher l'avancement étape par étape côté utilisateur,
  pour une expérience plus fluide.

---

## 3. Notre implémentation : précisément ce que nous avons fait

### Les points d'entrée de l'API (fichier `src/api/main.py`)

Le serveur expose neuf points d'entrée (en anglais "endpoints", les adresses
auxquelles on envoie une requête). La colonne "Authentification" indique si un jeton
de connexion est exigé.

| Point d'entrée | Authentification | Rôle |
|---|---|---|
| `POST /auth/login` | public | Connexion par mot de passe, renvoie un jeton de session de type Bearer (un jeton signé JWT, algorithme HS256). Pour la démonstration, seul le couple identifiant/mot de passe `demo/demo` est accepté. |
| `POST /upload` | jeton requis | Enregistre une photo envoyée par le vendeur, point de départ du parcours. |
| `GET /uploads/{id}` | public (URL secrète) | Sert une photo enregistrée, afin de l'afficher dans l'annonce. L'accès est protégé par une URL secrète et non devinable, fabriquée à partir d'un identifiant aléatoire (un "uuid4", c'est-à-dire un identifiant universel unique tiré au hasard). |
| `GET /health` | public | Sonde de santé : indique la version et quels services sont effectivement chargés. |
| `POST /identify` | jeton requis | Le cœur du système : à partir de photos et d'un texte optionnel, renvoie les meilleurs produits candidats, une éventuelle question de précision et une validation visuelle. |
| `POST /price` | jeton requis | Calcule un prix suggéré par une cascade de quatre niveaux (notés L1 à L4). |
| `POST /describe` | jeton requis | Rédige un titre et une description ancrés sur les vraies données du catalogue. |
| `GET /history` | jeton requis | Renvoie les dernières identifications enregistrées, pour la traçabilité. |
| `POST /identify/stream` | jeton requis | Variante du cœur qui renvoie les étapes du pipeline en temps réel (technique des événements envoyés par le serveur). |

À propos du jeton de session : la connexion renvoie un jeton signé que le client doit
ensuite joindre à chacune de ses requêtes métier. Un jeton JWT (sigle anglais de "JSON
Web Token") est une chaîne de caractères qui contient l'identité de l'utilisateur et
une signature cryptographique. L'algorithme HS256 est la méthode de signature : le
serveur peut vérifier que le jeton n'a pas été falsifié, sans avoir à stocker l'état de
chaque session.

### Le chargement au démarrage (le "lifespan")

Au démarrage du serveur, on crée et charge trois services. Le chargement se fait en
mode tolérant aux pannes : si l'un des services échoue à se charger (par exemple parce
qu'un fichier d'artefact est absent), l'application démarre quand même. Le point
d'entrée correspondant renverra alors une erreur HTTP 503 (le code signifiant "service
indisponible") accompagnée d'un message précis indiquant quoi vérifier, au lieu de
faire planter tout le serveur.

### L'orchestrateur (fichier `src/api/pipeline.py`) : trois services

#### Le service d'identification, le plus riche

Ce service transforme une demande du vendeur en une liste de produits candidats.

Ce qu'il charge en mémoire au démarrage (une seule fois, pour ne pas relire le disque à
chaque requête) :

- L'index FAISS de type HNSW. FAISS est une bibliothèque qui retrouve très vite les
  éléments les plus proches parmi des millions. HNSW (sigle anglais de "Hierarchical
  Navigable Small World") désigne le type d'index utilisé, une structure en graphe qui
  permet une recherche approchée très rapide. Son réglage `efSearch=64` indique combien
  de voisins explorer pendant chaque recherche : plus ce nombre est élevé, plus la
  recherche est précise mais lente. La valeur 64 est notre compromis, qui atteint déjà
  un taux de bonnes récupérations de 0,948 en environ 0,29 milliseconde par recherche.
- Les métadonnées des produits d'entraînement (titre, marque, boutique, catégorie,
  prix de chaque produit), afin de pouvoir afficher les candidats trouvés.
- Plusieurs tables de correspondance préchargées en mémoire vive, qui associent à
  chaque identifiant produit ses informations : la vignette (image principale), la
  liste de toutes les vues photo, la catégorie fine, le fil d'Ariane complet de la
  catégorie (du type "A > B > C", c'est-à-dire le chemin de rangement dans le
  catalogue), la marque réelle du fabricant, et les facettes (couleur, capacité, et
  autres caractéristiques). Garder ces tables en mémoire permet d'enrichir
  instantanément chaque candidat sans relire un fichier.

L'encodeur Arctic, lui, est chargé en mode paresseux ("lazy"), c'est-à-dire pas au
démarrage du serveur mais à la toute première requête d'identification. Arctic
(de son nom complet "Snowflake/snowflake-arctic-embed-l-v2.0") est le modèle qui
transforme un texte en vecteur de nombres représentant son sens. Ce modèle est lourd à
charger en mémoire ; si personne n'identifie de produit, autant ne pas l'avoir chargé,
ce qui accélère le démarrage du serveur.

La fonction `encode_query` transforme le texte de la requête en vecteur, avec trois
subtilités importantes :

- Le réglage de prompt `"query"`. Arctic encode légèrement différemment une requête de
  recherche et un document du catalogue. On lui précise explicitement qu'il s'agit ici
  d'une requête, faute de quoi les scores de ressemblance seraient faussés.
- La normalisation L2. C'est une mise à l'échelle qui ramène chaque vecteur à une
  longueur unitaire, pour que la comparaison entre deux textes porte uniquement sur la
  direction du vecteur (autrement dit sur le sens), et non sur sa longueur. Cette
  comparaison de direction s'appelle la similarité cosinus.
- Un garde-fou de dimension. On vérifie que le vecteur produit comporte bien
  1024 nombres, la taille attendue pour ce modèle. Un détail technique compte ici : en
  cas d'écart, on déclenche une vraie erreur (instruction `raise` en Python) et non une
  simple assertion (`assert`). La raison est que Python supprime toutes les assertions
  quand le programme tourne en mode optimisé (option `python -O`). Une assertion aurait
  donc disparu silencieusement en production, alors que le `raise`, lui, reste actif.

La fonction `_maybe_translate` traduit la requête avant de chercher. Le catalogue est
rédigé en anglais (données issues du marché américain), tandis que le vendeur écrit en
français. On traduit donc la requête du français vers l'anglais avant la recherche.
Nous avons mesuré qu'une requête en français obtient un score de ressemblance plus bas
d'environ 0,08 par rapport à la même requête en anglais ; traduire améliore donc la
pertinence. Et si la traduction échoue (clé d'accès au service de traduction absente,
ou service en panne), on continue avec la requête brute non traduite : le modèle Arctic
comprend plusieurs langues, il est juste un peu moins précis sans traduction. On ne
bloque jamais le vendeur pour une traduction ratée.

La fonction `identify` réalise l'enchaînement complet : traduire la requête, l'encoder
en vecteur, chercher les 30 produits les plus proches avec FAISS, construire la liste
des candidats enrichis, appliquer les garde-fous de confiance, puis poser une question
de précision si nécessaire. Les garde-fous donnent trois niveaux de confiance selon le
score du meilleur candidat (un score entre 0 et 1 mesurant la ressemblance) :

- un score supérieur ou égal à 0,60 donne le statut "identifié" ;
- un score compris entre 0,45 et 0,60 donne le statut "à confirmer" ;
- un score inférieur à 0,45 donne le statut "incertain".

Dans tous les cas, on affiche toujours les candidats : c'est l'humain qui tranche.
Enfin, si les deux premiers candidats sont trop proches (un écart de score inférieur à
0,05, ce qui correspond typiquement à deux variantes du même produit), on déclenche le
système de questions (l'Akinator) pour poser la question qui les distingue.

À noter sur les catégories : en plus du candidat de tête, le service prédit la
catégorie fine du produit par un vote pondéré de tous les candidats voisins. Chaque
voisin "vote" pour sa catégorie avec un poids égal à son score de ressemblance, et la
catégorie qui rassemble le plus de poids l'emporte. Cette méthode s'est révélée plus
robuste que de simplement reprendre la catégorie du seul meilleur candidat : elle
améliore de 2,4 points la justesse de la catégorie sur un jeu de 15 000 requêtes de
test. La confiance renvoyée correspond à la part du vote remportée par la catégorie
gagnante.

#### Le service de calcul de prix

Ce service charge le fichier de configuration du modèle de prix
(`m8_pricing_v1.joblib`, un fichier sérialisé contenant notamment les prix médians par
catégorie) puis délègue le calcul à une cascade de prix transparente à quatre niveaux.
Le principe de la cascade : on tente d'abord la méthode la plus fiable, et si elle
n'est pas applicable, on descend vers une méthode de repli. Les quatre niveaux sont,
du plus fiable au moins fiable : le prix catalogue du produit identifié (niveau L1), la
médiane des prix des voisins trouvés par la recherche (niveau L2), la médiane des prix
de la catégorie (niveau L3), et une valeur de repli (niveau L4). Chaque suggestion
indique le niveau utilisé et une fourchette de prix, pour rester transparente.

#### Le service de rédaction de l'annonce

Ce service charge les métadonnées des produits ainsi que les phrases d'ancrage,
c'est-à-dire la vraie description issue du catalogue. L'ancrage (en anglais
"grounding") consiste à forcer le modèle de langage à s'appuyer sur des faits réels du
catalogue plutôt que sur sa seule mémoire, afin d'éviter qu'il invente des
caractéristiques. Le rédacteur utilisé est un modèle distant accessible via le service
OpenRouter (un intermédiaire qui donne accès à plusieurs modèles de langage en ligne)
lorsqu'une clé d'accès est présente ; sinon, on bascule sur un rédacteur de
remplacement local appelé Mock, ce qui garantit que la démonstration ne plante jamais.

Une subtilité a été corrigée : les états d'un produit sont stockés sous forme de codes
techniques en minuscules (par exemple `bon_etat`). On convertit ces codes en libellés
français lisibles (par exemple "Bon état") avant de construire les instructions
envoyées au modèle. Sans cette conversion, le code technique fuyait parfois tel quel
dans le titre généré.

### Le déroulé d'une requête `/identify`, étape par étape

```
 POST /identify {image_ids, text_hint, already_observed}
 │ (jeton de session vérifié)
 ▼
 1. Récupérer les chemins des photos à partir de leurs identifiants
    [erreur 422 si aucune photo valide]
 ▼
 2. Le modèle de vision analyse les photos (dans un fil séparé)
    et en extrait un titre probable et des attributs
    [erreur 503 si la clé d'accès est absente ET qu'aucun texte n'est fourni]
 ▼
 3. Construire la requête = titre deviné par la vision + texte du vendeur ;
    les attributs vus par la vision pré-remplissent le système de questions
 ▼
 4. Le service d'identification cherche les candidats, applique
    les garde-fous de confiance et prépare une question si ambiguïté
 ▼
 5. Le modèle de vision valide le meilleur candidat (photo du vendeur
    comparée à l'image du catalogue) [au mieux, jamais bloquant]
 ▼
 6. Enregistrement de l'identification dans le journal
    [non bloquant : protégé par une capture d'erreur]
 ▼
 7. Réponse JSON : liste des candidats, validation visuelle,
    éventuelle question suivante, et explication textuelle
```

### Motifs transverses (présents partout dans l'API)

- Un intercepteur d'identifiant de requête est ajouté en tout premier. Un intercepteur
  (en anglais "middleware") est un morceau de code qui s'exécute autour de chaque
  requête. Le placer en premier garantit que l'identifiant unique de la requête est
  présent dans tous les journaux qui suivent.
- Les mesures de fonctionnement sont exposées au format Prometheus (un outil standard
  de collecte de mesures) mais seulement sur option, activée par la variable
  d'environnement `ENABLE_METRICS`. On les désactive pendant les tests automatisés,
  car la bibliothèque déclencherait sinon une erreur de doublon ("Duplicated
  timeseries") quand l'outil de test recrée l'application plusieurs fois.
- Le partage de ressources entre origines (en anglais "CORS") est configuré
  explicitement : on liste précisément les méthodes (GET et POST) et les en-têtes
  autorisés, au lieu d'autoriser tout par un caractère générique. Cette restriction
  réduit la surface d'attaque sur la page de connexion, qui est publique. Les origines
  autorisées sont celles de l'interface en développement (l'adresse locale du serveur
  de développement Vite, sur le port 5173).
- La persistance est gérée dans `src/api/persistence.py`, à l'aide de la bibliothèque
  SQLAlchemy (un outil qui fait le pont entre le code Python et une base de données).
  Chaque identification est historisée, mais au mieux : un échec d'enregistrement ne
  casse jamais l'API, car l'opération est protégée par une capture d'erreur.
- Les contrats de données sont définis dans `src/api/schemas.py` (192 lignes de schémas
  typés Pydantic version 2). Ce fichier est la source unique de vérité décrivant
  précisément la forme de chaque message d'entrée et de sortie.

---

## 4. Résultats mesurés

- Neuf points d'entrée opérationnels et documentés automatiquement. FastAPI génère une
  documentation interactive au standard OpenAPI, consultable à l'adresse `/docs`.
- Test de bout en bout réussi six fois sur six, joué dans un conteneur réel : connexion,
  envoi de photo, identification (30 candidats trouvés et validation visuelle au
  maximum), calcul de prix (niveau L1 atteint), puis rédaction d'un titre cohérent.
- Dégradation gracieuse vérifiée : sans clé d'accès au service de rédaction, le point
  d'entrée `/describe` bascule sur le rédacteur de remplacement ; sans index de
  recherche, `/identify` renvoie une erreur 503 actionnable. Dans les deux cas,
  l'application ne plante pas.
- Asynchronisme respecté : les opérations lourdes (recherche FAISS, modèle de vision)
  s'exécutent dans des fils séparés, la boucle d'événements reste libre pour traiter
  les autres requêtes.

> Pour la présentation orale, chiffres à mettre en avant : neuf points d'entrée, trois
> services chargés une fois au démarrage, un déroulé `/identify` en sept étapes (photo,
> vision, recherche, questions, validation, enregistrement, réponse), dégradation
> gracieuse partout (erreur 503 actionnable ou rédacteur de remplacement), et test de
> bout en bout réussi six fois sur six. Capture d'écran utile : la page de
> documentation `/docs` listant les points d'entrée, accompagnée d'une réponse JSON de
> `/identify`.

---

## 5. Analyse critique : où nous situons-nous ?

Points solides :

- Orchestration claire et testée. Un service par responsabilité, un déroulé lisible, et
  des garde-fous d'erreur à chaque étape (codes 401 pour un accès refusé, 422 pour des
  données invalides, 404 pour un produit introuvable, 503 pour un service
  indisponible).
- Asynchronisme correct (les opérations synchrones lourdes sont déportées dans des fils
  séparés) et streaming des étapes pour une expérience progressive.
- Dégradation gracieuse partout : si l'analyse de la photo échoue, on se rabat sur le
  texte ; si le modèle de langage est indisponible, on bascule sur le rédacteur de
  remplacement ; si l'enregistrement échoue, on poursuit quand même. La démonstration
  ne plante pas.
- Garde-fous de robustesse construits avec soin : utilisation de l'instruction `raise`
  (qui survit au mode optimisé), et traitement au mieux pour la validation visuelle et
  pour l'enregistrement, qui ne sont jamais bloquants.
- Sécurité : jeton de session exigé sur tout le métier, URL secrète non devinable pour
  servir les photos, et configuration explicite du partage entre origines.

Limites assumées :

- L'état global est conservé dans une simple structure unique en mémoire (un
  dictionnaire). C'est simple et suffisant pour un serveur à processus unique, mais peu
  adapté à une montée en charge sur plusieurs processus partageant un état : chaque
  processus rechargerait l'index pour son compte.
- La persistance de l'historique repose sur SQLite, une base de données légère stockée
  dans un seul fichier. C'est suffisant pour la démonstration, mais il faudrait passer
  à une base plus robuste comme PostgreSQL pour une mise en production sur plusieurs
  instances.
- Quelques commentaires de code datent d'une version antérieure, antérieure au passage
  d'une approche texte seul à une approche centrée sur la photo. Le code, lui, est bien
  centré sur la photo ; ces commentaires restent à nettoyer.
- Il n'y a pas de limitation de débit applicative (le contrôle du nombre de requêtes
  par utilisateur est délégué au répartiteur de charge placé en amont). Par ailleurs,
  la variante en temps réel `/identify/stream` ne gère pour l'instant que l'entrée
  texte et pas encore le parcours par photo.

---

## 6. Références

- FastAPI, "Lifespan events" : https://fastapi.tiangolo.com/advanced/events/
- FastAPI, "Concurrency and async / await" : https://fastapi.tiangolo.com/async/
- Pydantic version 2, "Models" : https://docs.pydantic.dev/latest/concepts/models/
- MDN, "Server-Sent Events" :
  https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

---

### En une phrase, pour la défense orale

Le cœur du temps d'exécution, c'est le fichier `pipeline.py` : il charge les modèles
une seule fois au démarrage, puis, pour chaque requête `/identify`, il enchaîne la
photo, l'extraction par le modèle de vision, la recherche FAISS, les garde-fous de
confiance, le système de questions, la validation visuelle et l'enregistrement, le tout
de façon asynchrone (pour ne jamais bloquer les autres requêtes) et avec une
dégradation gracieuse à chaque étape (un composant qui tombe ne casse jamais le flux).
