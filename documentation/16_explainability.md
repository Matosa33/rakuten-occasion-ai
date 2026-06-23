# 16 — Explainability & interprétabilité

> Pouvoir **expliquer pourquoi** le modèle décide ce qu'il décide : pourquoi cette catégorie,
> pourquoi ces produits sont jugés similaires, et documenter chaque modèle. Un modèle
> inexplicable n'est pas acceptable face à un particulier.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre
Un modèle ML est souvent une « boîte noire » : il donne une réponse sans dire pourquoi.
L'**explainability** rend cette décision **lisible** :
- **SHAP** répond à « **quelles caractéristiques** ont poussé vers cette catégorie ? » (et de
  combien chacune).
- **t-SNE / UMAP** répond à « les produits que le modèle juge similaires sont-ils **vraiment**
  regroupés ? » en projetant les vecteurs 1024-dim sur un plan 2D qu'on peut **regarder**.
- **Model Cards** = une fiche d'identité par modèle (à quoi il sert, ses données, ses limites).

### Pour l'expert
- **SHAP** (*SHapley Additive exPlanations*) attribue à chaque feature une contribution fondée
  sur les **valeurs de Shapley** (théorie des jeux) : la seule attribution qui satisfait
  efficacité + symétrie + additivité. `TreeExplainer` est la variante exacte et rapide pour les
  modèles à base d'arbres.
- **t-SNE** préserve les **voisinages locaux** (pas les distances globales) → idéal pour *voir*
  des clusters, à interpréter avec prudence (la distance entre clusters n'a pas de sens absolu).
- **Model Cards** (Mitchell et al., 2019, Google) : standard de **gouvernance** ML — usage prévu,
  données, métriques, limites, considérations éthiques.

---

## 2. État de l'art

- **SHAP/LIME** sont les standards de l'attribution de features (local + global).
- **t-SNE/UMAP** pour visualiser des espaces de grande dimension ; UMAP préserve mieux la
  structure globale et passe mieux à l'échelle.
- **Model Cards / Datasheets** : attendus pour tout modèle « responsable » (transparence,
  traçabilité, limites explicites) — de plus en plus exigés en contexte réglementaire (AI Act).
- Principe : **expliquer au bon niveau** — global (quelles features comptent en général) ET local
  (pourquoi CETTE prédiction).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

Un script unique `src/explain/01_shap_tsne_modelcards.py` (309 lignes) produit **3 livrables** :

| Livrable | Quoi | Paramètres |
|---|---|---|
| **SHAP** | `TreeExplainer` sur M3 (Random Forest) → top features importantes par catégorie (summary plot + waterfall par classe sur 3 cas) | `SHAP_N_SAMPLES = 1000` (échantillon val) |
| **t-SNE** | projection 2D des embeddings (Arctic texte + SigLIP vision) **colorés par catégorie** → vérifie la **séparation visuelle** des 4 catégories (D-011) | `TSNE_N_SAMPLES = 5000`, `perplexity = 30` |
| **Model Cards** | **12 fiches** format HuggingFace (M1-M8 internes + E1-E4 externes) : type, tâche, entrée/sortie, données d'entraînement, **limitations** | `reports/09_explainability/model_cards/*.md` |

Idée fondatrice (cohérente avec tout le projet) : **un modèle non explicable n'est pas
acceptable en production pour un particulier**. Le vendeur doit pouvoir comprendre *pourquoi* on
lui suggère cette catégorie (features SHAP) et *pourquoi* le retrieval voit ces produits comme
similaires (t-SNE qui montre les clusters de catégories bien séparés = cohérent avec le F1 élevé).

Sorties : `reports/09_explainability/shap_m3.{md,png}`, `tsne_text.png`, `tsne_vision.png`,
`model_cards/{m1..m8,e1..e4}.md`. Génération **graceful** : chaque livrable se produit seulement
si son artefact d'entrée existe (pas de crash si un embedding manque).

---

## 4. Résultats (mesurés)

- **12 Model Cards** générées (8 modèles internes M1-M8 + 4 externes E1-E4).
- **t-SNE** : les 4 catégories forment des **clusters visuellement séparés** → confirmation
  visuelle du F1 élevé (si les catégories se mélangeaient, le classifieur ne pourrait pas être
  bon ; ici l'œil confirme la métrique).
- **SHAP** : top features par catégorie documentées (`shap_m3.md`).

> 📊 **Chiffres slide** : « 12 Model Cards (gouvernance) », « t-SNE : 4 catégories visuellement
> séparées (confirme le F1) », « SHAP : top features par catégorie ». 📸 **Capture** : le nuage
> **t-SNE coloré par catégorie** (très parlant : on *voit* que le modèle sépare bien) + un
> waterfall SHAP + une Model Card.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Triple explainability** : global (SHAP features), géométrique (t-SNE clusters),
  gouvernance (Model Cards) → on couvre les 3 angles attendus.
- ✅ **Cohérence métrique ↔ visuel** : le t-SNE confirme à l'œil le F1 mesuré (rare et
  convaincant).
- ✅ **12 Model Cards** = traçabilité complète des modèles (utile pour défendre les choix).
- ✅ Génération **graceful** (pas de dépendance dure).

**Limites assumées :**
- **SHAP calculé sur M3 (Random Forest)**, or M3 a été **écarté** du serving (inefficace en
  haute dim, D-015) : SHAP explique donc un modèle *représentatif* à base d'arbres, pas
  directement le k-NN servi (le k-NN s'explique mieux par « voici les voisins », ce que fait
  déjà le retrieval). À clarifier dans la défense.
- **Pas d'explication par prédiction *en live*** : le vendeur voit les candidats + scores + le
  badge VLM, mais pas un waterfall SHAP au runtime — l'explainability est **hors-ligne**
  (rapports), pas intégrée à l'UI.
- **t-SNE sur échantillon** (5 000 points) : suffisant pour visualiser, pas exhaustif ; UMAP
  serait un complément (structure globale).

---

## 6. Références
- Lundberg & Lee — *A Unified Approach to Interpreting Model Predictions (SHAP)* — https://arxiv.org/abs/1705.07874
- SHAP — documentation `TreeExplainer` — https://shap.readthedocs.io/en/latest/
- van der Maaten & Hinton — *Visualizing Data using t-SNE* — https://www.jmlr.org/papers/v9/vandermaaten08a.html
- Mitchell et al. — *Model Cards for Model Reporting* — https://arxiv.org/abs/1810.03993

---

### En une phrase (pour la défense)
*« On explique nos modèles sur trois plans : SHAP (quelles caractéristiques poussent vers une
catégorie), t-SNE (on *voit* que les 4 catégories forment des clusters séparés, ce qui confirme
visuellement notre F1), et 12 Model Cards qui documentent chaque modèle et ses limites. Principe :
un modèle inexplicable n'est pas acceptable face à un particulier. »*
