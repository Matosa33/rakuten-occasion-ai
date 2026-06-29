# Glossaire : tous les termes techniques, expliqués simplement

> Ce fichier est le « décodeur » du projet. Chaque mot technique employé
> ailleurs y est expliqué en une ou deux phrases claires, sans supposer aucune
> connaissance préalable.
> But : n'importe qui peut comprendre le vocabulaire du projet sans bloquer sur
> le jargon, et un lecteur technique y retrouve les définitions exactes.

## Le projet en une phrase

Le projet est un assistant qui aide un particulier à mettre en vente un objet
d'occasion : à partir d'une photo et d'un texte, il identifie le produit dans un
catalogue, vérifie que la photo correspond bien, rédige automatiquement une
annonce et suggère un prix. Le périmètre couvre quatre familles de produits :
l'électronique (Electronics), les téléphones et accessoires
(Cell_Phones_and_Accessories), les jeux vidéo (Video_Games) et l'outillage et
bricolage (Tools_and_Home_Improvement).

## Données et représentations

- **Embedding (vecteur)** : une liste de nombres qui résume le *sens* d'un texte
  ou d'une image. Le texte des produits est résumé en une liste de 1024 nombres,
  les images en une liste de 768 nombres. Deux objets au sens proche donnent deux
  listes de nombres proches, ce qui permet de les comparer mathématiquement.
- **Normalisation L2** : ramener tous les vecteurs à la même longueur (la
  longueur 1) pour ne comparer que leur *direction*, c'est-à-dire le sens, et
  jamais leur taille. Dans le projet, cette mise à la même échelle est faite une
  seule fois, au moment de produire les vecteurs.
- **Similarité cosinus** : une mesure de l'*angle* entre deux vecteurs. Un petit
  angle signifie un sens proche. La valeur va de -1 (opposés) à 1 (identiques).
- **FP16 (float16)** : un format qui stocke chaque nombre sur 16 bits au lieu de
  32. Cela divise par deux la place sur le disque, avec une perte de précision
  négligeable pour la recherche de produits similaires. Les vecteurs sont
  stockés dans ce format compact.
- **mmap (memory-map)** : une technique pour lire un gros fichier « à la
  demande », morceau par morceau, sans tout charger dans la mémoire vive. Elle
  évite de saturer la mémoire quand les fichiers de vecteurs pèsent plusieurs
  giga-octets.
- **GroupKFold** : une façon de séparer les données en un jeu d'entraînement et un
  jeu de test en gardant tout un *groupe* du même côté. Ici un groupe est un
  produit : toutes les lignes d'un même produit vont soit dans l'entraînement,
  soit dans le test, jamais à cheval.
- **Stratification** : garder les mêmes proportions de catégories dans chaque jeu
  de données (entraînement, validation, test), pour qu'aucun jeu ne sur-représente
  une famille de produits.
- **Data leakage (fuite de données)** : une information du jeu de test qui « fuit »
  par erreur dans l'entraînement. Le modèle a alors triché sans le savoir, et son
  score paraît excellent mais est faux. Le projet vérifie explicitement l'absence
  de fuite.
- **Pandera** : un outil qui vérifie automatiquement que chaque colonne d'un
  tableau de données respecte un *contrat* : le bon type (texte, nombre), une
  plage de valeurs autorisée, l'absence de cases vides là où c'est interdit.

## Recherche de produits similaires (retrieval)

- **FAISS** : une bibliothèque logicielle qui retrouve très vite les vecteurs les
  plus proches d'un vecteur donné, parmi des millions. C'est le moteur qui, à
  partir de la photo et du texte du vendeur, repère les produits du catalogue qui
  ressemblent le plus.
- **HNSW** : un type d'index FAISS organisé en graphe à plusieurs étages, comme un
  réseau routier où l'on prend d'abord l'autoroute puis les petites rues pour
  arriver vite et juste. C'est l'index principal du projet, réglé pour être à la
  fois rapide et précis.
- **IVF_PQ** : un autre type d'index FAISS, *compressé*. Il occupe beaucoup moins
  de mémoire (entre huit et seize fois moins) au prix d'une précision légèrement
  inférieure. Utile quand la mémoire est limitée.
- **Recherche approchée (ANN, Approximate Nearest Neighbors)** : trouver les
  vecteurs « presque » les plus proches, au lieu des plus proches exacts. C'est
  beaucoup plus rapide, et la minuscule imprécision est sans conséquence en
  pratique.
- **Recall@k** : la proportion de cas où le bon résultat figure parmi les *k*
  premiers proposés. Par exemple Recall@5 mesure : « dans combien de cas le bon
  produit est-il dans les 5 premiers ? ».
- **RRF (Reciprocal Rank Fusion)** : une méthode qui fusionne plusieurs
  classements en regardant les *rangs* plutôt que les scores. Chaque produit
  reçoit, pour chaque classement, des points calculés par la formule un divisé par
  (60 plus son rang) ; les points sont additionnés. La constante 60 est la valeur
  d'usage. L'intérêt : on combine un classement issu du texte et un classement
  issu de l'image sans avoir à régler de poids, et le résultat reste robuste même
  si les deux n'utilisent pas la même échelle de scores.
- **OOD (Out-Of-Distribution, hors distribution)** : un cas « inconnu », par
  exemple un produit absent du catalogue. Le système le détecte et le signale
  plutôt que d'inventer une réponse fausse. La détection repose surtout sur deux
  signaux : un score de ressemblance trop faible avec tout le catalogue, ou un
  écart trop mince entre les deux meilleurs candidats.
- **Akinator** : un mécanisme qui lève le doute quand plusieurs candidats ont des
  scores très proches. Au lieu de poser une question écrite au vendeur, il lui
  demande de prendre *la* photo la plus utile pour trancher (vue de dos, scan de
  l'étiquette, gros plan sur les connecteurs, etc.). Le principe : demander à
  voir, pas à savoir.
- **Entropie de Shannon** : une mesure de « à quel point une caractéristique
  sépare bien » les candidats. Si chaque candidat a une valeur différente pour une
  caractéristique, celle-ci est très discriminante (entropie élevée) ; si tous
  partagent la même valeur, elle est inutile pour trancher (entropie nulle).
  C'est ce calcul qui choisit quelle photo demander au vendeur.

## Intelligences artificielles génératives

- **VLM (Vision-Language Model, modèle vision-langage)** : une IA capable de
  comprendre des images. Ici, elle regarde la photo du vendeur et l'image du
  produit candidat dans le catalogue, puis répond si c'est bien le même modèle.
- **LLM (Large Language Model, grand modèle de langage)** : une IA capable de
  comprendre et d'écrire du texte. Ici, elle rédige le titre et la description de
  l'annonce.
- **RAG (Retrieval-Augmented Generation, génération assistée par récupération) /
  grounded (ancré)** : donner à l'IA les *faits réels* du produit (extraits, par
  exemple, de vrais avis d'acheteurs) et lui interdire d'inventer le reste. Le
  texte produit reste ainsi collé à la réalité.
- **Hallucination** : quand une IA invente une information qui semble plausible
  mais qui est fausse. Tout le dispositif d'ancrage du projet vise à l'éviter.
- **Prompt** : les instructions et le contexte donnés à l'IA pour obtenir une
  réponse. Dans le projet, chaque prompt suit la même structure : le rôle à jouer,
  la tâche à accomplir, les faits réels à respecter, puis le format de réponse
  attendu.
- **Température** : un réglage de la « créativité » du modèle de langage. Une
  valeur basse rend les réponses factuelles et peu inventives. Le projet utilise
  la valeur 0,4 pour la rédaction des annonces, qui privilégie la fidélité aux
  faits. Les tâches d'extraction et de jugement structuré (identification
  raisonnée, voir plus bas) utilisent quant à elles la valeur 0, la plus
  factuelle possible, complétée par une graine fixe (seed) et le raisonnement
  désactivé pour que la même photo redonne toujours la même réponse.

## Identification raisonnée (le retriever sait, le modèle juge)

> L'idée centrale tient en une phrase : le
> *retriever* (la recherche de produits similaires) apporte la **connaissance**
> (les vrais produits du catalogue), et le modèle vision-langage apporte le
> **jugement** (lequel correspond, à quel prix neuf). Le modèle ne peut jamais
> inventer un produit hors de cette liste, ce qui le garde collé à la réalité.

- **Identification raisonnée** : une étape supplémentaire qui, après la recherche
  des produits similaires, demande à l'IA de *trancher* parmi les quinze
  meilleurs candidats. En un seul appel, l'IA reçoit une ou deux photos du
  vendeur plus les quinze fiches candidates **résumées en texte** (et non les
  quinze images du catalogue, pour économiser les jetons et donc le coût) ; elle
  renvoie la famille du produit, le candidat retenu, un éventuel signal d'absence
  du produit au catalogue, un prix neuf de référence et, au besoin, une question
  à poser au vendeur. C'est une étape **au mieux** (best-effort) : si la clé
  d'API manque, si le modèle est indisponible ou si sa réponse est illisible,
  l'étape renvoie « rien » et le reste du système continue avec le simple
  classement de la recherche. Elle ne peut donc jamais faire planter l'assistant
  ni produire une fiche vide.
- **Grounding (ancrage) avant génération** : le principe selon lequel l'IA doit
  fonder chaque affirmation sur un fait fourni (une fiche candidate réelle ou ce
  qui est visible sur la photo) plutôt que sur ses connaissances générales.
  Concrètement, plusieurs garde-fous appliquent cette règle après coup : si l'IA
  choisit un produit qui n'est pas dans les quinze candidats, on l'ignore et on
  retombe sur le premier résultat de la recherche, en remettant la confiance à
  zéro (l'IA n'a pas réellement validé ce produit) ; une caractéristique dont la
  source n'est pas vérifiable est jetée ; le prix neuf, lui, est conservé même
  sans preuve directe, car il est clairement étiqueté comme une *estimation* et
  non comme un fait.
- **Réordonnancement (le bon produit en tête)** : une fois le candidat jugé le
  plus pertinent désigné, il est remonté en première position de la liste. Tout
  ce qui suit (la fiche, le prix, la vérification visuelle) porte alors sur le
  **bon** produit. Sans cette correction, le premier résultat brut de la
  recherche pouvait être un accessoire : par exemple une coque d'iPhone affichée
  comme s'il s'agissait du téléphone lui-même.
- **Catalog-miss (produit absent du catalogue)** : le cas où **aucun** des
  candidats n'est réellement le produit photographié, y compris quand tous sont
  un modèle, une génération ou une variante différente de ce que l'on voit (on
  voit une « RTX 4080 » mais tous les candidats sont des « RTX 3080 », ou un
  « iPhone 14 » alors que tous sont des « iPhone 13 »). Dans ce cas, l'IA décrit
  le produit qu'elle voit *vraiment* et estime son prix par analogie avec les
  comparables, sans traiter les caractéristiques du mauvais candidat comme des
  faits. Côté vendeur, un bandeau signale honnêtement « produit estimé, absent du
  catalogue ».
- **Texte vendeur autoritaire** : une règle **déterministe** (sans IA) qui donne
  le dernier mot au texte saisi par le vendeur. Si ses précisions nomment un
  produit présent parmi les candidats, ce candidat est retenu, indépendamment du
  modèle rapide qui ignore parfois cette consigne. Le match est exigeant : au
  moins deux mots discriminants du texte présents dans le titre du candidat et au
  moins la moitié des mots couverts, en gardant les numéros de modèle même à un
  seul chiffre (pour distinguer « Momentum 3 » de « Momentum 2.0 »). En cas
  d'égalité entre candidats, on retient celui dont le prix est le plus
  représentatif (le plus proche de la médiane), pour ne pas bâtir la fiche sur
  une donnée corrompue (un même « Momentum 3 » listé à 9 755 $ par erreur). Sur
  un texte vide, la règle ne fait rien : aucun risque de régression.
- **Question discriminante (poser une question, pas inventer)** : quand une seule
  caractéristique manquante (la capacité, la couleur, la variante exacte) suffit
  à changer le produit ou son prix, l'IA lève un signal et formule **une** courte
  question destinée au vendeur, plutôt que de deviner. C'est le pendant écrit du
  mécanisme Akinator, ici porté par le jugement de l'IA.
- **Flag « Modèle à confirmer »** : un bandeau actionnable affiché quand
  l'identification du *modèle exact* reste incertaine. Le pourcentage de
  confiance montré au vendeur correspond à la part du vote des plus proches
  voisins sur la catégorie fine ; il n'est affiché que s'il est net (au moins
  60 %). Un pourcentage bas ne traduit pas un doute sur la *catégorie* mais une
  *fragmentation* du vote (le produit exact est ambigu, par exemple un casque où
  le vote se disperse à 34 %). Plutôt que d'afficher ce chiffre trompeur, on
  invite alors le vendeur à préciser le modèle ou à ajouter une photo de
  l'étiquette ou de la boîte, en reprenant la question discriminante de l'IA si
  elle en a posé une.

## Modèles et mesures de qualité

- **F1-score** : une note entre 0 et 1 qui résume la qualité d'un classifieur
  (l'outil qui range un produit dans une catégorie). Elle équilibre deux risques :
  se tromper de catégorie et oublier des produits d'une catégorie.
- **F1 pondéré et F1 macro** : deux façons de faire la moyenne du F1 sur toutes
  les catégories. Le F1 pondéré tient compte de la taille de chaque catégorie ; le
  F1 macro les traite toutes à égalité, ce qui rend la note plus sévère quand les
  petites catégories sont mal prédites.
- **Top-k accuracy (justesse top-k)** : mesure si la bonne réponse figure parmi
  les *k* premières propositions du modèle, et non seulement à la première place.
- **ECE (Expected Calibration Error, erreur de calibration attendue)** : mesure si
  le modèle est *honnête* sur sa propre confiance. Un modèle bien calibré qui dit
  « 80 % sûr » a effectivement raison environ 80 % du temps. Plus l'ECE est bas,
  mieux c'est ; il est calculé en répartissant les prédictions en dix tranches de
  confiance.
- **Calibration de Platt** : une technique qui transforme les scores bruts d'un
  classifieur SVM en véritables probabilités lisibles. Dans le projet, les modèles
  texte sont calibrés ainsi pour produire des pourcentages de confiance fiables.
- **SVM (Support Vector Machine, machine à vecteurs de support)** : un type de
  classifieur qui sépare les catégories en traçant la meilleure frontière
  possible entre elles. Le projet en utilise une version linéaire, robuste sur un
  grand nombre de catégories.
- **MAPE (Mean Absolute Percentage Error, erreur absolue moyenne en
  pourcentage)** : l'erreur moyenne exprimée en pourcentage. Sert à juger la
  qualité du prix suggéré : une MAPE de 15 % signifie qu'en moyenne le prix
  proposé s'écarte de 15 % du prix réel.
- **k-NN (k Nearest Neighbors, k plus proches voisins)** : prédire à partir des
  *k* exemples les plus ressemblants, les « comparables ». Pour le prix, le système
  regarde par exemple les dix produits les plus proches et prend leur prix médian.

## Suggestion de prix (la cascade)

> Le prix n'est pas produit par un modèle « boîte noire » mais par une cascade de
> règles **déterministes** et lisibles, pour que le vendeur comprenne *pourquoi*
> tel prix lui est suggéré. Le système descend les niveaux du plus fiable au
> moins fiable et s'arrête au premier qui s'applique.

- **Cascade de pricing (niveaux L1 à L4, plus L1.5)** : la suite ordonnée des
  sources de prix.
  - **L1 (confiance haute)** : on connaît le prix catalogue réel du produit
    identifié. On applique une décote d'état puis une dépréciation liée à l'âge.
  - **L1.5 (confiance haute-moyenne)** : on ne dispose pas du prix catalogue mais
    l'IA a estimé un prix neuf de référence (l'« ancre IA », voir plus bas). On
    applique exactement la **même** décote déterministe. Seule l'ancre est une
    estimation ; la décote, elle, reste entièrement transparente. Ce niveau est
    placé **avant** les médianes de voisins parce que celles-ci sont souvent
    polluées (elles donnaient par exemple 6 € pour une montre qui en vaut 150).
  - **L2 (confiance moyenne)** : prix médian des dix produits voisins, quand on
    n'a ni catalogue ni ancre IA.
  - **L3 (confiance basse)** : on ne connaît que la catégorie ; on prend son prix
    médian.
  - **L4 (confiance très basse)** : produit et catégorie inconnus ; aucun prix
    n'est inventé. L'interface affiche « Prix à fixer (saisie manuelle) » plutôt
    qu'un trompeur « 0,00 € ».
- **Ancre IA (prix neuf de référence)** : le prix du produit **neuf**, estimé par
  l'identification raisonnée à partir des prix neufs propres des candidats réels
  (les accessoires et lots étant exclus du calcul). C'est cette ancre qui
  alimente le niveau L1.5. Affichée honnêtement au vendeur comme « Prix neuf
  estimé par IA », jamais comme un prix catalogue certain.
- **Décote d'état (multiplicateur)** : le facteur appliqué au prix neuf selon
  l'état déclaré : neuf 1,00 ; très bon état 0,75 ; bon état 0,55 ; correct
  0,35 ; pour pièces / hors service 0,15. Ce dernier état correspond à la
  valeur résiduelle d'un appareil hors service.
- **Dépréciation par âge** : la perte de valeur annuelle selon la catégorie
  (Electronics -15 %/an, téléphones -20 %/an, jeux vidéo -10 %/an, outillage
  -5 %/an). Si le vendeur n'a pas renseigné l'année d'achat, un âge de deux ans
  est supposé, et l'interface le signale.
- **Garde-fous de pricing** : trois protections contre les prix
  absurdes. (a) **Anti sous-évaluation** : une médiane de voisins qui s'effondre
  bien en dessous du prix neuf attendu décoté est relevée à un plancher. (b)
  **Cohérence du niveau L1** : si le prix catalogue du premier candidat est
  dérisoire face à l'ancre IA (signe d'un accessoire mal apparié, comme une coque
  à 43 $ rangée sous un iPhone à près de 600 $), on l'ignore et on bascule sur
  L1.5, ce qui évite d'afficher « iPhone à 15 € ». (c) **Prix catalogue
  aberrant** : un prix catalogue très au-dessus de la médiane des voisins (par
  exemple 9 755 $ pour un casque, faute de saisie) est traité comme une donnée
  corrompue et ignoré.

## Génération de la fiche (provenance et complétude)

> Au-delà du prix, l'assistant remplit une fiche produit structurée. Chaque champ
> porte sa **provenance** pour rester honnête, et la fiche se construit en cascade
> selon ce que l'on sait réellement, sur le même esprit que la cascade de prix.

- **Provenance d'un champ** : l'origine de chaque information affichée, en cinq
  catégories. *Observé* : lu sur la photo (le plus fiable pour cet objet précis).
  *Catalogue* : provient d'un produit du catalogue jugé correctement apparié.
  *Typique-à-vérifier* : imputé des voisins, donc non affirmé comme certain.
  *Catégorie* : déduit de la catégorie votée. *Vendeur* : saisi ou choisi par le
  vendeur (l'état, l'année d'achat). En cas de catalog-miss, les specs du mauvais
  candidat ne sont jamais présentées comme des faits.
- **Cascade de complétude (niveaux N1 à N3)** : le niveau de remplissage de la
  fiche. *N1_catalog* : match catalogue fiable, on dispose des specs du produit
  réel. *N2_category_photo* : pas de match fiable mais catégorie sûre, on combine
  photo, schéma de la catégorie et métadonnée vendeur. *N3_observed* : catégorie
  incertaine, on s'appuie sur le seul observé et le vendeur complète.
- **Complétude par catégorie fine** : la part des caractéristiques attendues qui
  sont effectivement remplies. Le dénominateur n'est plus le schéma générique de
  la macro-catégorie mais seulement les caractéristiques réellement pertinentes
  pour la **catégorie fine** du produit (présentes chez au moins un candidat de
  même catégorie fine). Une enceinte n'est ainsi plus pénalisée pour l'absence
  d'une « capacité » qui n'a pas de sens pour elle. L'état, étant un choix du
  vendeur toujours disponible, est exclu de ce calcul pour ne pas fausser le
  score. Sur le panel réel de mesure, la complétude moyenne mesurée est de 0,84
  (médiane 0,83).
- **Type de produit (catégorie de l'identifié)** : le type affiché sur la fiche
  est celui du produit finalement retenu (réordonné par l'identification
  raisonnée), et non le résultat brut du vote des voisins, qui pouvait être
  pollué (une coque faisait afficher « Basic Cases » pour un iPhone).

## MLOps : industrialiser les modèles

- **MLflow** : le « carnet de laboratoire » du projet. Il enregistre chaque
  entraînement de modèle : les réglages utilisés, les scores obtenus et le modèle
  produit. On peut ainsi comparer les versions et retrouver exactement comment un
  modèle a été fabriqué.
- **Run (exécution)** : une session d'entraînement tracée dans le carnet de
  laboratoire, avec ses réglages et ses résultats.
- **Model Registry (registre des modèles)** : l'étagère où sont rangés les modèles
  et toutes leurs versions successives.
- **Alias @Production** : une étiquette posée sur le modèle effectivement utilisé
  par l'application. Pour changer de modèle en production, on déplace simplement
  cette étiquette d'une version à une autre, sans toucher au code.
- **Champion et challenger** : le « champion » est le modèle en place ; le
  « challenger » est un candidat qui cherche à le remplacer. On ne remplace le
  champion que si le challenger fait mieux d'une marge minimale fixée d'avance, ce
  qui évite de changer pour un gain insignifiant.
- **DAG (Directed Acyclic Graph, graphe orienté sans cycle)** : un graphe de
  tâches enchaînées dans un ordre précis, où chaque tâche attend que ses
  dépendances soient finies. C'est ainsi que sont décrites les chaînes de
  ré-entraînement automatique.
- **Airflow** : le planificateur qui exécute ces chaînes de tâches au bon moment,
  par exemple pour relancer un entraînement automatiquement.
- **Drift (dérive)** : le moment où les données récentes ne ressemblent plus à
  celles sur lesquelles le modèle a été entraîné. Le modèle risque alors de se
  dégrader, et il faut le ré-entraîner.
- **PSI, KS, Chi²** : trois tests statistiques qui mesurent l'ampleur de la dérive
  d'une variable entre deux périodes. PSI (Population Stability Index) compare des
  distributions, KS (Kolmogorov-Smirnov) compare des variables numériques, Chi²
  (khi-deux) compare des variables de catégorie.
- **Evidently** : l'outil qui compare deux jeux de données (l'ancien de référence
  et le récent) et produit un rapport visuel de dérive. Dans le projet, une alerte
  se déclenche quand au moins la moitié des variables surveillées ont dérivé.
- **DVC (Data Version Control)** : un outil qui versionne les *données*, comme un
  gestionnaire de versions le fait pour le code. On peut ainsi retrouver l'état
  exact des données utilisées à une date donnée.
- **BentoML** : un outil qui empaquette un modèle entraîné pour le servir comme un
  service web accessible par d'autres programmes.

## Observabilité et infrastructure

- **Quatre golden signals (quatre signaux d'or)** : les quatre mesures de santé
  d'un service informatique : la latence (le temps de réponse), le trafic (le
  nombre de requêtes), les erreurs (le taux d'échecs) et la saturation (le niveau
  de remplissage des ressources).
- **Percentile p95** : la valeur sous laquelle tombent 95 % des cas. Pour un temps
  de réponse, le p95 indique que 95 % des requêtes sont plus rapides que cette
  valeur. C'est plus honnête que la moyenne, car la moyenne masque les pires cas.
- **Prometheus et Grafana** : deux outils complémentaires. Prometheus collecte en
  continu les mesures du service ; Grafana les affiche sous forme de tableaux de
  bord lisibles.
- **structlog** : une bibliothèque qui écrit les journaux d'activité dans un
  format lisible par une machine (le format JSON, une structure clé-valeur)
  plutôt qu'en texte libre, ce qui facilite leur recherche et leur tri.
- **Logs métier (observabilité du pipeline)** : en plus des mesures techniques
  collectées par Prometheus, le système écrit, à chaque requête, des journaux
  structurés qui racontent ce que le pipeline a réellement fait. Le journal
  `identify_done` consigne par exemple l'issue de l'identification, le nombre de
  candidats, le score du premier, la catégorie fine et sa confiance, le fait que
  l'identification raisonnée a été utilisée, qu'il y a eu réordonnancement, un
  catalog-miss, le prix neuf estimé, la question posée, la complétude et les temps
  des appels d'IA ; le journal `price_done` consigne le niveau de cascade
  réellement atteint, la méthode, le prix suggéré et la présence d'une ancre IA.
  On peut ainsi *lire* directement le comportement du système (taux de
  catalog-miss, usage du niveau L1.5, répartition de la latence) au lieu de s'en
  remettre à des anecdotes.
- **request_id (identifiant de requête)** : un identifiant unique attribué à
  chaque requête entrante. Il permet de retrouver tous les journaux d'une même
  requête, du début à la fin, même quand plusieurs requêtes se mêlent.
- **Pushgateway (passerelle de poussée)** : un intermédiaire où les tâches
  ponctuelles, qui ne tournent pas en permanence, déposent leurs mesures.
  Prometheus vient ensuite les y récupérer.
- **Docker et conteneur** : un conteneur empaquette une application avec tout ce
  dont elle a besoin pour fonctionner (ses dépendances, sa configuration), de
  sorte qu'elle s'exécute de la même manière partout. Docker est l'outil qui crée
  et lance ces conteneurs.
- **Build multi-stage (construction en plusieurs étapes)** : construire le
  conteneur dans une image « atelier » bien équipée, puis ne conserver dans
  l'image finale que le strict nécessaire. Le résultat est plus léger et plus sûr.
- **Docker Compose** : un outil qui lance plusieurs conteneurs ensemble, reliés
  entre eux, à partir d'une seule commande.
- **Kubernetes (k8s)** : un orchestrateur qui déploie et met à l'échelle des
  conteneurs en production. Ses objets principaux sont : le Deployment (pour une
  application sans état, dont on peut multiplier les copies), le StatefulSet (pour
  une application avec état, comme une base de données), l'Ingress (qui aiguille le
  trafic entrant vers le bon service) et le HPA (Horizontal Pod Autoscaler, qui
  ajoute ou retire automatiquement des copies selon la charge).

## Qualité et sécurité

- **CI/CD (Continuous Integration / Continuous Delivery)** : deux automatisations.
  L'intégration continue (CI) re-teste le projet à chaque modification du code ;
  la livraison continue (CD) le publie automatiquement quand les tests passent.
- **GHCR (GitHub Container Registry)** : le dépôt en ligne de GitHub où sont
  stockées les images de conteneurs du projet.
- **SAST et SCA** : deux analyses de sécurité complémentaires. Le SAST (Static
  Application Security Testing) examine le *code* écrit ; le SCA (Software
  Composition Analysis) audite les *bibliothèques externes* utilisées.
- **pip-audit** : un outil qui scanne les bibliothèques Python du projet à la
  recherche de failles de sécurité déjà connues et répertoriées (les CVE, Common
  Vulnerabilities and Exposures).
- **JWT (JSON Web Token)** : un jeton signé qui prouve qu'un utilisateur est bien
  authentifié, sans avoir à redemander son mot de passe à chaque requête. Le
  projet le signe avec l'algorithme HS256.
- **bcrypt** : un algorithme qui transforme un mot de passe en empreinte
  irréversible (un « hachage »), de sorte que le mot de passe en clair n'est jamais
  stocké. Le projet utilise un coût de 12, un réglage qui rend le craquage
  volontairement lent.
- **Path-traversal (traversée de répertoire)** : une attaque qui tente de sortir
  du dossier autorisé pour atteindre d'autres fichiers, par exemple en utilisant
  des chemins du type `../../`. Le projet bloque ces tentatives en vérifiant la
  forme exacte des identifiants de fichiers.
- **Capability-URL (URL-capacité)** : une adresse web imprévisible, fondée sur un
  identifiant tiré au hasard (un uuid4, impossible à deviner), qui sert elle-même
  de « clé » d'accès à une ressource. Connaître l'URL suffit à y accéder, mais on
  ne peut pas la deviner. C'est ainsi que les photos déposées par les vendeurs
  sont rendues consultables sans exposer tout le contenu.

## Explicabilité (comprendre les décisions du modèle)

- **SHAP (SHapley Additive exPlanations)** : une méthode qui explique *quelles
  caractéristiques* ont poussé un modèle vers une prédiction donnée. Elle s'appuie
  sur les valeurs de Shapley, un principe issu de la théorie des jeux qui répartit
  équitablement la contribution de chaque caractéristique au résultat.
- **t-SNE et UMAP** : deux techniques qui projettent des vecteurs à très haute
  dimension sur un plan en deux dimensions, afin de *voir* d'un coup d'œil si les
  produits d'une même catégorie se regroupent bien ensemble.
- **Model Card (fiche de modèle)** : la fiche d'identité d'un modèle. Elle résume
  son usage prévu, les données qui l'ont entraîné, ses performances mesurées et ses
  limites connues.

## Conventions de code (la méthode du projet)

- **lazy loading (chargement paresseux)** : ne charger une ressource lourde (un
  gros modèle, une grosse bibliothèque) qu'au moment de sa première utilisation,
  et pas avant. Cela accélère le démarrage et économise la mémoire.
- **idempotent** : se dit d'une opération que l'on peut relancer sans danger,
  parce qu'elle ne refait pas le travail déjà accompli. Si un résultat existe
  déjà, l'étape est simplement sautée, ce qui permet de reprendre un traitement
  interrompu.
- **best-effort / fail-soft (au mieux / échec en douceur)** : si un composant
  secondaire échoue (par exemple la vérification visuelle de la photo), le système
  continue sans casser l'ensemble du flux. La fonction concernée est un bonus, pas
  un point de blocage.
