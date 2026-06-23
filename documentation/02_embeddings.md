# 02 — Représentations vectorielles (embeddings)

> Transformer un texte (ou une image) en une liste de nombres pour **comparer des produits
> par leur *sens***, pas par leurs mots exacts. C'est la fondation de toute la recherche.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)

Un ordinateur ne « comprend » pas le mot *iPhone*. Pour qu'il puisse comparer des produits, on
transforme chaque texte en une **liste de nombres** appelée **embedding** (ou *vecteur*). L'idée
géniale: ces nombres sont calculés de façon à ce que **deux textes de sens proche aient des
listes de nombres proches**.

Exemple concret:
- « smartphone Apple 128 Go débloqué »
- « iPhone 128GB unlocked »

Ces deux phrases n'ont presque **aucun mot en commun**, mais elles veulent dire la même chose.
Une recherche par mots-clés (« est-ce que le mot *iPhone* est présent ? ») échouerait. Les
embeddings, eux, donnent à ces deux phrases des vecteurs **très proches** → on retrouve le bon
produit même si le vendeur ne l'a pas écrit exactement comme le catalogue.

### Comment on mesure « proche »

Un vecteur, géométriquement, c'est une **flèche** dans un espace (sauf qu'ici l'espace a 1024
dimensions, impossible à dessiner — mais les maths fonctionnent pareil qu'en 2D). Pour dire si
deux flèches « pointent dans la même direction », on mesure **l'angle** entre elles: c'est la
**similarité cosinus**.
- angle ≈ 0° → cosinus ≈ 1 → même sens (très similaire),
- angle = 90° → cosinus = 0 → sans rapport,
- angle = 180° → cosinus = −1 → opposé.

On regarde **l'angle, pas la longueur**: un texte long et un texte court qui parlent du même
produit doivent être jugés similaires. La longueur ne doit pas compter, seulement la direction
(= le sens).

### Pour l'expert (le détail qui compte)

- **Normalisation L2** = ramener toutes les flèches à la **longueur 1** (les poser sur une
 *sphère unité*). Une fois normalisés, deux calculs deviennent équivalents:
 - `cosinus(a, b) = a · b` (produit scalaire) — plus de division par les normes,
 - et il existe l'identité **`‖a − b‖² = 2 − 2·cos(a, b)`**: sur des vecteurs normalisés,
 **trier par distance euclidienne croissante = trier par cosinus décroissant**. Conséquence
 pratique: on peut indexer avec FAISS en *inner product* ou en *L2*, le classement est le
 même. C'est exactement ce qui permet de choisir l'index par performance sans changer la
 sémantique (cf. rapport *Retrieval*).

---

## 2. État de l'art

- Les modèles d'embedding modernes produisent des vecteurs où la **similarité cosinus** reflète
 la proximité de sens. C'est la métrique **par défaut** en recherche sémantique, car robuste au
 bruit « ce texte est plus long ».
- **Normaliser systématiquement** est une règle d'hygiène : si une base vectorielle est configurée
 pour le cosinus mais reçoit des vecteurs non normalisés de façon incohérente, les scores
 deviennent faux et le rappel « dérive » silencieusement.
- Les modèles **contrastifs** (CLIP, SimCLR, familles *sentence-transformers*) normalisent
 pendant l'entraînement → pas d'ambiguïté.
- **Débat actuel** (arXiv 24, *« Is cosine-similarity really about similarity? »*): le
 cosinus peut être trompeur si les embeddings ne sont pas correctement régularisés/normalisés —
 raison de plus de traiter la normalisation comme un **contrat**, pas une option.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### Le modèle choisi
- **`Snowflake/snowflake-arctic-embed-l-v2.0`** (`src/encoders/01_text_arctic.py`).
- Architecture: **XLM-RoBERTa-large**, **multilingue** (important: nos vendeurs écrivent en
 français, le catalogue est en anglais).
- **1024 dimensions** de sortie, contexte max 8192 tokens, licence Apache 2.0.
- **Gelé** (pas de fine-tuning) — on utilise un excellent encodeur généraliste tel quel
 (choix assumé, cf. rapport *Classification* et critique ci-dessous).

### Ce qu'on encode
- L'entrée d'un produit = **`title` + `description`** concaténés (`_build_input_text`).

### Les choix d'ingénierie (et leur justification chiffrée)
| Paramètre | Valeur | Pourquoi (mesuré / raisonné) |
|---|---|---|
| `BATCH_SIZE` | **128** | tient sur une RTX 4080 16 Go en FP16 avec XLM-R-large |
| `MAX_SEQ_LENGTH` | **256 tokens** | les textes font ~55 tokens en médiane (title ~30 + desc ~25); 256 couvre le p99. L'attention est en **O(seq²)** → passer de 512 à 256 = **~4× plus rapide** sans perte utile |
| `normalize_embeddings` | **True** | normalisation L2 *built-in* → contrat cosinus respecté dès la source |
| `dtype` sortie | **float16** | ~**2× moins de disque** que float32, perte négligeable pour du retrieval |
| Stockage | **`.npy` en mmap** | 4,5 M × 1024 × 2 octets ≈ **9 Go**: on ne charge jamais tout en RAM, on *mappe* le fichier |
| Re-runs | **idempotents** | si le `.npy` d'un split existe déjà → skip (on ne recalcule pas 9 Go pour rien) |

### Les sorties
- `data/embeddings/text/text_arctic_{train,val,test}.npy` (un fichier par split).
- `data/embeddings/text_index_v1.parquet`: le **mapping** `parent_asin → row_id` (global +
 par split). C'est lui qui permet aux modules aval (FAISS) de retrouver *quel vecteur*
 correspond à *quel produit*.

### La boîte à outils mathématique (`src/encoders/similarity_utils.py`)
Un module **unique** (source de vérité) avec 5 fonctions *sans état* qui **ne mutent jamais**
les entrées:
- `l2_normalize` — avec un **garde-fou** : si une norme est < `eps` (1e-12), on renvoie un
 **vecteur nul** plutôt qu'un `NaN` qui se propagerait en silence (un vecteur nul signale un bug
 amont — padding, embedding non initialisé — à logguer en prod).
- `cosine_similarity`, `inner_product`, `l2_distance` (avec l'identité `‖a−b‖² = 2 − 2·a·b`
 pour le calcul *pairwise* efficace), `top_k_similar` (recherche directe sans FAISS pour
 < 100k vecteurs).

> **Note d'efficacité (expert)**: pour le retrieval, on **pré-normalise tout UNE FOIS** puis on
> utilise l'*inner product* (FAISS `METRIC_INNER_PRODUCT`) — c'est mathématiquement le cosinus,
> mais sans recalculer les normes à chaque requête.

---

## 4. Résultats (mesurés, vérifiables)

| Indicateur | Valeur | Ce que ça veut dire |
|---|---|---|
| Dimension des vecteurs | **1024** | richesse de représentation d'Arctic |
| Tests d'invariants maths | **22 tests verts** | norme = 1 après normalisation, cosinus ∈ [−1, 1], symétrie, équivalence cosinus = produit scalaire après normalisation, garde-fou zéro-norme |
| Effet de la traduction FR→EN | score **0,556 → 0,641** (+0,085) | une **requête française traduite en anglais** avant la recherche gagne nettement en pertinence — finding qui a justifié l'étape de traduction du pipeline |
| Stockage | FP16 + mmap | ~9 Go non chargés en RAM |

> 📊 **Chiffres slide**: « vecteurs 1024-dim, multilingue (XLM-RoBERTa) », « +0,085 de score
> grâce à la traduction FR→EN », « 22 tests d'invariants mathématiques », « FP16 + mmap: 9 Go
> jamais chargés en RAM ». 📸 **Capture**: la visualisation t-SNE du notebook
> `notebooks/03_embeddings_concept.ipynb` (nuage de points où les catégories se regroupent
> visuellement = **preuve que les embeddings capturent le sens**).

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ Normalisation L2 **systématique avec garde-fou** → exactement la bonne pratique
 « traiter la normalisation comme un contrat ».
- ✅ Similarité cosinus + équivalence IP/L2 maîtrisée → choix d'index libre côté retrieval.
- ✅ Modèle **multilingue moderne** (Arctic/XLM-R), normalisation native.
- ✅ **Invariants mathématiques testés** (rare et rassurant — on prouve que la brique de base
 est correcte avant de bâtir dessus).
- ✅ Ingénierie soignée: FP16, mmap, max_seq calibré sur la distribution réelle des tokens,
 re-runs idempotents.

**Limites assumées:**
- **Encodeur gelé, non spécialisé** sur notre domaine (occasion high-tech). Un *fine-tuning
 contrastif* sur nos paires (requête vendeur ↔ produit catalogue) pourrait gagner quelques
 points de rappel — non fait (coût d'entraînement vs gain non démontré; et le retrieval ancré
 fait déjà l'essentiel du travail).
- **Le multilingue n'est pas parfait en FR**: on mesure que l'anglais marche mieux, d'où la
 **traduction des requêtes** avant recherche. C'est un contournement efficace (+0,085) mais
 c'est un contournement, pas une élégance.
- **Branche image (SigLIP)**: l'indexation visuelle directe du catalogue reste *gated* (cf.
 rapports *Retrieval* et *VLM/LLM*); aujourd'hui l'entrée photo passe par une lecture VLM →
 texte → embedding texte.

---

## 6. Références
- Snowflake — Arctic Embed L v2 (modèle utilisé) — https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0
- Medium (Codastra) — *The math behind good embeddings: cosine similarity, norms* — https://medium.com/@2nick2patel2/the-math-behind-good-embeddings-cosine-similarity-norms-and-why-your-vectors-drift-over-time-433ff315b2a5
- PyImageSearch — *TF-IDF vs. Embeddings: from keywords to semantic search* — https://pyimagesearch.com/2026/02/09/tf-idf-vs-embeddings-from-keywords-to-semantic-search/
- arXiv 2403.05440 — *Is cosine-similarity of embeddings really about similarity?* — https://arxiv.org/html/2403.05440v1
- Dataquest — *Measuring similarity and distance between embeddings* — https://www.dataquest.io/blog/measuring-similarity-and-distance-between-embeddings/

---

### En une phrase (pour la défense)
*« Chaque produit devient un vecteur de 1024 nombres via un encodeur multilingue gelé (Arctic
Embed / XLM-RoBERTa), normalisé L2 pour que seule compte la proximité de sens (cosinus). On
encode en FP16 avec un max_seq calibré sur la distribution réelle des tokens (256, ~4× plus
rapide que 512), on stocke en mmap pour ne pas saturer la RAM, et on a 22 tests qui prouvent
les invariants mathématiques. Mesure clé: traduire les requêtes FR→EN avant la recherche
améliore la pertinence de +0,085. »*

---

> *Ce rapport sert de modèle de profondeur pour les autres : un débutant suit le raisonnement
> de bout en bout, un expert y trouve les paramètres exacts, les justifications chiffrées et les
> identités mathématiques.*
