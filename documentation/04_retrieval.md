# 04 — Recherche par similarité (retrieval)

> Le **moteur du produit** : retrouver, parmi 3,16 millions de produits, ceux qui
> ressemblent le plus à la photo du vendeur — vite et juste — puis lever le doute.

---

## 1. La technologie : qu'est-ce que c'est ?

Une fois le produit transformé en vecteur (cf. *Embeddings*), il faut **comparer ce vecteur
à des millions d'autres** et garder les plus proches. Le faire « bêtement » (comparer un par
un) est trop lent. On utilise donc un **index de recherche vectorielle** (FAISS) qui range
les vecteurs intelligemment pour répondre en une fraction de milliseconde.

Quatre briques chez nous :
1. **FAISS / HNSW** : l'index rapide qui trouve les voisins les plus proches.
2. **Multi-vue + RRF** : combiner plusieurs « points de vue » d'un même produit en une seule
   liste de résultats (RRF = *Reciprocal Rank Fusion*, une fusion de classements).
3. **Garde-fous OOD** : détecter un produit **inconnu** (hors catalogue) au lieu d'inventer.
4. **Akinator** : quand plusieurs candidats sont proches, poser **la** question qui les sépare.

---

## 2. État de l'art

- **HNSW** (graphe hiérarchique) atteint un rappel **quasi exact (≥ 0,95)** avec une latence
  de l'ordre de la milliseconde, sur CPU, sans GPU. C'est le standard quand « être précis et
  rapide » prime sur l'empreinte mémoire.
- **ANN (recherche approchée)** : HNSW/IVF sont des ordres de grandeur plus rapides que la
  recherche exacte (« Flat »), au prix d'une approximation minime.
- **Reciprocal Rank Fusion (RRF)** : technique standard pour **fusionner plusieurs listes de
  résultats** (ex. dense + mots-clés) en un classement final meilleur que chacun isolé.
- L'**IVF_PQ** comprime fortement (utile au-delà de ~20 M vecteurs) mais peut faire chuter le
  rappel.

---

## 3. Notre implémentation

| Brique | Fichier | Rôle |
|---|---|---|
| Index FAISS | `src/retrieval/01_faiss_indices.py` | construit/charge Flat, IVF_PQ et **HNSW** |
| Multi-vue + RRF | `src/retrieval/02_multiview_rrf.py` | fusionne plusieurs vues d'un produit |
| Garde-fous OOD | `src/retrieval/03_ood_guardrails.py` | 3 niveaux de confiance (identifié / à confirmer / inconnu) |
| Akinator | `src/retrieval/04_akinator_backend.py` | choisit la facette la plus discriminante (par entropie) |

Choix structurants (par la **mesure**, pas l'intuition) :
- **HNSW pour le service**, **Flat comme référence** d'évaluation (rappel 100 %), **IVF_PQ
  écarté** car son rappel s'effondre à notre échelle.
- **OOD = 3 niveaux** : on ne dit jamais juste « oui/non ». Si le meilleur candidat n'est pas
  assez sûr → « à confirmer » ou « non identifié », mais on montre toujours les candidats.
  **On n'invente jamais** (cohérent avec le principe « ancré »).
- **Akinator par entropie** : au lieu de poser une question au hasard, on calcule **quelle
  caractéristique sépare le mieux** les candidats restants (ex. la capacité 64/128 Go) et on
  ne demande que celle-là. « On demande à VOIR, pas à savoir » : on privilégie une observation
  (une vue, une étiquette) à une question abstraite.

---

## 4. Résultats (mesurés)

Benchmark des index (`reports/05_retrieval/`, sur 1 000 requêtes) :

| Index | Recall@1 | Latence p99 | Taille | Verdict |
|---|---|---|---|---|
| Flat (exact) | **1,000** | 23 ms | 12,3 Go | référence d'évaluation |
| **HNSW** | **0,948** | **0,29 ms** | 13,2 Go | **choisi pour le service** |
| IVF_PQ | 0,415 | 0,19 ms | 0,12 Go | écarté (rappel trop faible) |

Autres mesures :
- **Catégorie correcte en top-1 (après RRF)** : **94,2 %**.
- **Seuil OOD** calibré à **0,600** : précision **0,953**, rappel **0,988** (on attrape
  presque tous les cas inconnus sans trop de fausses alertes).
- **Akinator** déclenché sur ~**75 %** des cas ambigus (quand l'écart top-1/top-2 est faible).

> 📊 **Chiffres slide** : « HNSW : rappel 0,948 en 0,29 ms sur 3,16 M produits » (le chiffre
> qui impressionne), « catégorie top-1 à 94,2 % », « seuil OOD 0,600 (P 0,95 / R 0,99) ».
> 📸 **Captures** : le tableau de benchmark des index + un exemple d'écran « candidats +
> question Akinator » dans l'app.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ Choix d'index **par benchmark mesuré** (recall × latence × taille) → exactement la
  démarche attendue. HNSW = le bon compromis, conforme à l'état de l'art.
- ✅ **RRF** pour fusionner plusieurs vues → technique reconnue.
- ✅ **Garde-fous OOD calibrés** → on gère l'inconnu honnêtement (anti-hallucination).
- ✅ **Akinator par entropie** → désambiguïsation intelligente, pas de question au hasard.

**Limites assumées :**
- **0,29 ms mais 13 Go en RAM** : HNSW est gourmand en mémoire. Au-delà de ~20 M produits, il
  faudrait passer à IVF_PQ (compressé) en acceptant un rappel moindre — non nécessaire au
  périmètre actuel, mais à dire.
- **Recherche surtout textuelle** : l'index principal est sur le texte ; la recherche
  image→image directe (SigLIP sur le catalogue) reste *gated* (cf. limites VLM/vision).
- **RRF « multi-vue » limité** aujourd'hui par la disponibilité des vues — gagnera avec la
  branche vision.

---

## 6. Références
- Pinecone — *Hierarchical Navigable Small Worlds (HNSW)* — https://www.pinecone.io/learn/series/faiss/hnsw/
- Zilliz — *Faiss vs HNSWlib* — https://zilliz.com/blog/faiss-vs-hnswlib-choosing-the-right-tool-for-vector-search
- PyImageSearch — *Vector search with FAISS: ANN explained* — https://pyimagesearch.com/2026/02/16/vector-search-with-faiss-approximate-nearest-neighbor-ann-explained/
- Atlan — *Hybrid RAG: dense and sparse retrieval (RRF)* — https://atlan.com/know/hybrid-rag/
- Milvus — *Role of FAISS, HNSW, ScaNN* — https://milvus.io/ai-quick-reference/what-is-the-role-of-faiss-hnsw-and-scann-in-ai-databases

---

### En une phrase (pour la défense)
*« Notre moteur retrouve le bon produit parmi 3,16 millions en 0,29 ms avec un rappel de
0,948 (index HNSW choisi après benchmark), fusionne plusieurs vues par RRF, refuse d'inventer
grâce à des garde-fous OOD calibrés, et lève l'ambiguïté en posant la question la plus
discriminante (Akinator). »*
