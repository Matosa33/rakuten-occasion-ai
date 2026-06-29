# 01. Data engineering (la matière première)

> Récupérer, comprendre, nettoyer et découper les données proprement, avant d'entraîner le moindre
> modèle. C'est ici qu'on gagne ou qu'on perd la fiabilité de tout le reste du projet.

Ce document se lit seul. Aucune connaissance technique préalable n'est nécessaire : chaque terme
spécialisé est expliqué en une phrase la première fois qu'il apparaît. Vous n'avez besoin d'aucun
autre fichier pour comprendre ce composant de bout en bout.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)

Le **data engineering**, c'est toute la préparation des données avant l'entraînement d'un modèle
d'intelligence artificielle. Concrètement, quatre grandes tâches :

1. **Récupérer** les données brutes (ici, un catalogue de produits et leurs avis clients).
2. Les **auditer**, c'est-à-dire les inspecter : combien y en a-t-il ? Sont-elles complètes ? Bien
   réparties entre les catégories ? Contiennent-elles des pièges qui fausseraient les mesures ?
3. Les **nettoyer** : corriger les types, traiter les valeurs manquantes, retirer les doublons,
   remettre le texte d'aplomb.
4. Les **découper** en trois jeux séparés :
   - le **train** (jeu d'entraînement) : les exemples sur lesquels le modèle apprend ;
   - la **validation** : un jeu à part qui sert à régler les réglages internes du modèle (ses
     « hyperparamètres », c'est-à-dire les boutons qu'on tourne à la main avant l'entraînement) ;
   - le **test** : un jeu gardé intact, sur lequel on mesure la performance une seule fois, tout à
     la fin, pour obtenir un chiffre honnête.

Une image : avant de cuisiner, on choisit et on lave les ingrédients. De mauvais ingrédients
donnent un mauvais plat, quel que soit le talent du cuisinier. Le dicton du métier le résume :
« garbage in, garbage out » (des déchets en entrée, des déchets en sortie).

### Le danger numéro un : la fuite de données (data leakage)

C'est l'erreur qui rend une évaluation entièrement fausse. Une **fuite de données** survient quand
une information du jeu de test « fuit » dans le jeu d'entraînement. Le modèle a alors vu les
réponses à l'avance : il paraît brillant pendant le test, puis s'effondre une fois en production
face à des données réellement nouvelles. C'est comme un élève qui aurait eu le corrigé avant
l'examen.

Voici les formes de fuite que nous avons traquées et leur signification :

- **Variantes du même produit des deux côtés** : par exemple le même téléphone décliné en 64 Go et
  en 128 Go, l'une dans le train et l'autre dans le test. Le modèle « reconnaît » l'objet au lieu
  d'apprendre à généraliser. C'est notre risque principal.
- **Fuite par le label** : une colonne contient déjà la réponse que le modèle est censé deviner.
- **Fuite temporelle** : on entraîne sur des données du futur et on teste sur des données du passé,
  ce qui ne reflète pas l'ordre réel des événements.
- **Fuite par feature** : une statistique (une moyenne, une médiane) calculée sur la totalité des
  données au lieu du seul jeu d'entraînement ; cette statistique transporte alors de l'information
  du test vers l'entraînement.
- **Fuite utilisateur** : le même utilisateur présent des deux côtés, ce qui poserait problème pour
  un futur modèle qui apprendrait les goûts personnels des clients.

### Pour l'expert

- La fuite « variantes du même produit » est résolue par un **découpage par groupe** : on regroupe
  toutes les lignes d'un même produit sous une clé unique, l'identifiant `parent_asin`, et ce groupe
  reste entièrement dans un seul des trois jeux. La technique standard porte le nom de
  **GroupKFold** : un découpage qui garde chaque groupe d'un seul côté.
- Le déséquilibre entre catégories (certaines beaucoup plus grosses que d'autres) est évité par une
  **stratification** : on respecte, dans chacun des trois jeux, la même proportion de chaque
  catégorie.
- La fuite par feature est écartée par une règle stricte : toute statistique calculée (médiane,
  pondération de mots, index de recherche) doit l'être sur le jeu d'entraînement uniquement, jamais
  sur la validation ni sur le test.

---

## 2. État de l'art (les bonnes pratiques de référence)

- **Découper avant de pré-traiter.** On sépare d'abord les trois jeux, puis on calcule les
  statistiques sur le seul jeu d'entraînement. C'est l'ordre qui empêche toute contamination.
- **Données groupées, découpage qui respecte les groupes.** Quand plusieurs lignes appartiennent à
  une même entité (un produit, un utilisateur), tout le groupe reste du même côté du découpage.
- **Contrats de schéma.** Un « contrat de schéma » est une liste de règles écrites une fois pour
  toutes : telle colonne doit être du texte, telle autre un nombre entre 0 et 5, telle autre ne
  doit jamais être vide. On vérifie automatiquement ces règles à chaque entrée de données dans le
  système. Le principe : « valider tôt et souvent ». Les deux outils de référence dans l'écosystème
  Python sont Pandera et Great Expectations.
- **Contexte 2025.** Selon les études du secteur, 70 à 85 % des projets d'apprentissage automatique
  n'aboutissent pas, et la mauvaise qualité des données arrive en tête des causes. D'où l'attention
  portée à cette étape.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### a) Choix du jeu de données et audit

Faute de jeu de données Rakuten public, et parce qu'aspirer le site (le « scraping ») exposerait à
un risque juridique, nous utilisons un jeu de données ouvert comme remplaçant représentatif :
**Amazon Reviews 2023**, publié par le laboratoire de recherche McAuley (université de Californie à
San Diego) et hébergé sur la plateforme Hugging Face. Ce choix introduit un biais (Amazon n'est pas
Rakuten) que nous assumons et documentons. L'architecture mise au point se transpose ; seuls les
chiffres exacts changeraient sur de vraies données Rakuten.

L'audit est réalisé par quatre programmes numérotés, exécutés dans l'ordre :

1. **Téléchargement complet** des catégories retenues, converties au format Parquet (un format de
   stockage en colonnes, compact et rapide à lire). Le téléchargement gère la reprise après coupure
   et vérifie l'intégrité des fichiers.
2. **Audit de qualité** : taux de valeurs manquantes par colonne, types de données, doublons,
   longueurs des textes.
3. **Audit des distributions** : répartition par catégorie, distribution des prix, des notes et des
   dates.
4. **Audit des biais et des fuites** : déséquilibre entre catégories, biais de prix, biais
   temporel, et les signaux de fuite décrits plus haut.

Chacun de ces programmes produit un rapport accompagné d'un fichier de mesures chiffrées, ce qui
rend l'audit reproductible et vérifiable.

Une précaution de méthode mérite d'être soulignée : avant de télécharger des dizaines de
giga-octets, nous interrogeons d'abord les métadonnées du jeu de données (sa taille, le nombre
d'articles par catégorie). Cela évite de fixer le périmètre du projet à l'aveugle.

À noter aussi : le travail se fait avec la bibliothèque polars (un moteur de traitement de données
très rapide) en mode « lazy » et « streaming ». Concrètement, les calculs ne chargent jamais toutes
les données en mémoire d'un coup : ils les traitent par flux. C'est indispensable ici, car certaines
catégories comptent des dizaines voire des centaines de millions de lignes, ce qui ne tiendrait pas
dans la mémoire vive d'un ordinateur ordinaire.

### b) Un périmètre maîtrisé

Après un audit large couvrant une quinzaine de catégories, le projet a été volontairement recentré
sur **quatre catégories** où l'image du produit est déterminante et où le marché de l'occasion est
bien réel :

- Electronics (électronique),
- Cell_Phones_and_Accessories (téléphones et accessoires),
- Video_Games (jeux vidéo),
- Tools_and_Home_Improvement (outils et bricolage).

Ce périmètre représente environ **4,5 millions de produits** et environ **96 millions d'avis**.
Restreindre ainsi le champ rend le projet réalisable avec des ressources matérielles modestes, sans
sacrifier la pertinence. Ce choix est une décision tracée et justifiée, pas un hasard : c'est une
façon d'éviter l'élargissement progressif et incontrôlé du périmètre. Les onze autres catégories
restent téléchargées sur disque et pourraient être réintégrées plus tard. Le contrat de schéma
vérifie d'ailleurs que la colonne d'origine de chaque ligne (`_source_category`) ne contient bien
que ces quatre catégories.

### c) Le nettoyage en six étapes

Le nettoyage se déroule en six programmes numérotés, chacun produisant un fichier intermédiaire
servant d'entrée au suivant :

1. **Jointure des métadonnées avec les agrégats d'avis.** On rapproche, pour chaque produit, sa
   fiche descriptive et un résumé de tous ses avis. Ce résumé condense les avis en quelques chiffres
   parlants : nombre d'avis, note moyenne, écart-type des notes, part d'achats vérifiés, part de
   notes 5 étoiles et 1 étoile, année du premier et du dernier avis, nombre de clients distincts,
   moyenne des votes « avis utile ». Le résultat est une table où chaque ligne représente un produit
   (et non un avis pris isolément), car les modèles internes du projet raisonnent au niveau du
   produit.
2. **Suppression des colonnes trop vides.** Deux colonnes presque toujours absentes hors de
   quelques catégories (le sous-titre et l'auteur) sont vidées là où elles n'apportent rien. On ne
   supprime pas la colonne elle-même : on met simplement ses valeurs à « vide » hors de son domaine
   utile, ce qui garde une structure de table stable.
3. **Normalisation du texte.** On retire les balises HTML résiduelles (par exemple `<br>` ou
   `&amp;`), on convertit les caractères d'échappement HTML en caractères normaux, on réduit les
   espaces multiples à un seul et on supprime les espaces de début et de fin. Choix volontaire : on
   ne passe pas tout en minuscules, car les sigles et les marques (USB, Apple, Samsung) portent de
   l'information utile à la classification.
4. **Plafonnement des longueurs de texte et ajout d'indicateurs.** La description est plafonnée à
   **8192 caractères** (un avis isolé atteignait 1 476 557 caractères, ce qui ferait planter ou
   ralentir fortement l'étape suivante) et le titre à **1024 caractères**. On ajoute quatre
   indicateurs vrai/faux : description trop courte (moins de 5 caractères, ce qui concerne environ
   45 % des produits au total), titre trop court, présence d'une description, présence d'un titre.
5. **Création de nouvelles colonnes calculées (feature engineering).** Une « feature » est une
   colonne d'entrée fournie au modèle. On en dérive plusieurs :
   - `price_num` : le prix nettoyé et converti en nombre (on retire le symbole monétaire et les
     espaces) ; il reste vide pour environ 59 % des produits qui n'ont pas de prix exploitable ;
   - `log_price` : le logarithme du prix, utile aux modèles parce que les prix s'étalent sur une
     très large échelle ;
   - `price_band` : une étiquette de gamme, « low » (moins de 50 dollars), « mid » (de 50 à
     200 dollars) ou « high » (200 dollars et plus) ;
   - `length_title` et `length_description` : les longueurs de texte en caractères ;
   - `n_reviews_log` : le logarithme du nombre d'avis, pour atténuer l'effet des produits ayant
     énormément d'avis ;
   - `years_active` : la durée de vie visible du produit en années (du premier au dernier avis) ;
   - `recency_year` : le nombre d'années écoulées depuis le dernier avis, comptées par rapport à
     2023, dernière année du jeu de données.
   Toutes ces colonnes se calculent ligne par ligne, à partir de la seule valeur de la ligne, sans
   jamais utiliser de statistique globale. C'est volontaire : cela garantit l'absence de fuite par
   feature.
6. **Construction d'une table d'affichage produit.** On prépare une table légère pour l'interface :
   l'adresse de la vignette principale, l'ensemble des vues du produit (limité à 8 images pour ne
   pas alourdir), la catégorie fine telle qu'affichée sur le site (par exemple « Graphics Cards »),
   le chemin complet de rangement (par exemple « Electronics > Computers > Laptops »), la vraie
   marque du fabricant (plus fiable que le nom de la boutique vendeuse) et quelques caractéristiques
   distinctives, appelées **facettes** (couleur, capacité, taille, matériau, etc.). Une « facette »
   est un attribut court et comparable d'un produit, qui sert ensuite à distinguer deux objets
   proches (par exemple deux cartes graphiques identiques sauf la capacité mémoire) et à remplir
   automatiquement la fiche de vente. Ces facettes sont extraites du champ structuré `details` de la
   source (un dictionnaire de spécifications fourni par le catalogue), à partir d'une liste curée de
   clés discriminantes : couleur, capacité de stockage ou de mémoire, taille d'écran, matière,
   format, style, caractéristique spéciale, compatibilité. On exclut volontairement le bruit
   non-discriminant (poids de l'article, date de première mise en vente, classement des
   meilleures ventes…), inutile pour distinguer deux produits.

   **Limite de cette source et complément depuis le titre.** Le champ `details` du
   catalogue est souvent vide ou incomplet : une carte « RTX 4080 16GB » pouvait ainsi se retrouver
   sans facette « capacité », alors que l'information figure noir sur blanc dans son titre. Cette
   absence cassait à la fois la désambiguïsation entre produits voisins, la complétude de la fiche
   générée et la pertinence de la recherche. Pour y remédier, on **complète à la volée les facettes
   manquantes en les lisant dans le titre**, au moment de présenter les candidats à l'interface
   (fonction `enrich_facets_from_title` dans `src/api/pipeline.py`). Trois facettes sont concernées,
   chacune détectée par une expression régulière volontairement **prudente** pour éviter les
   faux positifs :
   - la **capacité** : seules les unités de stockage explicites sont reconnues (GB, TB, ainsi que
     leurs équivalents français Go et To, normalisés vers GB et TB). Ce filtrage strict écarte les
     pièges fréquents des titres techniques, comme un bus mémoire « 256-Bit », une fréquence
     « 2550 MHz », un type de mémoire « GDDR6X » ou un nombre de pièces « 65 Piece », qui ne sont
     pas des capacités ;
   - la **tension**, sous la forme d'un nombre suivi de « V » (par exemple « 18V » pour une
     visseuse) ;
   - la **puissance**, sous la forme d'un nombre suivi de « W » (par exemple « 1000W » pour une
     alimentation).

   Règle de priorité importante : cette extraction **ne remplace jamais** une facette déjà fournie
   par le catalogue. La valeur issue du champ `details` reste prioritaire ; le titre ne sert qu'à
   **combler les trous**. Le comportement est verrouillé par des tests automatiques
   (`tests/test_facets_from_title.py`) qui vérifient à la fois la bonne extraction, l'absence de
   faux positifs et le respect de la priorité catalogue.

### d) Le découpage anti-fuite

Le découpage en train, validation et test applique toutes les protections décrites au point 1 :

- **Stratifié catégorie par catégorie** : on découpe à l'intérieur de chaque catégorie, ce qui
  garantit que les quatre catégories sont représentées dans la même proportion dans les trois jeux.
- **Mélange déterministe.** Avant de couper, on mélange les lignes au hasard, mais avec une
  « graine » fixée (`seed = 42`). Une graine est un nombre de départ qui rend le tirage
  reproductible : relancer le programme redonne exactement le même découpage, ce qui est essentiel
  pour pouvoir reproduire les résultats.
- **Proportions 70 / 15 / 15** : 70 % des produits pour l'entraînement, 15 % pour la validation,
  15 % pour le test.
- **Regroupement par produit (GroupKFold sur `parent_asin`)** : un produit ne peut pas se retrouver
  à la fois dans le train et dans le test. Ici, comme chaque produit ne correspond déjà qu'à une
  seule ligne, la propriété est immédiate, mais elle est explicitement formalisée pour rester
  robuste si la granularité changeait un jour.

Le découpage produit **deux sorties** :

- Les fiches produits réparties par jeu : `products/train.parquet`, `products/val.parquet`,
  `products/test.parquet`.
- Un **index des avis** léger, qui ne stocke que les colonnes essentielles (`parent_asin`, `asin`,
  `user_id`, `timestamp`, la catégorie d'origine et le jeu d'appartenance). Cet index permettra plus
  tard de retrouver tous les avis d'un produit dans le bon jeu, sans dupliquer le texte volumineux
  des avis (le texte sera rapproché à la demande). Cet index est construit par **une seule jointure
  interne en flux** entre tous les avis et la correspondance produit-jeu. Ce choix est environ
  **dix fois plus rapide** qu'une vérification ligne par ligne d'appartenance à une grande liste,
  qui devrait comparer des dizaines de millions de chaînes de caractères.

### e) Les garde-fous automatiques

Deux mécanismes protègent durablement la qualité :

- **Cinq vérifications de fuite.** Un programme dédié contrôle automatiquement les cinq formes de
  fuite et écrit ses conclusions dans un rapport. Ces contrôles sont rejoués à chaque modification
  du code grâce à l'intégration continue. L'intégration continue (souvent abrégée « CI ») est un
  système qui relance automatiquement une batterie de tests à chaque changement, et qui bloque le
  changement si un test échoue.
- **Des contrats de schéma.** Deux contrats sont définis, l'un pour les fiches produits, l'autre
  pour l'index des avis. Ils déclarent les types attendus, les colonnes qui ne doivent jamais être
  vides, les plages de valeurs autorisées et des descriptions lisibles. Ces contrats sont vérifiés
  à la fois en intégration continue, sur un échantillon de 10 000 lignes (rapide), et en traitement
  complet sur l'ensemble des données, afin de confirmer qu'aucune ligne ne viole les règles. Quand
  une règle est cassée, le message indique précisément la colonne, la ligne et la règle en cause, au
  lieu d'une erreur technique opaque.

---

## 4. Résultats (mesurés, vérifiables)

| Indicateur | Valeur | Ce que cela veut dire |
|---|---|---|
| Produits partagés entre train et test | 0 | aucun produit n'est dans deux jeux à la fois, donc aucune triche n'est possible |
| Produits partagés train/validation, validation/test | 0 | le découpage au niveau produit est parfait |
| Formes de fuite | 4 propres, 1 documentée | la cinquième (le même utilisateur des deux côtés) est sans effet ici, car nos modèles n'utilisent pas l'identité de l'utilisateur comme donnée d'entrée |
| Valeurs manquantes côté avis | 0 % | toutes les colonnes d'avis sont renseignées |
| Couverture produits et avis | environ 99,98 % (environ 80 000 avis orphelins écartés à la jointure) | la quasi-totalité des produits ont leurs métadonnées |
| Découpage | 70 / 15 / 15, stratifié, graine 42 | les proportions des catégories sont respectées dans chaque jeu |
| Tests automatiques | tous au vert | quatre suites passent : vérification anti-fuite, contrats de schéma, invariants du nettoyage, invariants de l'audit |

> Drapeau slides, chiffres clés à afficher : « 0 produit partagé entre train et test (découpage par
> groupe) », « environ 99,98 % de couverture des métadonnées », « 0 % de valeurs manquantes sur les
> avis », « découpage 70 / 15 / 15 stratifié, graine 42 », « 5 formes de fuite vérifiées
> automatiquement ».
>
> Drapeau slides, captures à montrer : le tableau des « 0 » de produits partagés issu du rapport
> anti-fuite, et un graphique de distribution issu des figures d'audit.

---

## 5. Critique (état de l'art comparé à notre travail)

**Points solides :**

- Découpage effectué avant le pré-traitement, et statistiques calculées sur le seul jeu
  d'entraînement : aucune fuite par construction.
- Regroupement par produit combiné à la stratification par catégorie : c'est la méthode de
  référence pour ce type de données.
- Contrats de schéma déclaratifs, identiques en intégration continue (sur échantillon) et en
  traitement complet (sur l'ensemble).
- Audit chiffré en amont et tests automatiques en aval : l'ensemble est reproductible.
- Ingénierie efficace : un index des avis léger et une jointure en flux, environ dix fois plus
  rapide que la solution naïve.

**Limites assumées :**

- **Amazon n'est pas Rakuten.** C'est un jeu de données de substitution pour itérer ;
  l'architecture est transposable, mais les chiffres exacts différeraient sur de vraies données
  Rakuten.
- **Données en anglais.** Les requêtes en français devront être traduites avant la recherche ; ce
  point est traité au niveau du composant qui transforme texte et images en vecteurs numériques.
- **Fuite « utilisateur » présente mais neutre.** Nous n'avons pas fait de découpage par
  utilisateur, car ce serait seulement nécessaire pour un futur modèle qui apprendrait les
  préférences personnelles des clients. En l'état, nos modèles n'utilisent pas l'identité de
  l'utilisateur, donc cette fuite est sans conséquence.
- **Pas de surveillance continue de la qualité.** Nous validons les données au moment de leur
  construction, pas en flux permanent. C'est un axe d'amélioration identifié.

---

## 6. Références

- scikit-learn, *Common pitfalls and recommended practices* : https://scikit-learn.org/stable/common_pitfalls.html
- MachineLearningMastery, *Avoid data leakage in data preparation* : https://machinelearningmastery.com/data-preparation-without-data-leakage/
- CrowdStrike, *ML evaluation using data splitting* : https://www.crowdstrike.com/en-us/blog/machine-learning-evaluation-using-data-splitting/
- GeeksforGeeks, *Train-test split based on group ID (GroupKFold)* : https://www.geeksforgeeks.org/machine-learning/how-to-generate-a-train-test-split-based-on-a-group-id/
- endjin, *Pandera vs Great Expectations* : https://endjin.com/blog/a-look-into-pandera-and-great-expectations-for-data-validation

---

### En une phrase (pour la défense)

*« Nos données sont auditées par quatre programmes (en interrogeant d'abord les métadonnées),
nettoyées en six étapes, puis découpées au niveau du produit avec regroupement par identifiant et
stratification par catégorie : zéro produit partagé entre entraînement et test (vérifié), toutes les
statistiques calculées sur le seul jeu d'entraînement, et des contrats de schéma qui bloquent toute
donnée hors règle, le tout rejoué automatiquement à chaque changement de code. »*
