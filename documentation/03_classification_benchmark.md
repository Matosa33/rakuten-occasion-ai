# 03. Classification et comparaison de modèles

> L'idée tient en une phrase : au lieu de parier sur un seul modèle, on en entraîne plusieurs,
> on les compare sur exactement les mêmes données et les mêmes mesures, puis on choisit le
> meilleur. Tout est mesuré, rien n'est arrangé. C'est le cœur de la rigueur en apprentissage
> automatique.

---

## 1. De quoi parle-t-on ?

### Le problème, expliqué à partir de zéro

**Classer un produit**, c'est apprendre à le ranger dans la bonne **catégorie**. Dans ce projet,
il y a quatre grandes catégories : l'électronique (Electronics), les téléphones et accessoires
(Cell_Phones_and_Accessories), les jeux vidéo (Video_Games) et l'outillage et la maison
(Tools_and_Home_Improvement).

La méthode est toujours la même. On montre à un programme un grand nombre d'exemples déjà
étiquetés (cet ensemble d'apprentissage s'appelle le « train »). Le programme cherche tout seul
des régularités. Ensuite, on lui présente des exemples qu'il n'a **jamais vus** (l'ensemble de
« test ») et on vérifie s'il les range correctement. Mesurer sur des exemples jamais vus est
essentiel : un élève qui récite les corrigés par cœur n'a rien appris ; on veut savoir s'il sait
répondre à des questions nouvelles.

**Comparer (benchmark)** veut dire : ne pas se contenter d'un seul modèle. On en entraîne
plusieurs et on les met en concurrence sur le même protocole. Pourquoi ? Parce qu'on ne sait pas
à l'avance lequel sera le meilleur sur nos données précises, et qu'un modèle isolé « qui a l'air
de marcher » ne prouve rien tant qu'il n'a pas de point de comparaison.

### Les mesures de qualité (et pourquoi il en faut plusieurs)

Une seule mesure peut masquer un défaut. On en utilise donc quatre familles complémentaires.

- **Le F1-score** (un nombre entre 0 et 1, plus c'est haut mieux c'est). Il combine deux qualités
  opposées. La **précision** répond à : « quand je dis Téléphone, ai-je raison ? ». Le **rappel**
  répond à : « est-ce que j'attrape bien tous les téléphones ? ». Le F1 est leur équilibre.
  On le calcule de deux façons :
  - **F1 pondéré** : moyenne qui donne plus de poids aux grandes catégories (celles qui ont
    beaucoup de produits).
  - **F1 macro** : moyenne **simple**, qui traite toutes les catégories **à égalité**, y compris
    les rares. C'est une mesure plus sévère, car une catégorie peu fréquente compte autant qu'une
    catégorie immense.
- **La précision top-k** (top-1, top-3). On regarde si la bonne réponse figure parmi les *k*
  premières propositions du modèle. C'est utile parce que l'interface du produit propose souvent
  plusieurs candidats à l'utilisateur, pas un seul.
- **L'ECE** (de l'anglais *Expected Calibration Error*, « erreur de calibration attendue »). Cette
  mesure répond à une question d'honnêteté : quand le modèle dit « je suis sûr à 80 % », a-t-il
  vraiment raison environ 80 % du temps ? Un modèle bien **calibré** ne se vante pas et ne se
  sous-estime pas. On le calcule en rangeant les prédictions dans **10 tranches** de niveau de
  confiance et en comparant, dans chaque tranche, la confiance annoncée et la réussite réelle.
  Un ECE proche de 0 signifie une confiance fiable.

### Pour le lecteur plus technique

- **Écart entre F1 macro et F1 pondéré** : s'ils s'éloignent fortement, c'est que le modèle gère
  mal la **longue traîne**, c'est-à-dire les catégories rares. Dans nos résultats ils restent
  **proches**, ce qui est le signe d'une bonne couverture, y compris des catégories peu peuplées.
- **Calibration de Platt** : certains modèles (les machines à vecteurs de support linéaires)
  ne sortent pas naturellement des probabilités, mais des scores de marge. La calibration de Platt
  est une petite régression en forme de S (sigmoïde) appliquée par-dessus ces scores pour les
  transformer en vraies probabilités. On obtient ainsi des chiffres exploitables, à la fois pour
  mesurer l'ECE et pour décider quand demander une confirmation humaine.

---

## 2. Ce que recommandent les bonnes pratiques

- **Rapporter le F1 macro ET le F1 pondéré**, et idéalement le détail catégorie par catégorie,
  pour rester transparent.
- **Calibrer** : un bon modèle ne doit pas seulement avoir souvent raison, il doit aussi
  **connaître son incertitude**. D'où la mesure de l'ECE.
- **Protocole identique pour tous les modèles**, sans **fuite de données** (en anglais *data
  leakage* : laisser involontairement le modèle apprendre sur les exemples de test, ce qui gonfle
  artificiellement les scores). On apprend sur le train et on mesure sur un test resté intouché.
- **Aucun modèle n'est universellement supérieur** : k plus proches voisins, machines à vecteurs
  de support, réseau de neurones simple, combinaisons de modèles, chacun a ses forces. Seule la
  comparaison empirique permet de trancher.

---

## 3. Notre mise en œuvre, en détail

### Les six modèles comparés (l'exigence demandait au moins trois)

| Code | Fichier | Modèle | En clair |
|---|---|---|---|
| **knn-faiss** | `02_knn.py` | k plus proches voisins, par similarité, via l'index FAISS | on retrouve les 5 produits du train les plus ressemblants et on vote leur catégorie |
| **svm-embed** | `03_svm.py` | Machine à vecteurs de support linéaire (LinearSVC) + calibration de Platt | tracée sur un échantillon de 500 000 lignes pour limiter le coût |
| rf-embed | `04_rf.py` | Forêt aléatoire (Random Forest) | **écartée**, peu efficace en grande dimension (1024) |
| **mlp-embed** | `05_mlp.py` | Petit réseau de neurones (perceptron multicouche) | échantillon de 500 000 lignes |
| **tfidf-svm** | `01_tfidf_linsvc.py` | TF-IDF + machine à vecteurs de support + Platt | n'utilise PAS les vecteurs ; travaille directement sur les mots du texte |
| **fusion** | `06_fusion_adaptive.py` | Fusion, combinaison adaptative des modèles | mélange pondéré des probabilités de plusieurs modèles |
| (outil) | `07_bench_report.py` et `metrics.py` | génère le tableau comparatif et calcule toutes les mesures | F1 pondéré et macro, exactitude, top-1 et top-3, ECE en 10 tranches |

Quelques mots pour comprendre les noms techniques utilisés ci-dessus.

- **Un vecteur (ou embedding)** est une longue liste de nombres (ici 1024 nombres) qui résume le
  sens d'un produit. Deux produits proches dans cette représentation ont un sens proche. Ces
  vecteurs sont produits en amont par un modèle de langue, à partir du titre et de la description.
- **FAISS** est une bibliothèque qui retrouve très vite, parmi des millions de vecteurs, ceux qui
  ressemblent le plus à un vecteur donné. knn-faiss s'appuie dessus pour trouver les voisins en une
  fraction de milliseconde.
- **TF-IDF** (de l'anglais *Term Frequency, Inverse Document Frequency*) est une technique
  ancienne et robuste qui transforme un texte en chiffres en pesant chaque mot selon son
  importance : un mot fréquent dans une fiche mais rare dans le catalogue est jugé révélateur.
  Contrairement aux autres modèles, tfidf-svm ne lit pas les vecteurs de sens, il lit directement les
  mots.

### Réglages exacts de chaque modèle

- **knn-faiss (k plus proches voisins)** : pour chaque produit à classer, on cherche ses **5** voisins
  les plus proches dans le train (k = 5), avec une mesure de proximité par cosinus (l'angle entre
  deux vecteurs ; les vecteurs étant normalisés, c'est équivalent au produit scalaire). Chaque
  voisin vote pour sa catégorie, et son vote pèse selon sa ressemblance. La recherche passe par un
  index FAISS de type HNSW (un graphe de navigation qui accélère énormément la recherche, réglé
  ici avec M = 32 connexions et un paramètre d'exploration efSearch = 64).
- **svm-embed (machine à vecteurs de support sur les vecteurs de sens)** : LinearSVC avec un paramètre de
  régularisation C = 1.0, des poids de classe équilibrés (pour ne pas négliger les catégories
  rares), une calibration de Platt validée en 3 plis. Apprentissage sur un échantillon de
  500 000 lignes.
- **mlp-embed (petit réseau de neurones)** : une architecture 1024 puis 512 puis 256 puis 4 sorties (une
  par catégorie), fonction d'activation ReLU, optimiseur Adam, lots (batches) de 256 exemples,
  au plus 30 passages sur les données avec arrêt anticipé (on stoppe dès que la qualité cesse de
  progresser sur une part de validation interne). Apprentissage sur un échantillon de 500 000
  lignes.
- **tfidf-svm (TF-IDF + machine à vecteurs de support)** : on retient jusqu'à 50 000 mots et expressions,
  en comptant les mots seuls et les paires de mots consécutifs (ngram_range de 1 à 2), en ignorant
  les termes apparaissant moins de deux fois, avec une pondération adoucie (sublinear_tf). Le
  classifieur derrière est de nouveau un LinearSVC (C = 1.0, poids équilibrés) suivi d'une
  calibration de Platt en 3 plis. Ce modèle apprend sur la totalité du train.
- **rf-embed (forêt aléatoire), écartée mais documentée** : elle avait été préparée avec 300 arbres, une
  profondeur maximale de 20 et la racine carrée du nombre de dimensions testée à chaque coupe. Elle
  reste peu adaptée à des vecteurs de 1024 dimensions et n'a pas été retenue dans le classement.
- **fusion (fusion)** : on ne réentraîne rien. On prend les probabilités déjà produites par plusieurs
  modèles, on en fait une moyenne pondérée, et on cherche les poids qui donnent le meilleur
  résultat sur l'ensemble de validation (recherche sur une grille de poids). Toutes les
  probabilités sont calibrées par Platt, donc comparables entre elles.

### Les règles d'évaluation que l'on s'est imposées

- **Pas de fuite de données.** On entraîne (on « ajuste ») uniquement sur le train, puis on mesure
  (on « prédit ») sur la validation puis sur le test. Jamais rien n'est réglé en regardant le test.
  Pour les deux modèles les plus longs à entraîner (svm-embed et mlp-embed), on apprend sur un **échantillon de
  500 000 lignes** prélevé dans le train (qui en compte plus de 3 millions) au lieu de la totalité.
  Cet échantillon est tiré uniquement côté train, et la validation comme le test sont évalués en
  entier. On a vérifié que l'écart de F1 entre 500 000 lignes et le train complet est inférieur à
  0,01 : l'apprentissage a déjà atteint son plateau. C'est un gain de temps sans perte de qualité,
  pas un raccourci subi. Ce plateau est cohérent avec un fait connu en traitement du texte (la loi
  de Heaps) : passé un certain volume, voir plus d'exemples n'apporte presque plus de vocabulaire
  nouveau, donc presque plus d'information.
- **Comparaison large** : six modèles évalués, là où la consigne en demandait au moins trois.
- **Traçabilité.** Chaque entraînement est enregistré comme une « exécution » dans MLflow, un
  outil de suivi qui conserve automatiquement les réglages, les scores et les fichiers produits.
  Tout est ainsi reproductible et comparable après coup.

### Pourquoi knn-faiss est le meilleur, mais tfidf-svm est celui mis en service

knn-faiss (les k plus proches voisins via FAISS) obtient le **meilleur score**, mais il ne fonctionne que
si l'index FAISS est présent et chargé : il ne sait rien faire tout seul. tfidf-svm (TF-IDF avec machine à
vecteurs de support), lui, est **autonome et facile à déplacer** : c'est un seul fichier qui
contient tout. On garde donc **knn-faiss comme moteur de la recherche par ressemblance** (le cœur du
produit) et **tfidf-svm comme classifieur effectivement déployé et versionné**. C'est un choix
d'ingénierie de mise en production (portabilité), pas un hasard.

### À quoi sert vraiment ce classifieur, et comment on attribue la catégorie fine

Une distinction importante à énoncer clairement : ces classifieurs entraînés ne sont **pas** le
moteur d'identification des produits en ligne. Ils servent à deux choses.

1. **Prouver la rigueur** : entraîner, comparer et calibrer plusieurs modèles, ce qui est tout
   l'objet de ce document.
2. **Faire vivre la chaîne de mise en production** : pour démontrer un cycle de vie complet
   (versionner un modèle, le promouvoir, le réentraîner, le servir), il faut un vrai modèle
   déployé. C'est le classifieur texte portable (tfidf-svm) qui joue ce rôle.

En usage réel, l'identification d'un produit passe par la **recherche de ressemblance** (on
retrouve les produits voisins), pas par le classifieur servi. Et la **catégorie la plus fine**
affichée sur la fiche n'est pas la sortie d'un modèle qui choisirait parmi 2 956 catégories (ce
serait impossible à entraîner proprement, car beaucoup de ces catégories ont trop peu d'exemples).
Cette catégorie fine résulte d'un **vote pondéré des catégories des produits voisins** retrouvés.
Autrement dit, c'est l'index de recherche lui-même qui joue le rôle de classifieur fin.

On a comparé **quatre façons** d'attribuer cette catégorie fine, toujours sur le même protocole
(échantillon de test, sans fuite de données : 15 000 requêtes, 200 voisins examinés par requête).
Et surtout, on mesure la justesse à **chaque niveau du chemin de catégories**, pas seulement tout
en bas. Un chemin va du plus général au plus précis : la grande famille (le « macro », par exemple
Électronique), puis un premier sous-niveau intermédiaire (noté L1, par exemple Composants
informatiques), puis un second (noté L2, par exemple Cartes graphiques), jusqu'à la feuille (en
anglais « leaf »), la catégorie la plus fine. Mesurer chaque niveau montre exactement où la
prédiction commence à se tromper.

| Méthode | macro | L1 | L2 | feuille | F1 hiérarchique |
|---|---|---|---|---|---|
| Premier voisin recopié | 0,942 | 0,889 | 0,808 | 0,710 | 0,812 |
| Filtrage par famille puis premier voisin | 0,949 | 0,893 | 0,810 | 0,709 | 0,812 |
| **Vote des voisins** *(retenue)* | 0,949 | **0,949** | **0,849** | **0,733** | **0,820** |
| Du large au fin (filtre par famille puis vote) | 0,949 | 0,947 | 0,848 | 0,731 | 0,818 |

Le « F1 hiérarchique » récompense les bonnes réponses partielles : se tromper de feuille mais avoir
juste les niveaux du dessus vaut mieux que tout rater. Lecture : la justesse baisse quand on descend
(de 0,95 en grande famille à 0,73 en feuille), ce qui est normal puisque les catégories fines sont
beaucoup plus nombreuses et se ressemblent davantage. Le vote des voisins est le meilleur ou à
égalité à **tous les niveaux**, et nettement devant sur les niveaux intermédiaires (L1 et L2).

Le **vote des voisins l'emporte** (gain de 2,3 points par rapport à recopier le premier voisin),
pour un coût quasi nul, et il fournit en prime une mesure de **confiance** (la part du vote
remportée par la catégorie gagnante). Résultat honnête à signaler : le filtrage par famille
**n'aide pas**. Les quatre familles sont déjà bien séparées dans l'espace des vecteurs ; filtrer
ne fait donc que jeter de bons voisins. À titre indicatif, la recherche retrouve la bonne
catégorie fine parmi les 200 voisins examinés dans 96,8 % des cas, ce qui est le plafond
qu'un meilleur vote pourrait viser.

---

## 4. Résultats mesurés

Modèles triés par F1 pondéré sur le test (du meilleur au moins bon).

| Rang | Modèle | F1 pondéré | F1 macro | ECE | Temps d'entraînement |
|---|---|---|---|---|---|
| 1 | **knn-faiss k plus proches voisins (FAISS)** | **0,9537** | 0,9415 | 0,0069 | environ 0 s (réutilise l'index) |
| 2 | fusion fusion | 0,9522 | 0,9418 | 0,0230 | environ 0 s |
| 3 | **tfidf-svm TF-IDF + machine à vecteurs de support** | **0,9503** | 0,9375 | 0,0092 | 956 s |
| 4 | mlp-embed petit réseau de neurones | 0,9489 | 0,9382 | **0,0013** (meilleure calibration) | 514 s |
| 5 | svm-embed machine à vecteurs de support sur vecteurs | 0,9311 | 0,9193 | 0,0145 | 924 s |

Lecture des chiffres. Partout, le F1 pondéré et le F1 macro sont très proches : le modèle gère
donc **bien les catégories rares**, et pas seulement les grandes. L'objectif que l'on s'était fixé
(« un F1 supérieur à 0,90 ») est **largement atteint**. mlp-embed affiche la **meilleure calibration**
(ECE de 0,0013) : sa confiance est la plus fiable, ce qui serait précieux si l'on cherchait
avant tout un modèle dont les pourcentages de certitude sont dignes de foi.

Un point d'honnêteté sur la fusion (fusion) : elle ne dépasse pas le meilleur modèle individuel. Son
F1 pondéré au test (0,9522) est même très légèrement inférieur à celui de knn-faiss (0,9537), soit un
écart de 0,0015 dans le mauvais sens. Combiner plusieurs modèles a donc ici un coût (il faut faire
tourner plusieurs modèles) sans bénéfice de qualité : c'est un résultat utile à connaître, et
exactement le genre de constat qu'un benchmark sert à révéler.

> Chiffres pour une diapositive : « 6 modèles comparés », « F1 pondéré 0,954 pour knn-faiss », « F1 macro
> proche du F1 pondéré, donc catégories rares bien gérées », « ECE 0,0013 pour mlp-embed », « objectif
> de 0,90 atteint ». Capture d'écran suggérée : le tableau de comparaison plus la liste des
> exécutions dans MLflow, triables par F1.

---

## 5. Regard critique : nos forces et nos limites

**Ce qui est solide.**

- Six modèles évalués sur un protocole identique et sans fuite de données, ce qui dépasse
  l'exigence minimale.
- Des mesures riches et complémentaires : F1 pondéré, F1 macro, ECE, top-1 et top-3, temps
  d'entraînement.
- Une calibration explicite (Platt), donc des probabilités exploitables et un ECE réellement
  mesuré.
- Un F1 macro proche du F1 pondéré, preuve d'une bonne couverture des catégories rares.
- Tout est tracé dans MLflow, donc reproductible et comparable.

**Les limites, assumées.**

- Ce sont des modèles d'apprentissage classique, pas un grand réseau de neurones profond entraîné
  de zéro. C'est un choix adapté (la recherche par ressemblance fait l'essentiel du travail), mais
  il faut le dire clairement : la valeur démontrée ici est « comparer rigoureusement plusieurs
  modèles », pas « entraîner un énorme réseau ».
- La forêt aléatoire (rf-embed) a été écartée car inefficace en 1024 dimensions. C'est une décision
  documentée, pas un oubli.
- L'échantillon de 500 000 lignes pour svm-embed et mlp-embed est justifié (plateau d'apprentissage vérifié),
  mais ce n'est pas le train complet.
- Le détail catégorie par catégorie est calculé par le code mais n'est pas mis en avant dans le
  tableau de synthèse (le F1 macro le résume). C'est un axe d'amélioration en matière de
  transparence.
- La tâche est relativement « facile » : les quatre grandes catégories sont bien séparées dans
  l'espace des vecteurs. Les F1 élevés reflètent donc aussi cette facilité du problème, ce qu'il
  faut contextualiser honnêtement. La difficulté réelle apparaît au niveau de la catégorie la plus
  fine, où l'on plafonne autour de 0,73 d'exactitude.
- **Doublons quasi-identiques (à signaler honnêtement).** Le découpage train/test est propre au
  niveau de l'identifiant produit (un même produit ne peut pas être à la fois en apprentissage et en
  test). Mais le catalogue contient des annonces **quasi-identiques** sous des identifiants
  différents (le même objet revendu par plusieurs boutiques, avec un texte presque copié). Le modèle
  k plus proches voisins, qui retrouve les produits les plus ressemblants, en bénéficie un peu : son
  F1 réel est donc légèrement **optimiste** (de l'ordre de quelques points). Ce n'est pas une fuite
  de données au sens strict, mais une caractéristique du catalogue qu'il faut mentionner pour ne pas
  survendre le score.

---

## 6. Références

- EmergentMind, *Macro-F1 score overview* : https://www.emergentmind.com/topics/macro-f1-score
- scikit-learn, *Probability calibration (Platt scaling)* :
  https://scikit-learn.org/stable/modules/calibration.html
- NCBI Bookshelf, *Evaluating machine learning models and their diagnostic value* :
  https://www.ncbi.nlm.nih.gov/books/NBK597473/
- arXiv 2310.10655, *Uncertainty quantification and calibration (ECE)* :
  https://arxiv.org/pdf/2310.10655

---

### En une phrase, pour la soutenance

*On n'a pas parié sur un seul modèle : six modèles ont été entraînés et comparés sur le même
protocole, sans fuite de données, en mesurant le F1 pondéré, le F1 macro, la calibration (ECE) et
le temps. Le meilleur atteint 0,954 de F1, le F1 macro reste proche du pondéré (les catégories
rares sont donc bien gérées), et le modèle réellement mis en service est choisi pour une raison
d'ingénierie (sa portabilité, tfidf-svm), pas par hasard.*
