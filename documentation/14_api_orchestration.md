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
pannes. Ce travail de coordination est réparti principalement dans deux fichiers :
`src/api/main.py` (environ 700 lignes, qui définit les points d'entrée de l'API et
orchestre la passe d'identification raisonnée du Cycle 36) et `src/api/pipeline.py`
(environ 610 lignes, qui contient la logique d'enchaînement des modèles : recherche,
vote de catégorie, cascade de prix, rédaction). À ces deux fichiers s'ajoutent trois
modules spécialisés appelés par l'orchestrateur : `src/vlm/reasoned_identification.py`
(la passe de jugement par le modèle de langage, Cycle 36), `src/serving/listing_fill.py`
(l'assemblage de la fiche structurée avec provenance) et `src/pricing/01_algorithmique.py`
(la cascade de prix transparente). Le détail de chacun est donné plus bas.

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
| `POST /identify` | jeton requis | Le cœur du système : à partir de photos et d'un texte optionnel, renvoie les meilleurs produits candidats (réordonnés pour mettre le bon produit en tête), une fiche structurée du produit retenu, le jugement raisonné du modèle de langage (famille, ancre de prix neuf, question discriminante), une éventuelle question de précision et une validation visuelle. |
| `POST /price` | jeton requis | Calcule un prix suggéré par une cascade transparente de cinq niveaux (L1, puis le niveau L1.5 ajouté au Cycle 36, puis L2, L3 et L4). |
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

#### L'identification raisonnée (Cycle 36, fichier `src/vlm/reasoned_identification.py`)

C'est l'ajout le plus important du Cycle 36. L'idée directrice se résume en une phrase :
le moteur de recherche apporte la **connaissance** (les quinze fiches catalogue réelles
les plus proches), et le modèle de langage apporte le **jugement** (lequel de ces
quinze produits correspond vraiment à la photo, et à quel prix neuf). On sépare ainsi
deux compétences que l'on confondait avant : trouver des candidats plausibles, et
choisir le bon parmi eux.

Concrètement, la fonction `reason_identify` réalise un seul appel au modèle de langage
multimodal (via OpenRouter). On lui envoie une à deux photos du vendeur (encodées en
"data-url", c'est-à-dire l'image transformée en texte base64 directement dans le
message) accompagnées des **quinze fiches candidates résumées en texte** (et non les
quinze images du catalogue, ce qui économise beaucoup de jetons donc de coût), des
attributs déjà observés par la vision, et du texte du vendeur. Le modèle renvoie un
objet JSON contenant : la famille de produit qu'il reconnaît, sa confiance dans cette
famille, l'identifiant du candidat qu'il choisit, un drapeau "absent du catalogue"
(en anglais "catalog miss"), une **estimation du prix neuf de référence en dollars**
(l'ancre de prix), la confiance de cette ancre, les indices des fiches qui ont servi à
l'établir, un éventuel besoin de question discriminante, et une liste de facettes
chacune accompagnée de sa source.

Le modèle utilisé est paramétrable par la variable d'environnement
`PHOTO_VLM_IDENTIFY_MODEL` ; par défaut, on réutilise le même modèle que pour
l'extraction photo, `qwen/qwen3.5-flash-02-23`. Pour garantir un résultat reproductible
(le même cliché donne la même fiche), on règle la température à 0, on fixe une graine
aléatoire ("seed"), et on désactive la chaîne de raisonnement explicite. Ce module ne
crée pas son propre client réseau : il réutilise les fonctions `post_with_retry` et
`_to_data_url` déjà écrites pour l'extraction photo, afin de ne pas dupliquer la
logique de réessai et d'encodage.

Plusieurs garde-fous d'ancrage protègent contre l'invention (ce qu'on appelle
l'hallucination du modèle) :

- Si le modèle choisit un identifiant qui n'est **pas** dans les quinze candidats
  (donc inventé), on retombe sur le premier candidat de la recherche **et** on remet sa
  confiance de famille à zéro. La logique est subtile : le modèle n'a pas réellement
  endossé un candidat valide, donc l'aval ne doit pas traiter ce choix comme un fait
  certain.
- Une facette dont la source est invalide (ni "observé", ni "analogie", ni un indice de
  fiche existant) est purement et simplement jetée. On n'affirme jamais une
  caractéristique non sourcée.
- L'ancre de prix, en revanche, est **conservée même sans preuve** ("evidence") : c'est
  assumé comme une **estimation explicitement étiquetée**, pas comme un fait catalogue.
  Mieux vaut une estimation honnêtement présentée comme telle que de retomber sur une
  médiane polluée (on y revient dans la partie prix).

Toute la passe est en mode "best-effort", c'est-à-dire non bloquante (règle interne
R15). En cas d'absence de clé d'accès, de modèle injoignable, de JSON inexploitable ou
d'exception quelconque, `reason_identify` renvoie simplement `None`, et le pipeline
poursuit avec le classement de recherche brut et la cascade de prix habituelle. La
passe raisonnée ne peut jamais faire planter l'identification ni produire une fiche
vide.

Bénéfice concret du réordonnancement : le candidat choisi par le modèle est **remonté
en tête** de la liste des candidats. Comme la fiche, le prix et la validation visuelle
portent tous sur le candidat de tête, ils portent désormais sur le **bon** produit.
Avant cet ajout, le premier candidat de la recherche pouvait être un accessoire (par
exemple une coque d'iPhone affichée comme s'il s'agissait de l'iPhone lui-même), ce qui
faussait toute la suite.

#### Le texte vendeur, source d'autorité (fichier `src/api/main.py`, fonction `_seller_text_best_match`)

Le texte libre saisi par le vendeur (le champ "Précisions") est traité comme une
**source d'autorité déterministe**, indépendante du modèle de langage. La raison est
pratique : le modèle rapide ignore parfois la consigne du texte vendeur. Si ce texte
nomme un produit qui figure dans les candidats, on retient ce candidat sans faire
intervenir le modèle.

Le match exigé est volontairement fort, pour éviter les faux positifs : il faut au
moins deux jetons discriminants du texte présents dans le titre du candidat, **et** au
moins la moitié des jetons du texte couverts. On garde délibérément les numéros de
modèle même à un seul chiffre (pour distinguer un "Momentum 3" d'un "Momentum 2.0"),
car c'est souvent le numéro qui départage deux variantes. En cas d'égalité entre
plusieurs candidats, on choisit celui dont le prix est le plus **représentatif**, au
sens du plus proche de la médiane : cela évite de bâtir la fiche sur une donnée
corrompue (par exemple un même "Momentum 3" listé à 9755 dollars par erreur de saisie).

Quand le texte vendeur l'emporte ainsi, une branche dédite "override vendeur" bâtit la
fiche sur la fiche catalogue du produit nommé, et écarte les attributs observés par la
vision qui concernaient un autre produit. Sur un texte vide (cas du parcours photo
seule), cette logique ne fait strictement rien : aucune régression possible.

#### Le service de calcul de prix

Ce service charge le fichier de configuration du modèle de prix
(`pricing-cascade_v1.joblib`, un fichier sérialisé contenant notamment les prix médians
par catégorie) puis délègue le calcul à une cascade de prix transparente, désormais à
**cinq niveaux** (le Cycle 36 a inséré un niveau intermédiaire L1.5). Le principe de la
cascade reste le même : on tente d'abord la méthode la plus fiable, et si elle n'est pas
applicable, on descend vers une méthode de repli. Du plus fiable au moins fiable :

- **L1 (haute)** : le prix catalogue **réel** du produit identifié, auquel on applique
  une décote d'état puis une dépréciation liée à l'âge. C'est un fait, pas une
  estimation.
- **L1.5 (haute-moyenne, ajouté au Cycle 36)** : l'**ancre de prix neuf estimée par
  l'intelligence artificielle** lors de la passe raisonnée. On lui applique **exactement
  la même décote déterministe** qu'à L1. Point important pour la défense : seule l'ANCRE
  est une estimation de l'IA ; la décote, elle, reste 100 % déterministe et transparente,
  donc l'affirmation "pas de modèle de prix opaque" reste vraie. Ce niveau est placé
  **avant** les médianes de voisins, parce que ces dernières sont polluées (voir
  ci-dessous).
- **L2 (moyenne)** : la médiane des prix des voisins trouvés par la recherche. Niveau
  **rétrogradé** au Cycle 36 : ce sont précisément ces médianes, polluées par des
  accessoires, des coques et des lots, qui donnaient des prix absurdes (de l'ordre de
  6 euros pour une montre valant 150 euros).
- **L3 (basse)** : la médiane des prix de la catégorie, quand seule la catégorie est
  connue. Également rétrogradée pour la même raison.
- **L4 (très basse)** : valeur de repli en saisie manuelle. L'interface n'affiche plus
  "0,00 €" mais "Prix à fixer (saisie manuelle)".

Chaque suggestion indique le niveau utilisé, une fourchette de prix et une explication
lisible, pour rester transparente.

**Les décotes.** La décote d'état est un multiplicateur appliqué au prix neuf : neuf
1,00 ; très bon état 0,75 ; bon état 0,55 ; correct 0,35 ; et "pour pièces / HS" 0,15
(cet état "pour pièces" est nouveau au Cycle 36, car c'est un cas courant en occasion).
La dépréciation est linéaire par catégorie (par exemple −15 %/an pour l'électronique).
Enfin, les prix du catalogue sont en dollars (données Amazon américaines) alors que
l'interface affiche des euros : on convertit par un taux fixe documenté (environ 0,92,
ajustable par la variable d'environnement `PRICE_USD_EUR_RATE`), appliqué après la
décote et la dépréciation.

**Les garde-fous du Cycle 36.** Trois protections rendent la cascade robuste aux données
sales :

- *Anti sous-évaluation* : si une médiane de voisins tombe nettement sous le prix neuf
  attendu (décoté au même état et au même âge), on la relève à un plancher (ratio 0,25
  du prix neuf décoté). C'est un garde-fou surtout défensif : le vrai travail de
  correction est fait par le niveau L1.5.
- *Cohérence de L1* : si une ancre de l'IA existe et que le prix catalogue du premier
  candidat est dérisoire en comparaison (en dessous de 0,2 fois l'ancre), c'est le signe
  que ce premier candidat est un accessoire mal apparié (une coque à 43 dollars pour un
  iPhone à 598 dollars). On ignore alors ce prix catalogue pollué et on bascule sur
  L1.5, ce qui évite d'afficher "iPhone à 15 euros". Le ratio est volontairement bas :
  un prix catalogue est un fait (un produit reconditionné ou en promotion peut être
  légitimement plus bas que l'estimation IA), on ne l'écarte que s'il est aberrant.
- *Prix catalogue aberrant* : un prix catalogue plus de 4 fois supérieur à la médiane
  des voisins (avec au moins trois voisins pour fiabiliser la médiane) est une donnée
  corrompue (du type 9755 dollars pour un casque) ; on l'ignore au profit des voisins.

Côté API, l'endpoint `/price` reçoit désormais l'ancre de prix neuf et sa confiance
(champs `reference_new_price_usd` et `reference_new_confidence`, issus de la passe
raisonnée et repassés par l'interface), et les transmet à la cascade. Ces champs sont
optionnels : sans eux, le comportement d'un ancien client reste strictement inchangé.

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

#### La fiche structurée exhaustive (fichier `src/serving/listing_fill.py`, fonction `assemble_listing`)

À partir du Cycle 36, l'endpoint `/identify` ne renvoie plus seulement une liste de
candidats : il renvoie aussi une **fiche structurée** du produit retenu, prête à être
affichée façon marketplace. Cette fiche génère toutes les données structurées
exploitables : d'abord les facettes du schéma attendu pour la catégorie
(`expected_facets`), puis les attributs **riches** hors schéma (format, caractéristique,
certification, tension, puissance, connectivité, et autres, dont les valeurs trop
longues sont tronquées pour éviter le bruit), et enfin la **fusion des facettes jugées
par l'intelligence artificielle** lors de la passe raisonnée. Le texte brut issu de
l'OCR ("visible_text", souvent un filigrane ou un titre recopié) est délibérément exclu.

Le point fort de cette fiche est la **traçabilité de chaque champ** par sa provenance.
Il y a cinq provenances possibles, affichables telles quelles : "observé" (lu sur la
photo par la vision), "catalogue" (issu d'un produit catalogue jugé fiable),
"typique-à-vérifier" (imputé des voisins, donc non affirmé comme certain), "catégorie"
(déduit de la catégorie votée) et "vendeur" (saisi ou choisi par le vendeur). En cas de
produit absent du catalogue, les caractéristiques du mauvais candidat ne sont **jamais**
traitées comme des faits. De même, une facette dont la source est "analogie" (estimée
par comparaison) n'est pas injectée comme un fait : on reste fidèle au principe
d'anti-invention.

La fiche suit aussi une cascade de niveaux, dans le même esprit que la cascade de prix :
"N1_catalog" (match catalogue fiable), "N2_category_photo" (pas de match fiable mais
catégorie sûre) et "N3_observed" (catégorie incertaine, on s'appuie sur le seul observé).

Deux corrections de finesse méritent d'être notées. D'une part, le champ "Type de
produit" prend désormais la catégorie du produit **identifié** (réordonné), et non plus
le résultat du vote pollué : avant, la présence d'une coque parmi les voisins pouvait
faire afficher "Basic Cases" pour un iPhone. D'autre part, la **complétude** est mesurée
par **catégorie fine** : on ne retient du schéma de la macro-catégorie que les facettes
réellement présentes chez au moins un candidat de la même catégorie fine. Ainsi une
enceinte n'est plus pénalisée parce qu'il lui manque une "capacité". L'état (choix
vendeur, toujours disponible) est exclu du dénominateur, pour ne pas fausser le calcul.

#### Le parcours vendeur côté interface (dossier `frontend/src`)

Le Cycle 36 a refondu le parcours du vendeur pour qu'il colle au nouveau pipeline. Le
choix manuel du "type d'objet" a été **supprimé** : le type est désormais dérivé de la
catégorie identifiée par la fonction `kindFromCategory` (fichier `condition.ts`). Les
motifs de détection portent sur le **mot entier** et excluent les accessoires, ce qui
règle deux pièges : un casque "Over-Ear Headphones" qui contient les lettres "phone"
n'est plus classé comme un téléphone, et les chargeurs ne le sont plus non plus. La
conséquence ergonomique est que la **checklist d'état spécifique** (santé de la batterie
et état de l'écran pour un téléphone, clavier pour un ordinateur portable, manettes pour
une console, etc.) ne s'affiche qu'**après** l'identification, c'est-à-dire au bon
moment.

Trois autres ajouts côté interface :

- L'état "Pour pièces / HS" est proposé, et un champ optionnel "Année d'achat" alimente
  la dépréciation (à défaut, on suppose un âge de deux ans, ce qui est signalé).
- L'**auto-confirmation** : si l'intelligence artificielle est sûre d'elle (statut
  "identified"), on enchaîne directement vers la fiche, sans demander au vendeur de
  choisir parmi les candidats ; sinon, on montre les candidats. Un bouton "Ce n'est pas
  le bon produit ? Voir les autres résultats" reste accessible sur la fiche.
- Le **drapeau "Modèle à confirmer"** : le pourcentage de confiance affiché correspond à
  la part du vote des voisins sur la catégorie fine, et n'est montré que s'il est net (au
  moins 60 %). Un pourcentage bas ne signale pas un doute sur la catégorie, mais une
  **fragmentation** du vote (le modèle exact est ambigu, par exemple un casque où le vote
  se disperse). Dans ce cas, plutôt qu'un pourcentage trompeur, on affiche un bandeau
  actionnable invitant à préciser le modèle ou à ajouter une photo de l'étiquette ou de
  la boîte, en reprenant la question discriminante de l'IA quand elle existe. Un bandeau
  distinct "Produit estimé, absent du catalogue" prévient en cas de produit hors
  catalogue, et l'étiquette honnête "Prix neuf estimé par IA" accompagne le niveau L1.5.

#### L'observabilité métier (fichier `src/api/main.py`)

Au-delà des mesures HTTP exposées au format Prometheus (latence, nombre de requêtes,
requêtes en cours), le Cycle 36 ajoute des **journaux structurés** (via la bibliothèque
structlog) qui rendent chaque requête **inspectable**. Deux événements sont émis :
`identify_done` (avec le statut, le nombre de candidats, le score du premier, la
catégorie fine et sa confiance, un drapeau "passe raisonnée effectuée", un drapeau
"réordonné", le "catalog miss", l'ancre de prix, la question éventuelle, la confiance de
famille, la complétude, et les temps d'extraction et de raisonnement) et `price_done`
(avec le niveau de cascade réellement utilisé, la méthode, le prix suggéré, la présence
d'une ancre, la catégorie et l'état). Le but est concret : pouvoir **lire** ce que fait
le pipeline en production (le taux de produits hors catalogue, la part d'usage du niveau
L1.5, ou l'endroit où part la latence), sans rien de décoratif.

#### Sécurité et durcissement (revue adverse, Cycle 36)

Une revue adverse sur cinq dimensions a relevé puis corrigé un ensemble de problèmes
(sept jugés "élevés", huit "moyens"). Les contre-mesures notables :

- Des **bornes** sont posées sur les prix dans les schémas (strictement positifs,
  inférieurs à un million, et sans valeurs infinies ou "NaN", c'est-à-dire "non un
  nombre"). De même, le texte vendeur et les listes (identifiants de photos, prix des
  voisins) sont bornés en taille, pour éviter qu'un message démesuré ne gonfle le prompt
  envoyé au modèle (problème de coût et de déni de service).
- Le texte vendeur est **délimité comme donnée non fiable** dans le prompt de la passe
  raisonnée, et le modèle est explicitement prévenu de ne pas l'interpréter comme une
  instruction (protection contre l'injection de consigne, en anglais "prompt
  injection").
- Pour la **latence**, le troisième appel au modèle (la validation visuelle) est sauté
  quand la passe raisonnée a déjà tranché avec confiance, puisqu'elle couvre déjà le
  jugement de correspondance.

### Le déroulé d'une requête `/identify`, étape par étape (refondu au Cycle 36)

```
 POST /identify {image_ids, text_hint, already_observed}
 │ (jeton de session vérifié)
 ▼
 1. Récupérer les chemins des photos à partir de leurs identifiants
    [erreur 422 si aucune photo valide]
 ▼
 2. EXTRACTION : le modèle de vision analyse les photos (dans un fil séparé)
    et en extrait un titre probable et des attributs
    [erreur 503 si la clé d'accès est absente ET qu'aucun texte n'est fourni ;
     sinon, repli sur le texte seul si la vision échoue]
 ▼
 3. Construire la requête = titre deviné par la vision + texte du vendeur ;
    les attributs vus par la vision pré-remplissent le système de questions
 ▼
 4. RETRIEVAL : le service d'identification cherche les candidats (30 voisins),
    vote la catégorie fine, applique les garde-fous de confiance, prépare
    une question si ambiguïté
 ▼
 5. PASSE RAISONNÉE (Cycle 36) : le modèle de langage juge le top-15
    (dans un fil séparé) → famille, candidat choisi, ancre de prix neuf,
    question discriminante, facettes sourcées [best-effort, None si indispo]
 ▼
 6. RÉORDONNANCEMENT : on retient le produit nommé par le texte vendeur s'il
    fait foi, sinon le candidat choisi par la passe raisonnée ; ce produit
    est remonté en TÊTE des candidats → fiche/prix/validation portent dessus
 ▼
 7. VALIDATION VISUELLE : le modèle compare la photo du vendeur à l'image
    du catalogue du candidat de tête [au mieux ; SAUTÉE si la passe raisonnée
    est déjà confiante, pour économiser un appel et de la latence]
 ▼
 8. FICHE EXHAUSTIVE : assemblage de la fiche structurée du produit retenu
    (facettes du schéma + attributs riches + facettes jugées par l'IA),
    avec provenance par champ et complétude par catégorie fine
 ▼
 9. Enregistrement de l'identification dans le journal + log métier
    structuré [non bloquant : protégé par une capture d'erreur]
 ▼
10. Réponse JSON : candidats réordonnés, fiche structurée, jugement raisonné,
    validation visuelle, éventuelle question suivante, et explication
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
- Les contrats de données sont définis dans `src/api/schemas.py` (environ 250 lignes de
  schémas typés Pydantic version 2). Ce fichier est la source unique de vérité décrivant
  précisément la forme de chaque message d'entrée et de sortie. Le Cycle 36 y a ajouté le
  niveau de confiance L1.5 (énumération `ConfidenceLevelEnum`), l'état "pour pièces / HS"
  (énumération `ConditionEnum`), les champs d'ancre de prix dans la requête `/price`, les
  schémas de la fiche structurée (`AssembledListingOut`, `ListingFieldOut`) et du
  jugement raisonné (`ReasonedIdentificationOut`, `ReasonedFacetOut`), tous deux
  optionnels (laissés à `None` quand la passe raisonnée est indisponible).

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

### Mesure de qualité de fiche sur panel réel (Cycle 36)

Plutôt que de s'appuyer sur des anecdotes, le Cycle 36 a mis en place un protocole de
mesure reproductible (script `scripts/mesure_qualite_fiche.py`, sorties dans
`reports/09_fiche_quality/mesure_fiche.json` et `.md`). Il rejoue le pipeline complet
sur le **panel réel** `data/photos_eval` (94 produits, dont 93 effectivement mesurés ;
les noms des dossiers servent de vérité-terrain), en mode **photo seule**, c'est-à-dire
sans le texte de précisions du vendeur, donc dans le cas le plus difficile. Résultats
mesurés :

- **Identification** : 90,3 % (critère : au moins la moitié des jetons clés du nom
  attendu se retrouvent dans la famille jugée par l'IA et le titre du premier candidat).
  Le rappel moyen de jetons est de 78 %.
- **Complétude de la fiche** : 0,84 en moyenne, 0,83 en médiane.
- **Passe raisonnée** : effectuée dans 100 % des cas. Taux de produits hors catalogue
  ("catalog miss") : 28 %. Question posée : environ 11 %. Répartition des niveaux de
  prix sur le panel : 42 fiches en L1, 51 fiches en L1.5.
- **9 produits non identifiés, tous expliqués** : perception du modèle (une RTX 4080
  Super lue comme une 3080, une Xbox Series S, un Sennheiser Momentum lu comme un
  Philips), produit absent du catalogue (un SSD, une station d'accueil), ou nom de
  dossier ambigu (un simple artefact de mesure, pas une erreur du pipeline).

Cette mesure remplace les anecdotes par un chiffre défendable (doctrine interne R21 :
mesurer sur de vraies sorties, jamais sur des comptages de lignes ou des pourcentages
abstraits).

> Pour la présentation orale, chiffres à mettre en avant : neuf points d'entrée, trois
> services chargés une fois au démarrage, un déroulé `/identify` refondu au Cycle 36
> (extraction, recherche, passe raisonnée, réordonnancement, validation, fiche
> exhaustive, réponse), dégradation gracieuse partout (erreur 503 actionnable ou
> rédacteur de remplacement), et la mesure de qualité de fiche sur le panel réel
> (94 produits, identification 90,3 %, complétude 0,84). Capture d'écran utile : la page
> de documentation `/docs` listant les points d'entrée, accompagnée d'une réponse JSON de
> `/identify` montrant le bloc `reasoned` et la fiche `informations_cles`.

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
  (qui survit au mode optimisé), et traitement au mieux pour la validation visuelle, la
  passe raisonnée et l'enregistrement, qui ne sont jamais bloquants.
- Séparation connaissance / jugement (Cycle 36) : la recherche apporte les candidats
  réels, le modèle de langage les juge sans jamais pouvoir introduire un produit hors de
  ces candidats. Le prix reste une cascade déterministe (aucun modèle de prix opaque) :
  seule l'ancre de prix neuf est une estimation, explicitement étiquetée comme telle.
- Sécurité : jeton de session exigé sur tout le métier, URL secrète non devinable pour
  servir les photos, configuration explicite du partage entre origines, bornes sur les
  entrées (anti déni de service), et texte vendeur traité comme donnée non fiable dans
  les prompts (anti injection de consigne).

Limites assumées :

- Photo seule, la perception du **modèle exact** par le modèle de vision reste limitée
  pour les produits sans marquage visible sur les clichés envoyés (par exemple un
  Sennheiser Momentum 3 dont le logo est sur l'étui) : le modèle peut alors choisir un
  sosie avec aplomb. Trois mécanismes atténuent ce risque : le texte vendeur faisant
  autorité (la métadonnée fixe le produit, et "sauve" quand le produit est bien au
  catalogue), le drapeau "Modèle à confirmer", et le bouton "Ce n'est pas le bon ?".
- Le modèle rapide par défaut (qwen3.5-flash) **sous-déclenche** le signalement de
  produit hors catalogue : il colle volontiers à un sosie d'une autre génération (un
  iPhone 14 lu comme un 13, une RTX 4080 comme une 3080). Un modèle jugé plus fort,
  branché via `PHOTO_VLM_IDENTIFY_MODEL`, ferait mieux ; cette option n'est pas câblée
  par défaut.
- Le garde-fou anti sous-évaluation de la cascade de prix est surtout défensif : c'est
  bien le niveau L1.5 (l'ancre de l'IA) qui fait le vrai travail de correction.

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

Le cœur du temps d'exécution, ce sont `main.py` et `pipeline.py` : ils chargent les
modèles une seule fois au démarrage, puis, pour chaque requête `/identify`, ils
enchaînent l'extraction par le modèle de vision, la recherche FAISS, la **passe
raisonnée** où le modèle de langage juge les quinze meilleurs candidats (Cycle 36), le
**réordonnancement** qui remonte le bon produit en tête (le texte vendeur faisant
autorité), la validation visuelle et l'assemblage d'une **fiche structurée** avec
provenance et complétude, puis l'enregistrement. Le prix est calculé par une cascade
transparente à cinq niveaux (avec le niveau L1.5, l'ancre de prix neuf estimée par
l'IA). Le tout est asynchrone (pour ne jamais bloquer les autres requêtes) et en
dégradation gracieuse à chaque étape (un composant qui tombe ne casse jamais le flux),
et chaque requête est inspectable par des journaux métier structurés. La preuve : sur le
panel réel de 94 produits, en photo seule, l'identification atteint 90,3 % et la
complétude de fiche 0,84.
