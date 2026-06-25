# Documentation du projet

Toute la documentation du projet tient dans ce seul dossier. Ce fichier est le sommaire : il explique, en mots simples, ce que contient chacun des autres documents, dans quel ordre les lire, et à quoi ils servent. Vous pouvez tout comprendre en partant d'ici, sans aucune connaissance technique préalable.

## En une phrase : à quoi sert le projet

Le projet est un assistant qui aide un particulier à revendre un objet d'occasion (un téléphone, une console, un outil). À partir d'une simple photo, le système retrouve l'objet dans un grand catalogue de produits réels, puis rédige tout seul l'annonce de vente : la catégorie, le titre, les caractéristiques, une description honnête et un prix conseillé. La personne n'a plus qu'à vérifier et publier.

L'idée directrice est simple : on ne demande jamais à une intelligence artificielle de deviner quel est le produit. On le retrouve d'abord dans un catalogue de produits réels, puis une intelligence artificielle rédige l'annonce à partir de ces faits vérifiés. Ce principe, appelé « ancré » (en anglais « grounded »), empêche le système d'inventer des informations.

## Par où commencer

Lisez ces trois documents dans l'ordre, ils donnent une vision complète sans entrer dans le détail technique.

1. Le document `PROJECT.md` présente le cadrage du produit : à quel besoin il répond, sur quelles hypothèses il repose, ce qu'il doit faire, et ce qu'il a volontairement choisi de ne pas faire.
2. Le document `00_vue_ensemble.md` présente le système dans son entier, du premier clic du vendeur jusqu'à l'annonce finale. C'est le plan complet du fonctionnement, étape par étape.
3. Ensuite, vous pouvez lire les documents par thème (la liste se trouve plus bas). Chacun se lit indépendamment des autres.

Si un mot technique vous bloque dans n'importe quel document, le fichier `GLOSSAIRE.md` définit chaque terme du projet en une seule ligne.

## Comment chaque document par thème est construit

Tous les documents thématiques suivent la même trame, pensée pour deux types de lecteurs : un débutant suit le raisonnement du début à la fin, un spécialiste y trouve les réglages exacts et les justifications. La trame est la suivante :

1. La technologie expliquée à partir de zéro, et le rôle qu'elle joue dans le projet.
2. L'état de l'art, c'est-à-dire ce que font habituellement les meilleures équipes pour ce besoin.
3. Notre implémentation réelle, avec les fichiers concernés et les réglages effectivement utilisés.
4. Les résultats que nous avons mesurés, chiffres à l'appui.
5. La critique honnête : les limites connues et les choix assumés.
6. Les références.

## Sommaire des documents par thème

Chaque ligne ci-dessous décrit en clair ce que vous trouverez dans le document correspondant.

- `00_vue_ensemble.md` : le système entier en un seul coup d'œil. Le trajet complet d'une photo jusqu'à l'annonce, le principe « ancré » qui empêche d'inventer, et la façon dont le prix est calculé. C'est la lecture d'introduction la plus importante.

- `01_data_engineering.md` : la préparation des données, c'est-à-dire tout ce qui se fait avant d'entraîner le moindre modèle. On récupère les données brutes, on les nettoie, on les vérifie, puis on les découpe en deux paquets séparés (un pour apprendre, un pour évaluer) en veillant à ce qu'aucune information du paquet d'évaluation ne se retrouve dans celui d'apprentissage. Ce dernier point, appelé fuite de données, gonflerait artificiellement les scores : ce document explique comment on l'évite.

- `02_embeddings.md` : la transformation d'un texte ou d'une image en une liste de nombres (un « embedding ») qui résume son sens, et non ses mots exacts. C'est la fondation de toute la recherche de produits : deux objets au sens proche obtiennent des listes de nombres proches, ce qui permet de les comparer automatiquement.

- `03_classification_benchmark.md` : l'entraînement de plusieurs modèles classiques pour ranger un produit dans la bonne catégorie, et leur comparaison équitable sur les mêmes données et les mêmes critères afin de choisir le meilleur. On y trouve la fiche détaillée de chaque modèle et les scores obtenus.

- `04_retrieval.md` : le moteur central qui retrouve, parmi environ 3,16 millions de produits du catalogue, ceux qui ressemblent le plus à la photo et à la description du vendeur. On explique l'index de recherche rapide utilisé, la fusion de plusieurs classements pour de meilleurs résultats, la détection des produits absents du catalogue (qu'on signale au lieu d'inventer), et le mode « Akinator » qui pose la bonne question quand deux produits se ressemblent trop.

- `05_vlm_llm_grounded.md` : les deux intelligences artificielles génératives du projet. La première « voit » : elle lit la photo et en déduit le produit probable. La seconde « rédige » : elle écrit l'annonce. Les deux sont volontairement bridées par des faits réels pour les empêcher d'inventer. C'est le garde-fou anti-invention, présent du début à la fin du traitement.

- `06_pricing.md` : le calcul du prix conseillé. Plutôt qu'un chiffre opaque sorti d'une boîte noire, le système propose un prix accompagné d'une fourchette, d'un niveau de confiance et d'une explication lisible, pour que le vendeur comprenne pourquoi ce prix lui est proposé.

- `07_mlflow_suivi.md` : le carnet de bord des entraînements. Chaque fois qu'on entraîne un modèle, on enregistre automatiquement ses réglages, ses scores, les fichiers produits et la version exacte du code utilisé. Sans cette mémoire écrite, impossible de comparer les essais ni de reproduire un bon résultat plus tard.

- `08_registry_champion_challenger.md` : l'étagère qui range les modèles et marque clairement celui qui est en service. On y décrit la règle qui veut qu'un modèle en place ne soit remplacé par un nouveau candidat que si ce dernier est prouvé meilleur, de façon automatique et sans jamais casser ce qui fonctionne déjà.

- `09_airflow_retrain.md` : le « robot » qui ré-entraîne le modèle tout seul à intervalle régulier, vérifie qu'il est bon, et ne le met en service que s'il mérite de remplacer l'ancien. C'est la boucle de vie complète du modèle, du nouvel apprentissage jusqu'à la mise en production, sans intervention humaine.

- `10_drift_evidently.md` : la surveillance du vieillissement. On vérifie en continu si les données qui arrivent aujourd'hui ressemblent encore à celles sur lesquelles le modèle a appris. Quand elles changent trop, le modèle devient moins juste sans qu'aucune erreur ne saute aux yeux : détecter ce changement permet de relancer un entraînement au bon moment.

- `11_observabilite.md` : la capacité de voir si l'application va bien une fois en service. Combien de requêtes elle reçoit, à quelle vitesse elle répond, combien d'erreurs surviennent, et comment retracer pas à pas ce qui s'est passé pour une requête donnée grâce à un identifiant unique attaché à chacune.

- `12_infra.md` : l'emballage technique de l'application pour qu'elle tourne partout de façon identique, l'organisation de ses nombreux services, et les moyens de la déployer puis de l'agrandir quand le nombre d'utilisateurs augmente.

- `13_cicd_securite.md` : l'automatisation des contrôles et la sécurité. À chaque modification du code, un programme rejoue automatiquement les vérifications de qualité, les tests, l'audit des dépendances et la reconstruction de l'application. Le document couvre aussi la protection des secrets, l'authentification et la vérification des fichiers envoyés par les utilisateurs.

- `14_api_orchestration.md` : le chef d'orchestre du système. C'est la couche qui reçoit les demandes, charge les modèles, enchaîne dans le bon ordre la recherche du produit, la lecture de la photo, la levée de doute, le calcul du prix et la rédaction, puis renvoie une réponse propre. Sans elle, les briques d'intelligence artificielle resteraient des fichiers isolés.

- `15_frontend_ux.md` : l'interface que le vendeur utilise vraiment dans son navigateur, pour photographier, vérifier et publier. C'est l'endroit où tout le traitement automatique devient un produit réellement utilisable, et où l'ergonomie décide si le vendeur va jusqu'au bout.

- `16_explainability.md` : la capacité d'expliquer pourquoi le système décide ce qu'il décide. Pourquoi cette catégorie a été choisie, pourquoi ces produits sont jugés semblables, et la fiche d'identité de chaque modèle. Un système incapable de se justifier ne serait pas acceptable face à un particulier.

- `17_etude_chaine_valeur_photo.md` : l'étude scientifique qui prouve, chiffres et tests statistiques à l'appui, la valeur de chaque maillon de la chaîne. Elle démontre sur 93 annonces réelles que la photo est le signal décisif (mieux que le texte du vendeur, et plusieurs photos mieux qu'une seule), que les informations saisies par le vendeur n'ajoutent rien une fois les photos disponibles, et quel modèle de lecture d'image a été retenu après comparaison. C'est la pièce maîtresse de la démonstration.

Les quatre derniers documents (numéros 14 à 16, plus la vue d'ensemble) décrivent les couches que voit l'utilisateur final : l'interface qui relie toutes les briques entre elles, l'écran du vendeur, et les explications qui rendent les décisions compréhensibles.

## Documents de cadrage et de traçabilité

Ces documents servent à vérifier que le projet construit bien le bon produit et couvre bien tout ce qui est attendu.

- `PROJECT.md` : le cadrage du produit. Le besoin auquel il répond, les hypothèses de départ, la liste des fonctions attendues, et le périmètre volontairement laissé de côté.

- `exigences_fonctionnelles.md` : un tableau qui reprend chaque fonction attendue du produit et indique, pour chacune, ce qui a réellement été livré et l'écart éventuel avec l'objectif. Il répond à la question : « construit-on le bon produit ? »

- `exigences_coverage.md` : un tableau qui croise les attentes du cahier des charges avec ce qui se trouve réellement dans le code, fichier par fichier. Il répond à la question : « le projet couvre-t-il tout ce qui est demandé ? »

- `GLOSSAIRE.md` : tout le vocabulaire technique du projet, chaque terme expliqué en une seule ligne, pour lire n'importe quel document sans bloquer sur le jargon.

- `SOUTENANCE_PLAN.md` : le plan de présentation orale du projet, organisé en blocs minutés, avec pour chaque diapositive le message principal, le visuel à montrer et le chiffre clé à afficher.

## La phrase à retenir

Notre système ne devine pas un produit, il le retrouve dans un catalogue réel puis rédige l'annonce à partir de ces faits vérifiés. La photo suffit à démarrer, l'humain valide toujours le résultat, le prix s'explique en clair, et toute la chaîne, des données propres jusqu'à la surveillance en service, est mesurée et reproductible.
