# 04 — Recherche par similarité (retrieval)

> Le **moteur du produit**: retrouver, parmi 3,16 millions de produits, ceux qui ressemblent
> le plus à la photo/description du vendeur — **vite et juste** — puis lever le doute sans jamais
> inventer.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
Le produit est devenu un vecteur (cf. *Embeddings*). Il faut maintenant **comparer ce vecteur à
des millions d'autres** et garder les plus proches. Comparer un par un serait trop lent (3,16 M
comparaisons par requête). On utilise donc un **index** (FAISS) qui range les vecteurs
intelligemment pour répondre en une **fraction de milliseconde**.

Quatre briques:
1. **FAISS / HNSW**: l'index rapide qui trouve les voisins.
2. **RRF**: fusionner plusieurs « points de vue » d'un produit en un classement.
3. **Garde-fous OOD**: détecter un produit **inconnu** (hors catalogue) au lieu d'inventer.
4. **Akinator**: si plusieurs candidats sont proches, poser **la** question qui les sépare.

### Pour l'expert
- **HNSW** (*Hierarchical Navigable Small World*): un **graphe à plusieurs couches**. On entre
 par une couche grossière (sauts longs) et on descend vers des couches fines (sauts courts) —
 comme un index « autoroute → nationale → rue ». Recall quasi exact (≥ 0,95) en temps
 logarithmique, sur CPU, sans GPU.
- **RRF** (*Reciprocal Rank Fusion*, Cormack 2009): `score(d) = Σᵢ 1/(k + rangᵢ(d))` avec
 **k = 60**. Génial parce qu'il fusionne des classements **sans aligner les scores** (il ne
 regarde que les **rangs**) → robuste quand deux « vues » ont des échelles de score différentes.
- **OOD**: on calibre un **seuil** sur la courbe précision/rappel, **biaisé vers la précision**
 (une fausse identification coûte plus cher qu'un « inconnu » raté).

---

## 2. État de l'art

- **HNSW** domine le régime « recall ≥ 0,95 à la milliseconde » quand la précision prime sur
 l'empreinte mémoire. **IVF_PQ** compresse fortement (utile > ~20 M vecteurs) au prix du recall.
- **ANN (recherche approchée)**: ordres de grandeur plus rapide que la recherche exacte (Flat).
- **RRF**: technique standard pour fusionner dense + lexical (BM25), ou plusieurs vues.
- **Détection OOD**: seuils sur scores de similarité, signaux contradictoires (top-1 fort mais
 catégories du top-K incohérentes).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### a) Les index FAISS (`src/retrieval/01_faiss_indices.py`)
On **construit et benchmarke 3 index** sur les mêmes vecteurs (métrique = **inner product**, car
les embeddings sont déjà L2-normalisés ⇒ IP = cosinus):
| Index | Paramètres exacts | Usage |
|---|---|---|
| **Flat IP** | exact, brute force | **référence** d'évaluation (recall 100 %) |
| **HNSW** | `M=32`, `efConstruction=200`, `efSearch=64` | **servi en production** |
| **IVF_PQ** | `nlist=1024` (~√n), `m=32` sous-quantizers, `nprobe=16` | écarté (recall trop bas à notre échelle) |

### b) Multi-vue + RRF (`src/retrieval/02_multiview_rrf.py`)
`_rrf_fusion` applique `score(d) = Σ 1/(60 + rangᵢ(d))` sur N classements (par vue) → un
classement fusionné. **k = 60** (convention Cormack, insensible aux scores).

### c) Garde-fous OOD — 3 niveaux (`src/retrieval/03_ood_guardrails.py`)
- `is_ood_top1(score, seuil)`: seuil **absolu** sur le top-1.
- `is_ambiguous_top12(s1, s2, gap=0.05)`: top-1 et top-2 trop proches → ambiguïté.
- En usage réel, la requête vendeur est **courte** → cosinus systématiquement plus bas qu'un
 item↔item complet. On passe donc à **3 niveaux** et on montre **TOUJOURS** les candidats
 (l'humain est le validateur):
 - **≥ 0,60** → *identifié*, **[0,45; 0,60[** → *à confirmer*, **< 0,45** → *incertain*.

### d) Akinator backend (`src/retrieval/04_akinator_backend.py`)
Quand `top1 − top2 < 0,05` (variantes proches), on **désambigue par observation dirigée**:
1. calculer les **attributs discriminants** entre les `TOP_K_AMBIG = 5` candidats,
2. mapper l'attribut le plus discriminant à une **observation à demander** (« montrez
 l'étiquette / le dos »),
3. re-scorer (côté API) avec la nouvelle info,
4. boucler jusqu'à clarté ou épuisement → mode dégradé honnête.

> **« On demande à VOIR, pas à savoir »**: on privilégie une observation visuelle (une vue, une
> étiquette) à une question abstraite. La sélection par **entropie** (Shannon × couverture ×
> priorité sémantique) est rejouée côté frontend (`facets.ts`, cf. rapport *Frontend*).

---

## 4. Résultats (mesurés, `reports/05_retrieval/`, 1 000 requêtes)

| Index | Recall@1 | Latence p99 | Taille | Verdict |
|---|---|---|---|---|
| Flat (exact) | **1,000** | 23 ms | 12,3 Go | référence |
| **HNSW** | **0,948** | **0,29 ms** | 13,2 Go | **servi** |
| IVF_PQ | 0,415 | 0,19 ms | 0,12 Go | écarté (recall trop bas) |

- **Catégorie correcte en top-1 (après RRF)**: **94,2 %**.
- **Seuil OOD** calibré à **0,600**: **précision 0,953 / rappel 0,988**.
- **Akinator** déclenché sur ~**75 %** des cas ambigus (gap top1/top2 faible).

> 📊 **Chiffres slide**: « HNSW: recall 0,948 en **0,29 ms** sur 3,16 M produits » (le chiffre
> qui impressionne), « catégorie top-1 94,2 % », « OOD 0,600 → P 0,95 / R 0,99 ». 📸 **Capture**:
> le tableau de benchmark des index + un écran « candidats + question Akinator ».

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **Choix d'index par benchmark mesuré** (recall × latence × taille) — la démarche attendue.
 HNSW = bon compromis, conforme à l'état de l'art.
- ✅ **RRF** (Cormack k=60) pour fusionner des vues, robuste aux échelles de score.
- ✅ **OOD calibré** côté précision → on gère l'inconnu honnêtement (anti-hallucination).
- ✅ **Akinator par observation dirigée** + entropie → désambiguïsation intelligente.

**Limites assumées:**
- **HNSW = 13 Go en RAM**: au-delà de ~20 M produits, il faudrait passer à IVF_PQ (compressé)
 en acceptant un recall moindre — non nécessaire ici, mais à dire.
- **Seuil OOD calibré sur item↔item**, alors que la requête réelle est plus courte → on a
 compensé par les 3 niveaux, mais une recalibration sur de vraies requêtes vendeur serait mieux.
- **Recherche surtout textuelle**: l'index principal est sur le texte; la recherche
 image→image directe (SigLIP catalogue) reste *gated* (cf. *VLM/LLM*).
- **RRF multi-vue** aujourd'hui limité par la disponibilité des vues — gagnera avec la vision.

---

## 6. Références
- Malkov & Yashunin — *Efficient and robust ANN search using HNSW graphs* — https://arxiv.org/abs/1603.09320
- Pinecone — *Hierarchical Navigable Small Worlds (HNSW)* — https://www.pinecone.io/learn/series/faiss/hnsw/
- Cormack et al. — *Reciprocal Rank Fusion* — https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
- FAISS — wiki (index types, IVF_PQ) — https://github.com/facebookresearch/faiss/wiki

---

### En une phrase (pour la défense)
*« Notre moteur retrouve le bon produit parmi 3,16 M en 0,29 ms avec un recall de 0,948 (HNSW
M=32, choisi après benchmark contre Flat et IVF_PQ), fusionne les vues par RRF (Cormack k=60),
refuse d'inventer grâce à des garde-fous OOD calibrés côté précision (seuil 0,600, P 0,95/R 0,99),
et lève l'ambiguïté en demandant l'observation la plus discriminante (Akinator par entropie). »*
