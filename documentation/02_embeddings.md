# 02 - Représentations vectorielles (embeddings)

> Transformer un texte (ou une image) en une liste de nombres pour comparer des produits par
> leur **sens**, et non par leurs mots exacts. C'est la fondation de toute la recherche de
> produits du projet.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre (en partant de zéro)

Un ordinateur ne « comprend » pas le mot *iPhone* comme un humain. Pour qu'il puisse comparer
des produits entre eux, on transforme chaque texte en une **liste de nombres** appelée
**embedding** (on dit aussi *vecteur*). L'idée centrale est la suivante : ces nombres sont
calculés de façon à ce que **deux textes de sens proche obtiennent des listes de nombres
proches**.

Exemple concret, voici deux annonces qui décrivent le même produit :

- « smartphone Apple 128 Go débloqué »
- « iPhone 128GB unlocked »

Ces deux phrases n'ont presque **aucun mot en commun**, mais elles veulent dire la même chose.
Une recherche par mots-clés (qui se contente de vérifier « est-ce que le mot *iPhone* est
présent ? ») échouerait. Les embeddings, eux, donnent à ces deux phrases des vecteurs **très
proches**. On retrouve donc le bon produit même si le vendeur ne l'a pas écrit exactement comme
le catalogue.

### Comment on mesure « proche »

Un vecteur, vu géométriquement, c'est une **flèche** dans un espace. Ici l'espace a 1024
dimensions, ce qui est impossible à dessiner, mais les mathématiques fonctionnent exactement
comme en deux dimensions. Pour décider si deux flèches « pointent dans la même direction », on
mesure **l'angle** entre elles. Cette mesure s'appelle la **similarité cosinus** (le cosinus est
une opération de trigonométrie qui donne un nombre entre -1 et 1 à partir d'un angle) :

- angle proche de 0 degré, cosinus proche de 1, les deux textes ont le même sens (très similaires),
- angle de 90 degrés, cosinus égal à 0, les deux textes n'ont aucun rapport,
- angle de 180 degrés, cosinus égal à -1, les deux textes sont opposés.

Point important : on regarde **l'angle, pas la longueur** de la flèche. Un texte long et un texte
court qui parlent du même produit doivent être jugés similaires. La longueur du texte ne doit pas
compter, seule la direction compte (c'est-à-dire le sens).

### Pour l'expert (le détail qui compte)

La **normalisation L2** consiste à ramener toutes les flèches à la **longueur 1** (on les pose
toutes sur une *sphère unité*, c'est-à-dire une boule de rayon 1). Une fois les vecteurs
normalisés de cette manière, deux calculs deviennent équivalents :

- la similarité cosinus se réduit à un simple **produit scalaire** (`cosinus(a, b) = a · b`,
  c'est-à-dire la somme des produits coordonnée par coordonnée), il n'y a plus besoin de diviser
  par les longueurs des vecteurs,
- il existe de plus l'identité mathématique `‖a - b‖² = 2 - 2·cos(a, b)` (où `‖a - b‖` désigne la
  distance en ligne droite entre les deux flèches). Sur des vecteurs normalisés, **trier par
  distance croissante revient exactement à trier par cosinus décroissant**.

La conséquence pratique est précieuse : on peut ranger les vecteurs dans une base de recherche en
utilisant soit le produit scalaire, soit la distance en ligne droite, le **classement des
résultats sera identique**. On choisit donc la méthode la plus rapide sans jamais changer le sens
du résultat.

---

## 2. État de l'art

- Les modèles d'embedding modernes produisent des vecteurs où la **similarité cosinus** reflète
  la proximité de sens. C'est la mesure utilisée **par défaut** en recherche sémantique (la
  recherche qui s'appuie sur le sens plutôt que sur les mots exacts), car elle est robuste au
  biais « ce texte est plus long ».
- **Normaliser systématiquement les vecteurs** est une règle d'hygiène de base. Si une base de
  recherche est réglée pour le cosinus mais reçoit des vecteurs non normalisés de façon
  incohérente, les scores deviennent faux et la qualité de la recherche se dégrade lentement, sans
  message d'erreur visible.
- Les modèles dits **contrastifs** (une famille de modèles entraînés à rapprocher ce qui se
  ressemble et à éloigner ce qui diffère, dont CLIP, SimCLR et la famille des
  *sentence-transformers*) normalisent déjà leurs vecteurs pendant l'entraînement, ce qui supprime
  toute ambiguïté.
- Un **débat scientifique récent** (article de 2024 intitulé *« Is cosine-similarity really about
  similarity? »*) montre que le cosinus peut être trompeur si les vecteurs ne sont pas correctement
  régularisés ni normalisés. C'est une raison de plus de traiter la normalisation comme une
  **obligation systématique**, et non comme une option facultative.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### Le modèle choisi

- Nous utilisons le modèle **`Snowflake/snowflake-arctic-embed-l-v2.0`**, mis en oeuvre dans le
  fichier `src/encoders/01_text_arctic.py`.
- Son architecture interne est **XLM-RoBERTa-large**, un grand réseau de neurones **multilingue**.
  Ce point est essentiel pour notre cas : nos vendeurs écrivent leurs annonces en français, alors
  que le catalogue de référence est en anglais. Un modèle multilingue sait rapprocher les deux.
- Il produit des vecteurs de **1024 dimensions** (donc 1024 nombres par produit). Il accepte des
  textes très longs (jusqu'à 8192 *tokens*, un *token* étant un morceau de mot, environ trois
  quarts d'un mot anglais). Sa licence est Apache 2.0, ce qui autorise un usage libre, y compris
  commercial.
- Le modèle est utilisé **gelé**, c'est-à-dire sans réentraînement sur nos données. On se sert
  d'un excellent encodeur généraliste tel quel. C'est un choix assumé, dont les limites sont
  discutées en partie 5.

### Ce qu'on encode

Pour chaque produit, le texte d'entrée est la **concaténation du titre et de la description**
(le titre suivi de la description, dans la fonction `_build_input_text`). Si l'un des deux est
absent, on prend simplement ce qui existe.

### Les choix d'ingénierie (et leur justification chiffrée)

| Paramètre | Valeur | Pourquoi (mesuré ou raisonné) |
|---|---|---|
| Taille des lots (`BATCH_SIZE`) | **128** | On encode les produits par paquets de 128 pour aller vite. Ce nombre tient dans la mémoire d'une carte graphique RTX 4080 de 16 Go en demi-précision avec ce grand modèle. |
| Longueur de texte max (`MAX_SEQ_LENGTH`) | **256 tokens** | Nos textes mesurent environ 55 tokens en médiane (un titre d'environ 30 tokens plus une description d'environ 25). La limite de 256 couvre donc 99 % des cas. Or le coût de calcul du modèle augmente comme le **carré** de la longueur du texte : passer de 512 à 256 rend l'encodage **environ 4 fois plus rapide** sans perte utile. |
| Normalisation (`normalize_embeddings`) | **activée** | Le modèle normalise lui-même chaque vecteur à la longueur 1 dès la sortie. La règle du cosinus est ainsi respectée à la source, sans étape supplémentaire. |
| Type des nombres en sortie | **float16** (demi-précision) | Chaque nombre est stocké sur 16 bits au lieu de 32. Cela divise par environ **2 la place sur le disque**, avec une perte de précision négligeable pour de la recherche. |
| Stockage sur disque | **fichier `.npy` lu en *mmap*** | Le *mmap* est une technique qui laisse le fichier sur le disque et n'en lit que les morceaux nécessaires. Pour 4,5 millions de produits, soit 4,5 M × 1024 nombres × 2 octets, le total atteint **environ 9 Go** : on ne charge jamais ces 9 Go en mémoire vive d'un coup. |
| Re-exécutions | **sans recalcul inutile** | Si le fichier de vecteurs d'un sous-ensemble existe déjà, on le saute. On ne recalcule pas 9 Go pour rien. |

### Les sorties produites

- Trois fichiers de vecteurs, un par sous-ensemble de données :
  `data/embeddings/text/text_arctic_train.npy`, `text_arctic_val.npy` et `text_arctic_test.npy`
  (les données sont découpées en trois : un ensemble d'entraînement, un de validation et un de
  test).
- Un fichier `data/embeddings/text_index_v1.parquet` qui contient la **table de correspondance**
  entre l'identifiant unique d'un produit (`parent_asin`) et son numéro de ligne dans les fichiers
  de vecteurs. C'est cette table qui permet, plus tard, de retrouver **quel vecteur correspond à
  quel produit**.

### La boîte à outils mathématique (`src/encoders/similarity_utils.py`)

Toutes les opérations sur les vecteurs sont regroupées dans un **module unique**, qui sert de
référence pour tout le reste du projet. Ses fonctions ne gardent aucune mémoire entre deux appels
et **ne modifient jamais les données qu'on leur donne** (elles renvoient toujours une copie). On
y trouve cinq fonctions :

- `l2_normalize` ramène un vecteur à la longueur 1. Elle inclut un **garde-fou** : si la longueur
  d'un vecteur est inférieure à un très petit seuil (`eps`, fixé à 1e-12, soit 0,000000000001),
  la fonction renvoie un **vecteur nul** plutôt qu'un résultat invalide qui se propagerait
  silencieusement (un résultat invalide vient d'une division par zéro). Un vecteur nul est un
  signal clair indiquant un problème en amont, par exemple un texte vide ou un vecteur jamais
  rempli, à surveiller en production.
- `cosine_similarity` calcule la similarité cosinus entre vecteurs.
- `inner_product` calcule le produit scalaire (équivalent au cosinus une fois les vecteurs
  normalisés).
- `l2_distance` calcule la distance en ligne droite entre vecteurs, en s'appuyant sur l'identité
  `‖a - b‖² = 2 - 2·a·b` pour les calculs de masse efficaces.
- `top_k_similar` retrouve directement les voisins les plus proches d'un vecteur. Elle convient
  aux recherches de petite taille (moins de 100 000 vecteurs) sans avoir besoin d'un moteur de
  recherche spécialisé.

> **Note d'efficacité (pour l'expert)** : pour la recherche de masse, on **normalise tous les
> vecteurs une seule fois** au départ, puis on utilise uniquement le produit scalaire. C'est
> mathématiquement identique au cosinus, mais on évite de recalculer les longueurs des vecteurs à
> chaque requête.

---

## 4. Résultats (mesurés et vérifiables)

| Indicateur | Valeur | Ce que ça veut dire |
|---|---|---|
| Dimension des vecteurs | **1024** | Chaque produit est résumé par 1024 nombres, ce qui offre une représentation riche de son sens. |
| Tests des propriétés mathématiques | **22 tests réussis** | On vérifie automatiquement que la longueur vaut bien 1 après normalisation, que le cosinus reste entre -1 et 1, que la mesure est symétrique (a comparé à b donne le même résultat que b comparé à a), que cosinus et produit scalaire coïncident après normalisation, et que le garde-fou du vecteur nul fonctionne. |
| Effet de la traduction du français vers l'anglais | score **0,556 → 0,641 (gain de +0,085)** | Quand une requête écrite en français est d'abord **traduite en anglais** avant la recherche, la pertinence des résultats progresse nettement. Ce constat a justifié l'ajout d'une étape de traduction dans la chaîne de traitement. |
| Stockage | demi-précision plus lecture *mmap* | Environ 9 Go de vecteurs qui restent sur le disque et ne saturent jamais la mémoire vive. |

> 📊 **Chiffres pour la présentation** : « vecteurs de 1024 dimensions, modèle multilingue
> (XLM-RoBERTa) », « gain de +0,085 de score grâce à la traduction du français vers l'anglais »,
> « 22 tests des propriétés mathématiques réussis », « demi-précision plus lecture *mmap* : 9 Go
> jamais chargés en mémoire vive ».
> 📸 **Capture à montrer** : la visualisation du notebook
> `notebooks/03_embeddings_concept.ipynb`. Il s'agit d'un nuage de points (obtenu par une méthode
> nommée t-SNE, qui projette les vecteurs de 1024 dimensions sur un plan visible). Les produits
> d'une même catégorie s'y regroupent visuellement, ce qui **prouve que les embeddings capturent
> bien le sens**.

---

## 5. Critique (état de l'art comparé à notre travail)

**Ce qui est solide :**

- ✅ La normalisation à la longueur 1 est **systématique et protégée par un garde-fou**, ce qui
  correspond exactement à la bonne pratique « traiter la normalisation comme une obligation ».
- ✅ La similarité cosinus et son équivalence avec le produit scalaire et la distance en ligne
  droite sont maîtrisées, ce qui laisse libre le choix de la méthode de rangement la plus rapide.
- ✅ Le modèle est **multilingue et moderne** (Arctic / XLM-RoBERTa), avec normalisation native.
- ✅ Les **propriétés mathématiques sont testées automatiquement**, ce qui est rare et rassurant :
  on prouve que la brique de base est correcte avant de construire dessus.
- ✅ L'ingénierie est soignée : demi-précision, lecture *mmap*, longueur de texte calibrée sur la
  distribution réelle des textes, re-exécutions sans recalcul inutile.

**Limites assumées :**

- **L'encodeur est gelé et non spécialisé** sur notre domaine (le matériel électronique
  d'occasion). Un réentraînement ciblé sur nos paires (requête de vendeur associée au produit du
  catalogue) pourrait gagner quelques points de pertinence. Nous ne l'avons pas fait : le coût
  d'entraînement n'est pas justifié par un gain démontré, et l'étape de recherche fournit déjà
  l'essentiel du travail.
- **Le multilingue n'est pas parfait en français.** Nos mesures montrent que l'anglais fonctionne
  mieux, d'où la traduction des requêtes du français vers l'anglais avant la recherche. C'est un
  contournement efficace (gain de +0,085), mais cela reste un contournement plutôt qu'une solution
  élégante.
- **La branche image n'est pas encore activée pour l'indexation directe.** Indexer visuellement le
  catalogue entier supposerait un modèle d'image dont l'accès reste restreint pour l'instant.
  Aujourd'hui, une entrée par photo passe d'abord par une lecture automatique de l'image qui
  produit du texte, puis ce texte est transformé en vecteur. La photo n'est donc pas comparée
  directement, elle est d'abord décrite en mots.

---

## 6. Références

- Snowflake, Arctic Embed L v2 (le modèle utilisé) : https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0
- Medium (Codastra), *The math behind good embeddings: cosine similarity, norms* : https://medium.com/@2nick2patel2/the-math-behind-good-embeddings-cosine-similarity-norms-and-why-your-vectors-drift-over-time-433ff315b2a5
- PyImageSearch, *TF-IDF vs. Embeddings: from keywords to semantic search* : https://pyimagesearch.com/2026/02/09/tf-idf-vs-embeddings-from-keywords-to-semantic-search/
- arXiv 2403.05440, *Is cosine-similarity of embeddings really about similarity?* : https://arxiv.org/html/2403.05440v1
- Dataquest, *Measuring similarity and distance between embeddings* : https://www.dataquest.io/blog/measuring-similarity-and-distance-between-embeddings/

---

### En une phrase (pour la défense)

*« Chaque produit devient un vecteur de 1024 nombres grâce à un encodeur multilingue gelé (Arctic
Embed, fondé sur XLM-RoBERTa), normalisé à la longueur 1 pour que seule compte la proximité de
sens mesurée par le cosinus. On encode en demi-précision avec une longueur de texte calibrée sur
la distribution réelle (256 tokens, environ 4 fois plus rapide que 512), on stocke en lecture
*mmap* pour ne pas saturer la mémoire vive, et 22 tests prouvent les propriétés mathématiques de
base. Mesure clé : traduire les requêtes du français vers l'anglais avant la recherche améliore la
pertinence de +0,085. »*

---

> *Ce document sert de modèle de profondeur pour les autres : un débutant suit le raisonnement de
> bout en bout, un expert y trouve les paramètres exacts, les justifications chiffrées et les
> identités mathématiques.*
