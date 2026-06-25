# 07 - Suivi des entraînements (MLflow)

> L'idée centrale : enregistrer chaque entraînement de modèle (ses réglages, ses scores, les
> fichiers produits, et la version exacte du code utilisé) pour pouvoir comparer les essais,
> reproduire un bon résultat plus tard, et expliquer comment chaque modèle a été obtenu. Sans
> cette mémoire écrite, le travail n'est ni comparable ni reproductible.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre à partir de zéro

Quand on entraîne un modèle d'intelligence artificielle, on essaie beaucoup de combinaisons de
réglages. À chaque essai, on obtient des scores. Très vite, on ne sait plus quel essai a donné
quoi, ni avec quels réglages. C'est le problème classique : « c'était quels paramètres déjà,
pour ce résultat que je trouvais bon ? »

MLflow est l'outil qui résout ce problème. C'est un carnet de laboratoire automatique pour
l'intelligence artificielle (MLflow est une bibliothèque logicielle libre et gratuite, très
répandue dans le métier). Chaque entraînement devient ce qu'on appelle un run, c'est-à-dire une
fiche d'essai datée qui enregistre toute seule :

- les paramètres, c'est-à-dire les réglages choisis avant l'entraînement (par exemple le nombre
  de voisins examinés, ou la graine aléatoire qui fixe le hasard pour que l'essai soit rejouable
  à l'identique) ;
- les métriques, c'est-à-dire les scores obtenus après l'entraînement (par exemple le F1, un
  score de qualité de classification qui va de 0 à 1, ou le temps qu'a pris l'entraînement) ;
- les artefacts, c'est-à-dire les fichiers produits (le modèle entraîné lui-même, des graphiques) ;
- le contexte, c'est-à-dire l'identité exacte du code utilisé. On enregistre notamment le
  « commit git », un identifiant unique qui désigne l'état précis du code à ce moment-là
  (git est l'outil qui garde l'historique de toutes les versions du code d'un projet).

Grâce à cela, on peut comparer deux essais de façon fiable, et retrouver trois mois plus tard les
réglages exacts d'un bon résultat pour le reproduire.

### Pour le lecteur technique

MLflow ajoute deux briques au-delà du simple suivi des essais.

Le Model Registry est un catalogue qui versionne les modèles validés (version 1, version 2, et
ainsi de suite) et relie chaque version au run qui l'a produite. On obtient une traçabilité
complète : à partir d'un modèle en service, on remonte aux données et aux réglages exacts qui
l'ont généré.

Un alias est une étiquette mobile que l'on pose sur une version. L'alias `@Production` désigne le
modèle réellement utilisé par l'application. Pour changer de modèle servi, il suffit de déplacer
cette étiquette d'une version à une autre, sans modifier le code de l'application. C'est rapide
et réversible.

Enfin, le stockage de MLflow est découplé en deux parties. D'un côté le « tracking store », qui
garde les réglages et les scores. De l'autre l'« artifact store », qui garde les gros fichiers
(les modèles). Chacune peut être locale (une simple base de données SQLite et un dossier sur le
disque) ou répartie sur des serveurs (une base PostgreSQL pour les scores, et un stockage de type
objet comme MinIO pour les fichiers).

---

## 2. Les bonnes pratiques du métier

Les usages reconnus dans le domaine sont les suivants.

- Enregistrer tout ce qui est utile, pas seulement le score final : aussi la version du code
  (commit git), la version des données, la graine aléatoire et l'environnement logiciel.
- Donner des noms cohérents et stables aux expériences et aux métriques, et pouvoir interroger
  les essais par programme (et non seulement à l'œil dans une interface).
- Tenir un catalogue de modèles (registry) : un nom unique, des versions numérotées et liées à
  leur run, et un cycle de vie clair (modèle candidat, puis modèle en production, puis archivé),
  géré par des étiquettes mobiles.
- Viser la reproductibilité : un run doit contenir tout ce qu'il faut pour rejouer l'essai à
  l'identique.

---

## 3. Notre implémentation (ce que nous avons réellement fait)

Tout le suivi est centralisé dans un seul fichier de code, `src/mlops/mlflow_utils.py`. Voici
précisément son comportement.

**Une expérience unique.** Tous les essais sont rangés dans une seule expérience nommée
`rakuten-mvp`. La fonction de configuration `setup_mlflow` est idempotente : on peut l'appeler
autant de fois qu'on veut, elle ne crée l'expérience qu'une seule fois et ne casse rien si elle
existe déjà.

**Une adresse de stockage paramétrable.** L'endroit où MLflow écrit est choisi automatiquement.
Si une variable d'environnement nommée `MLFLOW_TRACKING_URI` est définie, on l'utilise (cas du
déploiement avec conteneurs, où elle pointe vers un serveur appuyé sur PostgreSQL pour les scores
et MinIO pour les fichiers). Sinon, on bascule sur un fonctionnement local simple : une base de
données SQLite dans un fichier nommé `mlflow.db`, et un dossier `mlartifacts` pour les fichiers.
Le code détecte tout seul si l'adresse est un serveur web (elle commence par `http://` ou
`https://`) ; dans ce cas il ne force pas d'emplacement local pour les fichiers et laisse le
serveur décider où les ranger.

**La version exacte du code à chaque essai.** Une petite fonction appelée `git_commit` lit
l'identifiant court du code en cours (le SHA court du commit git) et l'enregistre comme étiquette
sur le run. Si git n'est pas disponible, elle inscrit `unknown` plutôt que de faire échouer
l'entraînement. C'est ce qui garantit qu'on sait toujours quel code a produit quel résultat.

**Des noms de scores cohérents et comparables.** Une fonction `_flatten_metrics` met à plat la
structure des résultats. Les scores sont organisés par jeu de données : le jeu de validation
(`val`, utilisé pour régler le modèle) et le jeu de test (`test`, utilisé pour mesurer la qualité
finale sur des données jamais vues). La fonction transforme par exemple un score `f1_weighted`
mesuré sur le test en une métrique nommée `test_f1_weighted`. Tous les essais utilisent ainsi les
mêmes noms, ce qui rend les comparaisons directes.

**Un enregistrement complet par entraînement.** La fonction principale `log_training_run` ouvre
un run et y inscrit : les étiquettes (l'identifiant du modèle, le commit git), les paramètres
convertis en texte, les métriques mises à plat, le nombre d'exemples d'entraînement et la durée
de l'entraînement quand ils sont fournis. Pour les modèles de type scikit-learn (une bibliothèque
standard d'apprentissage automatique en Python), elle enregistre aussi le modèle lui-même
accompagné de sa « signature », c'est-à-dire la description du format d'entrée et de sortie
attendu. Cette signature est déduite d'un petit échantillon d'exemples. Si quelque chose échoue
lors de l'écriture du modèle (par exemple un stockage non accessible en écriture), le code ne
plante pas : les paramètres et les scores restent enregistrés, et le run est marqué d'une
étiquette `artifact_logging = deferred` pour signaler que le fichier modèle reste à pousser plus
tard. C'est une dégradation propre, et non un échec brutal.

**Un catalogue de modèles avec étiquette de production.** Quand on le demande, la fonction inscrit
le modèle au catalogue sous le nom `rakuten-classifier` et peut poser l'étiquette `@Production`
sur la version concernée. La version réellement créée par l'appel est lue directement dans la
réponse de MLflow (et non devinée comme « la plus grande version »), ce qui évite les erreurs
quand plusieurs enregistrements se croisent.

**Un garde-fou avant de promouvoir un modèle.** Un second fichier de code, `src/mlops/promote_gate.py`,
décide de manière contrôlée quel modèle mérite l'étiquette `@Production`. Il compare le dernier
modèle enregistré (le « challenger ») au modèle actuellement en production (le « champion ») sur
le score `test_f1_weighted`. Il ne déplace l'étiquette que si le challenger fait au moins aussi
bien que le champion plus une petite marge fixée à 0,001. Cette marge évite de changer de modèle
pour une différence due au hasard. Le garde-fou gère aussi les cas particuliers : s'il n'existe
aucune version, il ne fait rien ; si le dernier modèle est déjà le champion, il s'arrête sans
rien déplacer. À chaque fois, il inscrit sa décision dans les étiquettes de la version
(promu, ou conservé). C'est ce mécanisme qui empêche une régression silencieuse, c'est-à-dire le
remplacement involontaire d'un bon modèle par un moins bon.

---

## 4. Résultats (mesurés et vérifiables)

- **13 runs** enregistrés dans l'expérience `rakuten-mvp`. Ils couvrent les six modèles de
  classification comparés dans le projet (notés knn-faiss à fusion), le modèle de prédiction de prix, et
  quelques ré-essais. Chacun porte ses métriques réelles (F1 pondéré, F1 macro, exactitude, ECE
  qui mesure la fiabilité des probabilités annoncées, temps) et l'étiquette du commit git.
- **Catalogue `rakuten-classifier`** alimenté de la version 1 à la version 5, avec l'étiquette
  `@Production` qui désigne le modèle servi. La résolution de l'adresse
  `models:/rakuten-classifier@Production` (la formule qui demande à MLflow « donne-moi le modèle
  marqué Production ») a été vérifiée et fonctionne.
- **Les deux stockages réconciliés.** Le serveur tournant dans un conteneur (sur le port 5000,
  appuyé sur PostgreSQL et MinIO) était bloqué sur une ancienne version 2 de MLflow alors que le
  reste du projet utilisait la version 3. Il a été aligné sur la version 3, et il contient
  désormais des runs réels, le modèle enregistré au catalogue, et l'étiquette `@Production` (le
  fichier du modèle étant rangé dans MinIO). En parallèle, le stockage local dans `mlflow.db`
  reste la référence complète du projet.

> Drapeau slide. Chiffres à afficher : « 13 entraînements tracés (réglages + scores + commit
> git) », « 6 modèles comparés dans MLflow », « modèle `@Production` = tfidf-svm ». Capture d'écran à
> montrer : l'interface MLflow (lancée par la commande `mlflow ui --backend-store-uri
> sqlite:///mlflow.db`) avec la liste des runs triable par F1, et la page des modèles affichant
> l'étiquette `@Production`. C'est la preuve visuelle que les entraînements sont bien suivis.

---

## 5. Regard critique (bonnes pratiques face à notre travail)

**Points solides.**

- Tous les entraînements sont tracés, avec des scores riches, comparables, et accompagnés du
  commit git, donc reproductibles.
- Le catalogue de modèles et l'étiquette `@Production` donnent une traçabilité complète entre
  chaque essai et le modèle qui en découle, et permettent de changer de modèle servi en déplaçant
  une simple étiquette.
- L'adresse de stockage est paramétrable : le même code fonctionne en local (base SQLite) comme
  sur serveur (PostgreSQL et MinIO).
- Les défauts repérés lors de l'audit interne ont été corrigés (alignement sur la version 3 de
  MLflow, et remplissage du catalogue côté serveur conteneur).

**Limites assumées.**

- L'étiquette `@Production` a été historiquement fragile : elle a parfois disparu lors de
  ré-entraînements ou de changements de stockage. Elle a été reposée, et surtout protégée par un
  test automatique. Ce test vérifie que, même en l'absence d'étiquette, le garde-fou de promotion
  finit par désigner un modèle gagnant. Autrement dit, le système se répare tout seul et
  l'application ne se retrouve jamais sans modèle à servir.
- La version des données n'est pas encore enregistrée systématiquement comme étiquette. Le commit
  git du code l'est, mais ajouter une empreinte numérique du jeu de données serait un plus pour
  une reproductibilité totale.
- L'écriture automatique du fichier modèle dans le catalogue du serveur n'est pas encore intégrée
  à la chaîne de ré-entraînement complète. Lors de la mise en place, l'enregistrement au catalogue
  a été fait à partir du fichier modèle local. L'objectif suivant est que chaque futur
  ré-entraînement alimente automatiquement le catalogue côté serveur.

---

## 6. Références

- MLflow, documentation officielle, suivi des expériences : https://mlflow.org/docs/latest/ml/tracking/
- MLflow, documentation officielle, catalogue de modèles : https://mlflow.org/docs/latest/ml/model-registry/
- MLflow, gestion du cycle de vie d'un modèle expliquée aux ingénieurs : https://mlflow.org/articles/ml-lifecycle-management-explained-for-engineers/
- D. Patil, Medium, prise en main du suivi et du catalogue MLflow : https://dspatil.medium.com/demystifying-mlflow-a-hands-on-guide-to-experiment-tracking-and-model-registry-d99b6bfd1bda

---

### En une phrase (pour la soutenance)

*Chaque entraînement est tracé dans MLflow (13 runs, 6 modèles comparés, réglages et scores plus
le commit git pour la reproductibilité), avec un catalogue de modèles et l'étiquette `@Production`
qui désigne le modèle réellement servi. L'adresse de stockage est paramétrable (base SQLite en
local ou serveur PostgreSQL et MinIO), et j'ai aligné le serveur conteneur sur la version 3 de
MLflow pour qu'il porte lui aussi le catalogue.*
