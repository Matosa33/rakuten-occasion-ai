# 10. Détection de dérive des données avec Evidently

> Le but de cette brique est de surveiller si les données qui arrivent aujourd'hui
> ressemblent encore à celles sur lesquelles le modèle a appris. Quand elles changent trop,
> le modèle « vieillit » : il devient moins juste sans qu'aucune erreur ne saute aux yeux.
> Détecter ce vieillissement permet de relancer un entraînement au bon moment. C'est la pièce
> qui ferme la boucle de vie du modèle : on entraîne, on surveille, et on ré-entraîne quand
> il le faut.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre à partir de zéro

Un modèle d'apprentissage automatique apprend des régularités dans les données qu'on lui montre
pendant l'entraînement. Si, plus tard, les données reçues en vrai changent de nature, le modèle
continue de raisonner avec « l'ancien monde » et se trompe de plus en plus.

On appelle ce phénomène la **dérive** (en anglais *drift*). Concrètement, la dérive veut dire que
la **distribution** des données change. Une distribution, c'est simplement la façon dont les
valeurs se répartissent : par exemple, la longueur moyenne des descriptions de produits, ou la
proportion de chaque catégorie. Sur une boutique en ligne, ces répartitions bougent naturellement :
de nouveaux produits apparaissent, le vocabulaire des vendeurs évolue, certaines catégories
deviennent plus ou moins fréquentes selon les saisons.

Le danger est sournois : la qualité du modèle baisse lentement, sans message d'erreur, juste une
dégradation progressive. Sans surveillance, on ne s'en aperçoit que trop tard.

**Evidently** est une bibliothèque Python spécialisée dans cette surveillance. Elle compare deux
jeux de données : un jeu de **référence** (ce que le modèle a connu à l'entraînement) et un jeu
**actuel** (les données récentes). Elle produit ensuite un **rapport visuel** sous forme de page web
qui montre, colonne par colonne, lesquelles ont dérivé et dans quelle mesure.

### Pour aller plus loin (lecteur technique)

On ne compare jamais les valeurs une à une, mais bien la forme globale des distributions, à l'aide
de tests statistiques. Les plus courants sont :

- le **PSI** (*Population Stability Index*) : un indicateur qui résume en un seul nombre l'écart
  entre deux distributions. Un seuil habituel est PSI supérieur à 0,2 ou 0,25 pour considérer la
  dérive comme significative.
- le test de **Kolmogorov-Smirnov**, pour comparer deux distributions de valeurs numériques.
- le test du **Chi-deux**, pour comparer des proportions entre catégories.
- la **divergence de Jensen-Shannon**, une mesure de distance entre deux distributions.

Une distinction importante : la **dérive des données** (l'entrée du modèle change) n'est pas la même
chose que la **dérive du concept** (la relation entre l'entrée et la bonne réponse change). Ici, on
traite la première. Enfin, une bonne détection ne doit pas seulement alerter : elle doit déclencher
une action concrète, en l'occurrence un ré-entraînement.

---

## 2. Ce que recommandent les bonnes pratiques du domaine

Les références du secteur convergent sur quelques principes :

- détecter la dérive avec des tests comme le PSI, Kolmogorov-Smirnov ou le Chi-deux, et enregistrer
  une **référence** (les distributions de départ) dès la mise en production.
- fixer des **seuils chiffrés** clairs et déclencher un ré-entraînement quand la tolérance est
  dépassée, plutôt que de se contenter d'une alerte que personne ne lit.
- suivre des indicateurs de distribution (PSI, Jensen-Shannon) en plus de la précision du modèle,
  car la précision seule peut rester bonne un moment tout en masquant une dérive qui arrive.
- intégrer cette surveillance dès la conception du système, et non comme une rustine ajoutée après
  coup. Evidently propose plus de vingt méthodes de détection et des visualisations prêtes à
  l'emploi, ce qui en fait un outil standard du domaine.

---

## 3. Notre implémentation : précisément ce que nous avons fait

Le système repose sur quatre fichiers, chacun avec un rôle bien défini.

| Brique | Fichier | Rôle |
|---|---|---|
| Détection | `src/monitoring/drift_detection.py` | Compare référence et actuel avec Evidently (`DataDriftPreset`) et produit un rapport web. |
| Métriques | `src/monitoring/push_metrics.py` | Envoie les scores de dérive vers un collecteur de mesures (Pushgateway Prometheus). |
| Orchestration | `infra/airflow/dags/rakuten_drift_check_dag.py` | Lance la vérification chaque jour et déclenche le ré-entraînement si besoin. |
| Visualisation | `monitoring/grafana/dashboards/evidently_drift.json` | Tableau de bord Grafana qui affiche l'évolution de la dérive. |

### Comment la dérive est calculée

Le fichier `src/monitoring/drift_detection.py` constitue deux jeux de données puis les compare.

- Le jeu de **référence** est un échantillon de 50 000 lignes tiré du fichier d'entraînement
  (`train.parquet`). C'est la photo de « l'ancien monde » connu du modèle.
- Le jeu **actuel** est un échantillon de 10 000 lignes tiré du fichier de test (`test.parquet`).
  Les deux échantillons sont tirés avec une graine aléatoire fixée (`seed=42`), ce qui rend le
  résultat reproductible : relancer le calcul donne le même tirage.

Une précision honnête : dans cette version, le jeu « actuel » est un substitut de démonstration.
En production réelle, ce jeu viendrait du journal des entrées récentes envoyées à l'interface de
programmation (l'API qui reçoit les requêtes), mais ces entrées ne sont pas encore enregistrées.
On utilise donc le jeu de test comme remplaçant pour faire tourner et démontrer toute la mécanique.

Trois caractéristiques sont comparées entre les deux jeux :

- `title_len` : la longueur du titre du produit, en nombre de caractères.
- `description_len` : la longueur de la description, en nombre de caractères.
- `_source_category` : la répartition des produits entre les catégories.

Les deux premières sont des valeurs numériques, la troisième est une variable de catégorie.
Evidently est informé de cette distinction (via un objet `DataDefinition`) pour appliquer le bon
test statistique à chaque colonne.

### La règle de décision

On applique le préréglage `DataDriftPreset` d'Evidently. Il calcule, parmi les caractéristiques
suivies, la **part de celles qui ont dérivé** (en anglais, la *share* de la métrique
`DriftedColumnsCount`). Cette part est un nombre entre 0 et 1.

La règle est simple et explicite : si cette part atteint ou dépasse le seuil
**`DRIFT_SHARE_THRESHOLD = 0,5`**, c'est-à-dire si **au moins 50 % des caractéristiques surveillées
ont dérivé**, alors on déclare la dérive. Dans le cas contraire, on considère que tout va bien et
on ne fait rien.

À chaque exécution, le calcul produit aussi un rapport visuel interactif écrit dans le fichier
`monitoring/evidently/reports/drift_latest.html`. Ce rapport est consultable dans un navigateur et
montre, pour chaque caractéristique, sa distribution de référence, sa distribution actuelle et le
verdict de dérive.

### La boucle qui se ferme automatiquement

La vérification est pilotée par un orchestrateur de tâches planifiées : Airflow, un outil qui lance
des traitements à heure fixe et enchaîne les étapes. Le traitement concerné s'appelle
`rakuten_drift_check` et s'exécute **chaque jour**.

Ce traitement est volontairement découpé en deux blocs séparés, ce qui est le schéma recommandé :

- un bloc de vérification (`detect_drift`), léger, fréquent et en lecture seule, qui calcule la
  dérive. Il s'appuie sur un opérateur dit « court-circuit » (`ShortCircuitOperator`) : si aucune
  dérive n'est détectée, la suite est sautée et il ne se passe rien d'autre.
- un bloc de déclenchement (`trigger_retrain`) qui, uniquement si la dérive est avérée, lance le
  traitement de ré-entraînement nommé `rakuten_retrain` (via un opérateur `TriggerDagRunOperator`).

Séparer un ré-entraînement (lourd et conditionnel) d'une simple vérification (légère et quotidienne)
évite de mobiliser des ressources inutilement. C'est exactement cette mécanique qui ferme la
boucle : une dérive constatée déclenche, sans intervention humaine, un nouvel entraînement.

### Le suivi des scores dans le temps

À la fin de chaque calcul, le module `src/monitoring/push_metrics.py` envoie les résultats vers un
collecteur de mesures appelé Pushgateway, lui-même relié à Prometheus (une base de données de
mesures) et à Grafana (un outil d'affichage de tableaux de bord). On y retrouve notamment la part
de colonnes dérivées (`rakuten_drift_share`), le nombre absolu de colonnes dérivées
(`rakuten_drift_columns_count`), une alerte binaire valant 1 ou 0 selon que le seuil est franchi
(`rakuten_drift_detected`), la valeur du seuil (`rakuten_drift_threshold`), la taille des deux
échantillons et l'horodatage du dernier calcul.

Ce passage par un Pushgateway est nécessaire parce que la vérification est un traitement court : il
démarre, calcule, puis s'arrête. Or Prometheus, par défaut, vient interroger les programmes encore
en cours d'exécution ; il manquerait donc systématiquement un traitement qui se termine trop vite.
La solution consiste à pousser les mesures vers le Pushgateway, qui les conserve et les tient à
disposition jusqu'au prochain envoi.

Deux protections rendent le système robuste. D'une part, si la bibliothèque d'envoi des mesures
n'est pas installée, le calcul de dérive continue quand même et émet un simple avertissement.
D'autre part, si le Pushgateway n'est pas joignable (par exemple lors d'une démonstration sans
toute l'infrastructure démarrée), l'envoi échoue proprement sans faire planter le calcul métier.
La surveillance ne doit jamais casser ce qu'elle surveille.

### Lancer la détection à la main

Le calcul s'exécute aussi seul, en ligne de commande, avec `python -m src.monitoring.drift_detection`.
Il affiche alors le résultat au format JSON (un format texte structuré, facile à relire par un autre
programme), contenant entre autres la décision de dérive, la part de colonnes dérivées et le chemin
du rapport produit.

---

## 4. Résultats mesurés

- **Un vrai rapport visuel existe** : le fichier `monitoring/evidently/reports/drift_latest.html`
  pèse environ 3,8 Mo. C'est un rapport interactif réel, généré par Evidently, et non un fichier vide
  servant de simple exemple.
- **Une règle de décision chiffrée et nette** : la dérive est déclarée dès qu'au moins 50 % des
  caractéristiques surveillées ont changé.
- **La boucle dérive vers ré-entraînement est câblée** : le traitement quotidien déclenche bien le
  ré-entraînement quand la dérive est confirmée.
- **Les scores sont remontés** vers le Pushgateway puis affichés dans Grafana, ce qui permet de
  suivre l'évolution de la dérive jour après jour.
- **Des tests automatiques** valident chaque morceau : `test_drift_detection.py` pour le calcul,
  `test_drift_check_dag.py` pour l'orchestration et `test_push_metrics.py` pour l'envoi des mesures.

> Repère pour une diapositive. Points à mettre en avant : « détection avec Evidently
> (`DataDriftPreset`) », « seuil de 50 % de caractéristiques dérivées qui déclenche le
> ré-entraînement », « les scores remontent vers Grafana ». Capture d'écran conseillée : le rapport
> web Evidently (`drift_latest.html`, avec ses barres de dérive par caractéristique) accompagné du
> tableau de bord Grafana. Cette brique est très visuelle, donc parfaite pour une présentation.

---

## 5. Regard critique : où l'on est solide, où l'on est limité

### Points solides

- On utilise un outil standard et reconnu du domaine (Evidently), qui produit un vrai rapport
  visuel.
- La décision repose sur un seuil chiffré et déclenche une action concrète : on suit le principe
  « détecter puis agir », et pas seulement « détecter ».
- La surveillance est intégrée dès la conception, avec un traitement planifié dédié, des mesures
  remontées et un tableau de bord. Ce n'est pas un ajout de dernière minute.
- Des tests automatiques couvrent chaque composant.

### Limites assumées

- La décision se fonde sur la **part de caractéristiques dérivées** (50 %) plutôt que sur un PSI
  réglé finement, caractéristique par caractéristique. C'est plus simple à comprendre et à
  expliquer, mais moins granulaire que la pratique idéale (un seuil PSI supérieur à 0,2 pour chaque
  variable prise séparément).
- La **référence est figée** sur un échantillon unique. La bonne pratique serait une référence qui
  glisse dans le temps, c'est-à-dire une fenêtre récente qui se met à jour ; ce n'est pas encore
  fait.
- On ne surveille que la **dérive des données**. On ne mesure ni la dérive du concept (un changement
  de la relation entre l'entrée et la bonne réponse), ni la performance réelle du modèle en
  production, faute de retours du terrain.
- Le **déclenchement automatique** de la dérive vers le ré-entraînement existe et est câblé, mais il
  reste à valider de bout en bout en conditions réelles.
- Le jeu « actuel » est aujourd'hui un substitut de démonstration (le jeu de test) : en production,
  il faudra le remplacer par le journal réel des requêtes reçues, qui n'est pas encore enregistré.

---

## 6. Références

- Evidently AI, *What is data drift in ML* : https://www.evidentlyai.com/ml-in-production/data-drift
- Evidently AI, *Comparing 5 drift detection methods on large datasets* : https://www.evidentlyai.com/blog/data-drift-detection-large-datasets
- DataCamp, *Understanding data drift and model drift* : https://www.datacamp.com/tutorial/understanding-data-drift-model-drift
- IBM, *What is model drift?* : https://www.ibm.com/think/topics/model-drift

---

### En une phrase, pour la défense

*« On surveille la dérive des données avec Evidently : un rapport visuel compare un jeu de référence
au jeu récent, et si plus de 50 % des caractéristiques ont changé, on déclenche automatiquement un
ré-entraînement. La surveillance est intégrée dès la conception (traitement quotidien dédié, scores
remontés vers Grafana) : c'est la brique qui ferme la boucle de vie du modèle. »*
