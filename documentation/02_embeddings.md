# 02 — Représentations vectorielles (embeddings)

> Comment on transforme un texte (ou une image) en une liste de nombres pour pouvoir
> **comparer** des produits par leur *sens*, pas par leurs mots exacts.

---

## 1. La technologie : qu'est-ce que c'est ?

Un **embedding** est une **liste de nombres** (un « vecteur ») qui résume le sens d'un texte
ou d'une image. Deux contenus proches par le sens ont des vecteurs proches dans l'espace.

Exemple : « smartphone Apple 128 Go » et « iPhone 128GB » s'écrivent différemment mais
veulent dire presque la même chose → leurs vecteurs seront proches. Une simple recherche
par mots-clés raterait le lien ; les embeddings le capturent.

Pour mesurer « à quel point deux vecteurs se ressemblent », on utilise la **similarité
cosinus** : on regarde l'**angle** entre les deux vecteurs (pas leur longueur). Angle
petit = sens proche.

---

## 2. État de l'art

- Les modèles modernes produisent des vecteurs où la **similarité cosinus** correspond à la
  proximité de sens. C'est la métrique par défaut en recherche sémantique car elle est
  robuste au « ce texte est plus long » (la longueur ne doit pas compter, seul le sens).
- **Normalisation L2** : on divise chaque vecteur par sa longueur pour qu'ils aient tous la
  **même taille** (ils « posent sur une sphère unité »). Avantage : une fois normalisés,
  cosinus = simple produit scalaire (plus rapide, cohérent).
- **Bonne pratique** : *normaliser systématiquement*. Si une base vectorielle attend du
  cosinus mais reçoit des vecteurs non normalisés, les scores deviennent faux et le rappel
  « dérive ». Les modèles type CLIP / sentence-transformers normalisent par construction.

---

## 3. Notre implémentation

| Brique | Fichier | Rôle |
|---|---|---|
| Encodeur **texte** | `src/encoders/01_text_arctic.py` | **Snowflake Arctic Embed L v2**, 1024 dimensions, **multilingue**, normalisé L2 |
| Encodeur **image** | `src/encoders/02_vision_siglip.py` | SigLIP (vision) — *gated* (voir thème retrieval/limites) |
| Construction des index | `src/encoders/03_build_indices.py` | produit les fichiers de vecteurs pour la recherche |
| Boîte à outils maths | `src/encoders/similarity_utils.py` | `l2_normalize`, `cosine_similarity`, `inner_product`, `l2_distance`, `top_k_similar` |

Choix structurants :
- **Modèle pré-entraîné gelé** (Arctic) : on ne ré-entraîne pas l'encodeur, on l'utilise tel
  quel. C'est l'usage standard et économe : un bon encodeur généraliste suffit pour comparer.
- **Garde-fou « norme zéro »** (règle R11) : si un vecteur a une longueur nulle, on ne divise
  pas par zéro (on évite un `NaN` qui se propagerait en silence). Tolérance `eps=1e-12`.
- **Fonctions sans état** (R11/R3) : pas de mémoire accumulée entre appels → pas de fuite.
- **Stockage en mémoire-mappée** (`.npy` mmap) : 4,5 M × 1024 nombres = ~9 Go ; on ne charge
  pas tout en RAM d'un coup.

---

## 4. Résultats (mesurés)

| Indicateur | Valeur | Sens |
|---|---|---|
| Dimension des vecteurs | **1024** | richesse de représentation du modèle Arctic |
| Tests d'invariants maths | **22 tests verts** | norme = 1, cosinus ∈ [-1, 1], symétrie, équivalence cosinus↔produit scalaire après normalisation |
| Effet de la traduction FR→EN | score **0,556 → 0,641** | une requête française traduite en anglais avant recherche gagne nettement en pertinence |

> 📊 **Chiffres slide** : « vecteurs 1024-dim, multilingue », « +0,085 de score grâce à la
> traduction FR→EN », « 22 tests d'invariants mathématiques ».
> 📸 **Captures** : la visualisation t-SNE du notebook `notebooks/03_embeddings_concept.ipynb`
> (nuage de points où les catégories se regroupent = preuve visuelle que les embeddings
> « comprennent » le sens).

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ Normalisation L2 **systématique avec garde-fou** → exactement la bonne pratique.
- ✅ Similarité cosinus comme métrique → standard de la recherche sémantique.
- ✅ Modèle contrastif moderne (Arctic, famille sentence-transformers) → normalisation native.
- ✅ Invariants mathématiques **testés** (rare et rassurant).

**Limites assumées :**
- **Encodeur gelé, non spécialisé** sur notre domaine (occasion high-tech). Un *fine-tuning*
  contrastif sur nos paires produits pourrait gagner un peu de précision — non fait (coût vs
  gain non démontré).
- **Multilingue mais pas parfait en FR** : on observe que l'anglais marche mieux, d'où la
  traduction des requêtes avant recherche (contournement efficace, mais c'est un contournement).
- **Branche image (SigLIP)** : l'indexation visuelle du catalogue reste *gated* (cf. thème
  retrieval) ; aujourd'hui l'entrée photo passe par une lecture VLM → texte → embedding texte.

---

## 6. Références
- Medium (Codastra) — *The math behind good embeddings: cosine similarity, norms* — https://medium.com/@2nick2patel2/the-math-behind-good-embeddings-cosine-similarity-norms-and-why-your-vectors-drift-over-time-433ff315b2a5
- PyImageSearch — *TF-IDF vs. Embeddings: from keywords to semantic search* — https://pyimagesearch.com/2026/02/09/tf-idf-vs-embeddings-from-keywords-to-semantic-search/
- Dataquest — *Measuring similarity and distance between embeddings* — https://www.dataquest.io/blog/measuring-similarity-and-distance-between-embeddings/
- arXiv 2403.05440 — *Is cosine-similarity of embeddings really about similarity?* — https://arxiv.org/html/2403.05440v1
- Snowflake — Arctic Embed L v2 (modèle utilisé) — https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0

---

### En une phrase (pour la défense)
*« On transforme chaque produit en un vecteur de 1024 nombres avec un modèle multilingue
(Arctic Embed), normalisé L2 pour que seule compte la proximité de sens (cosinus). Les
propriétés mathématiques sont testées, et on traduit les requêtes FR→EN car ça améliore
mesurablement la pertinence. »*
