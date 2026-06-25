# 08 - Registre de modèles et champion/challenger

> Comment on choisit **le** modèle réellement utilisé en production, et comment on ne le remplace
> **que** s'il est **prouvé meilleur**, de façon automatique, sans jamais casser ce qui fonctionne déjà.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre (en partant de zéro)

Quand on entraîne un programme d'intelligence artificielle (un « modèle »), on en produit souvent
plusieurs au fil du temps : une première version, puis une deuxième améliorée, et ainsi de suite.
Il faut donc un endroit pour les ranger et savoir lequel sert vraiment aux utilisateurs.

Le **registre de modèles** (en anglais « model registry ») est cette étagère centrale. C'est un
catalogue qui stocke chaque modèle entraîné. Chaque modèle y porte un nom, des **versions**
numérotées (version 1, version 2, etc.), et une **étiquette** qui indique lequel est en service.
Chez nous, cette étiquette s'appelle **`@Production`** : le modèle qui la porte est celui que les
utilisateurs interrogent réellement.

Le schéma **champion / challenger** est une façon de gérer le remplacement d'un modèle sans risque :

- le **champion** est le modèle actuellement en production (celui qui travaille pour de vrai),
- le **challenger** est un nouveau modèle candidat qu'on vient d'entraîner,
- on compare les deux **sur exactement les mêmes données de test**,
- on **promeut** le challenger (on lui donne l'étiquette `@Production`) **seulement** s'il fait
  **clairement mieux** que le champion.

L'idée est simple : on ne déploie jamais un nouveau modèle « à l'aveugle ». Tant qu'on n'a pas la
preuve chiffrée qu'il est meilleur, on garde l'ancien. Cela évite de dégrader le service en mettant
en production un modèle moins bon que celui qu'on avait.

Un mot sur deux outils cités plus loin :

- **MLflow** est une bibliothèque qui sert à la fois de carnet de bord (elle enregistre les scores
  de chaque entraînement) et de registre de modèles (l'étagère décrite ci-dessus).
- **BentoML** est un outil qui transforme un modèle en service accessible par le réseau, pour que
  d'autres programmes puissent lui envoyer des requêtes.

### Pour l'expert

- La promotion se fait **par alias** et non par copie de fichier. Le code qui sert le modèle pointe
  toujours vers l'alias `@Production`. Pour basculer la production sur un nouveau modèle, on déplace
  simplement ce pointeur. Le **retour arrière** (rollback) est donc trivial : il suffit de re-pointer
  l'alias vers la version précédente.
- La comparaison entre champion et challenger peut être **hors ligne** (sur un jeu de test mis de côté,
  via le suivi des scores) ou **en ligne** (test A/B, envoi progressif d'une part du trafic réel au
  nouveau modèle). Nous faisons une comparaison **hors ligne** : c'est l'approche la plus simple et la
  plus sûre pour un produit minimal viable.

---

## 2. État de l'art

Voici les pratiques recommandées par l'industrie pour ce composant :

- **Champion en production, challenger candidat**, tous deux testés sur le même jeu de données mis de
  côté ; promotion uniquement si le challenger est meilleur. La bascule se gère par des alias dans le
  registre, ce qui rend le changement instantané et réversible.
- **Une barrière de promotion automatisée** (en anglais « promotion gate ») : on vérifie d'abord, par
  un calcul, que le candidat fait *au moins aussi bien* que le modèle en place, avant de le promouvoir.
  Une étape d'approbation humaine peut être ajoutée par-dessus.
- **Toujours prévoir un retour arrière**, et éviter d'envoyer 100 % du trafic vers le nouveau modèle
  d'un seul coup. On préfère un envoi progressif ou des interrupteurs de fonctionnalité (feature flags).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

Le tableau ci-dessous liste les fichiers de code concernés et leur rôle.

| Brique | Fichier | Rôle |
|---|---|---|
| Barrière de promotion | `src/mlops/promote_gate.py` | compare le challenger au champion et déplace l'étiquette `@Production` **seulement s'il est meilleur** |
| Import pour servir | `src/serving/import_model.py` | charge le modèle pointé par `models:/rakuten-category-classifier@Production` pour le mettre en service (via BentoML) |
| Service de mise en ligne | `src/serving/service.py` | expose le modèle au réseau (interface de programmation, plus des indicateurs de fonctionnement lisibles par l'outil de surveillance Prometheus) |
| Tests | `test_promote_gate.py`, `test_serving.py` | vérifient la logique de décision sur une base de données temporaire jetable |

### La logique de décision, étape par étape

Le cœur du composant est la fonction `decide_and_promote(metric, epsilon)` du fichier
`promote_gate.py`. Elle prend deux réglages : `metric`, le score de référence à comparer, et
`epsilon`, la marge minimale à dépasser pour accepter un remplacement. Voici ce qu'elle fait :

1. Elle lit la liste de toutes les versions du modèle nommé `rakuten-category-classifier` dans le registre.
   S'il n'y a aucune version, elle s'arrête et renvoie la décision `no_versions` (« rien à promouvoir »).
2. Elle identifie le **challenger** : la version la plus récente enregistrée (le plus grand numéro).
3. Elle identifie le **champion** : la version qui porte l'étiquette `@Production`. S'il n'y a pas
   encore de modèle en production, le champion est considéré comme inexistant.
4. **Cas particulier où il n'y a pas vraiment de nouveau candidat** : si la version la plus récente
   est exactement celle qui est déjà en production, c'est qu'aucun nouveau modèle n'a été créé. La
   fonction s'arrête sans rien toucher et renvoie la décision `skipped_no_challenger`. La production
   reste intacte.
5. Sinon, elle récupère le score de référence du challenger et celui du champion. Le score utilisé est
   le **F1 pondéré** sur le jeu de test, repéré dans le code par la clé `test_f1_weighted`. Le score
   F1 est une note de qualité de classement comprise entre 0 et 1 : plus il est proche de 1, mieux le
   modèle range les produits dans la bonne catégorie. Si un score est introuvable, il vaut -1 par
   défaut (ce qui garantit qu'un modèle sans score mesuré ne sera jamais promu).
6. **La règle de décision** : la fonction promeut le challenger **seulement si**
   `score_challenger >= score_champion + epsilon`. La valeur de `epsilon` est fixée à **0,001** dans
   le code. Cette petite marge évite de changer de modèle pour une différence insignifiante, qui ne
   serait que du bruit de mesure. Concrètement, un challenger doit faire au moins 0,001 point de F1 de
   mieux que le champion pour mériter sa place.
7. **Si la règle est satisfaite** : la fonction déplace l'étiquette `@Production` vers la nouvelle
   version, et marque cette version avec des annotations (le score du champion qu'elle remplace, et la
   mention `promoted`). La décision renvoyée est `promoted`.
8. **Si la règle n'est pas satisfaite** : la fonction ne touche pas à l'étiquette. Elle marque la
   nouvelle version comme `kept` (l'ancien champion est conservé) et renvoie la décision `kept`.

Quand on lance le programme en ligne de commande, il fait une chose de plus : il essaie d'envoyer le
résultat de la décision vers l'outil de surveillance (une « passerelle de poussée » nommée
Pushgateway, qui alimente des tableaux de bord). Si la bibliothèque de surveillance n'est pas
installée, l'envoi est simplement ignoré sans faire planter le programme. Le résultat final est
affiché au format JSON (un format texte structuré facile à relire par un autre programme).

Il s'agit d'une **comparaison hors ligne** : on compare les deux modèles sur le jeu de test, à partir
des scores enregistrés par MLflow. C'est la forme la plus sûre du schéma champion/challenger. Le code
de mise en ligne (`import_model.py`) charge **toujours** le modèle pointé par `@Production` : la
production suit donc automatiquement la dernière promotion, sans intervention manuelle.

---

## 4. Résultats mesurés, et la preuve que la barrière fonctionne

- Dans le registre du modèle `rakuten-category-classifier`, on compte **cinq versions** au total (de la
  version 1 à la version 5). L'étiquette **`@Production` pointe vers la version 2**, qui correspond au
  meilleur modèle obtenu (appelé en interne « tfidf-svm »).
- Les **ré-entraînements automatiques**, déclenchés par l'orchestrateur de tâches (Airflow, l'outil
  qui planifie et enchaîne les traitements), ont **réellement produit** les versions 3, 4 et 5.
- **La preuve que la barrière protège la production** : les versions 3, 4 et 5 sont d'autres modèles
  (de type SVM et MLP, deux familles d'algorithmes de classement) dont les scores F1 valent environ
  0,931 et 0,949. Ces scores sont **inférieurs** à celui du champion (version 2, score F1 d'environ
  0,950). La barrière a donc **refusé** de les promouvoir, et l'étiquette `@Production` est restée sur
  la version 2. Une barrière qui ne promeut pas un candidat plus faible, c'est exactement le
  comportement attendu.
- **Le registre est aussi rempli dans la version conteneurisée** : après mise au même niveau de
  MLflow (version 3.x), le registre est également peuplé dans le serveur exécuté en conteneur, sur le
  port réseau 5000. Un conteneur est un environnement logiciel isolé et reproductible.

> [SLIDE] **Chiffres à montrer** : « registre de 5 versions (v1 à v5) », « `@Production` = tfidf-svm (la
> version 2) », « les ré-entraînements ont créé les versions 3 à 5, mais la barrière a **refusé** les
> moins bonnes (0,931 et 0,949 contre 0,950) : la production a été protégée ».
> [CAPTURE] La page *Models* de MLflow (liste des versions et de l'alias), accompagnée d'un extrait du
> journal de `promote_gate` montrant les décisions (`kept` quand on refuse, `promoted` quand on accepte).

---

## 5. Critique (état de l'art comparé à notre travail)

**Points solides :**

- Une véritable barrière champion/challenger, fondée sur un alias et un seuil de marge `epsilon` :
  c'est conforme au schéma standard de l'industrie.
- Une comparaison hors ligne sur un jeu de test mis de côté, via MLflow : c'est la bonne approche,
  simple et sûre.
- Une preuve par les faits : de vrais candidats plus faibles ont été refusés à juste titre, sans
  intervention humaine.
- Un import pour la mise en ligne basé sur l'alias : la production lit toujours `@Production`, donc le
  retour arrière reste trivial.

**Limites assumées :**

- **Pas de comparaison en ligne** (pas de test A/B ni d'envoi progressif d'une part du trafic réel).
  Nous restons en comparaison hors ligne. C'est suffisant pour un produit minimal viable, mais le test
  A/B serait l'étape suivante pour une vraie mise en production à grande échelle.
- **Pas de retour arrière automatisé formalisé** : on re-pointe l'étiquette à la main. L'opération est
  triviale, mais elle reste manuelle.
- **L'étiquette `@Production` s'est révélée fragile** : elle a « disparu » à plusieurs reprises au
  cours du développement. Il reste à ajouter un test de garde qui vérifie en permanence sa présence.
- **Pas d'étape d'approbation humaine** dans la barrière : la promotion est entièrement automatique,
  décidée sur le seul score chiffré.

---

## 6. Références

- DataRobot, *Introducing MLOps champion/challenger models* : https://www.datarobot.com/blog/introducing-mlops-champion-challenger-models/
- Snowflake, *Automated retraining & champion/challenger deployment* : https://www.snowflake.com/en/developers/guides/ml-champion-challenger-model-deployment/
- Databricks, *MLOps workflows* : https://docs.databricks.com/aws/en/machine-learning/mlops/mlops-workflow
- MLflow, *Model Registry* : https://mlflow.org/docs/latest/ml/model-registry/

---

### En une phrase (pour la défense)

*Le modèle réellement servi porte l'étiquette `@Production` dans le registre. Une barrière
champion/challenger (règle : score du challenger supérieur ou égal au score du champion plus une marge
de 0,001, comparaison hors ligne sur le jeu de test) ne le remplace que si un candidat est mesurablement
meilleur. Preuve que cela fonctionne : les ré-entraînements ont créé les versions 3 à 5, mais comme
elles étaient moins bonnes que le champion (la version 2), la barrière a refusé de les promouvoir, et la
production a été protégée automatiquement.*
