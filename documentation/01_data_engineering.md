# 01 — Data engineering (la matière première)

> Récupérer, comprendre, nettoyer et découper les données **proprement**, *avant* d'entraîner
> le moindre modèle. C'est ici qu'on gagne ou qu'on perd la fiabilité de tout le reste.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
Le **data engineering**, c'est toute la préparation **avant** l'entraînement:
1. **récupérer** les données brutes,
2. les **auditer** (combien ? complètes ? bien réparties ? biaisées ?),
3. les **nettoyer** (types, valeurs manquantes, doublons, texte),
4. les **découper** en trois jeux: **train** (le modèle apprend), **validation** (on règle les
 hyperparamètres), **test** (on mesure une seule fois, à la fin).

Analogie: avant de cuisiner, on choisit et on lave les ingrédients. Mauvais ingrédients →
mauvais plat, quel que soit le talent du cuisinier (« garbage in, garbage out »).

### Le danger n°1: la fuite de données (data leakage)
C'est **l'erreur qui invalide une évaluation**. Elle survient quand une information du **test**
« fuit » dans l'**entraînement**. Le modèle a alors vu les réponses à l'avance → il paraît
brillant en test, puis s'effondre en vrai. Taxonomie des fuites qu'on a traquées:
- **L1 — variantes du même produit** des deux côtés (ex. le même téléphone en 64 et 128 Go) →
 le modèle « reconnaît » au lieu de généraliser.
- **fuite par le label**: une colonne contient déjà la réponse.
- **fuite temporelle**: on s'entraîne sur le futur, on teste sur le passé.
- **fuite par feature**: une statistique calculée sur tout le dataset (pas que le train).
- **fuite utilisateur**: le même utilisateur des deux côtés (pour un modèle de préférence).

### Pour l'expert
- On résout L1 par un **découpage par groupe** (`GroupKFold`) sur la clé produit `parent_asin`:
 tout le produit reste dans un seul split.
- On évite le déséquilibre de classes (B1) par une **stratification** par catégorie.
- On évite la fuite par feature avec la règle ****: *toute statistique (médiane, TF-IDF,
 index FAISS) est calculée sur le train uniquement*.

---

## 2. État de l'art

- **Découper AVANT de pré-traiter**: split d'abord, puis stats sur le train seul. L'outil
 canonique côté sklearn est le `Pipeline` (applique `fit` au train, `transform` au test).
- **Données groupées → validation croisée *group-aware*** (`GroupKFold` / `StratifiedGroupKFold`):
 tout le groupe d'une entité reste du même côté.
- **Contrats de schéma** (Pandera, Great Expectations): valider types, plages, non-nullité **à
 chaque entrée** dans le système; « valider tôt et souvent ».
- Contexte 2025: 70-85 % des projets ML échouent, la **qualité des données** en tête des causes.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### a) Choix du dataset + audit (`src/data/audit/`, `reports/01_audit/`)
- **Amazon Reviews 2023** (laboratoire McAuley) comme **proxy** de Rakuten (pas de dump public
 Rakuten; scraping = risque juridique). Biais assumé et documenté.
- **Audit en 4 portes** (4 scripts): qualité (`02_audit_qualite`), distributions
 (`03_audit_distributions`), biais & fuites (`04_audit_biais_leakage`) — chacun produit un
 rapport + un JSON de métriques.
- **Méthode « méta-first » **: on interroge d'abord les métadonnées du dataset (tailles,
 comptes par catégorie) **avant** de télécharger des dizaines de Go, pour ne pas calibrer le
 périmètre à l'aveugle.

### b) Périmètre maîtrisé 
- Audit large (jusqu'à 15 catégories evergreen-occasion) → **MVP focalisé sur 4
 catégories**: Electronics, Cell_Phones, Video_Games, Tools (~4,5 M produits). Le périmètre
 est une **décision tracée**, pas un hasard (anti scope-creep). Pandera vérifie d'ailleurs
 que `_source_category` ∈ **{4 valeurs }**.

### c) Nettoyage (`src/data/clean/`, 6 étapes numérotées)
`01_join_meta_with_review_aggregates` (jointure méta + agrégats d'avis) → `02_drop_sparse_columns`
→ `03_normalize_text` (mojibake, HTML, casse) → `04_cap_text_lengths` (plafonne à 8192 chars) →
`05_feature_engineering` (pct_verified, pct_5stars, flags `description_too_short`…) →
`06_build_product_lookup` (vignettes multi-vues, breadcrumb catégorie, marque, facettes).

### d) Découpage anti-fuite (`src/data/split/01_split_stratified_groupkfold.py`)
- **Stratifié catégorie par catégorie**, **shuffle déterministe** (`seed=42`), ratios
 **70/15/15**.
- **GroupKFold par `parent_asin`**: un produit ne peut pas être à la fois en train et en test.
 (Trivial ici car on est *product-level* = 1 ligne par `parent_asin`, mais **formalisé**.)
- **Deux sorties**: `products/{train,val,test}.parquet` ET un **`reviews_index`** léger
 `(parent_asin, asin, user_id, timestamp, _split)`. L'index des avis est construit par **un seul
 inner join lazy/streaming** (polars) reviews × mapping split — **~10× plus rapide** qu'un
 `is_in(grande_liste)` qui hasherait des dizaines de millions de chaînes. On ne **duplique pas**
 le texte des avis: on le joindra à la demande pour le RAG.

### e) Garde-fous automatiques
- **5 patterns de fuite** vérifiés (`src/data/validate/01_anti_leakage_check.py`,
 `reports/02_cleaning/anti_leakage_check.md`), re-testés en CI (`tests/test_anti_leakage.py`).
- **Contrats Pandera** (`src/data/validate/schemas.py`): `ProductSchema` + `ReviewIndexSchema`,
 **déclaratifs** (types, non-nullité, descriptions), validés en **CI sur un sample 10 000
 lignes** (rapide) et en **batch sur le full** (~26 M items). Erreurs lisibles (colonne + ligne
 + règle), pas un `AssertionError` opaque.

---

## 4. Résultats (mesurés, vérifiables)

| Indicateur | Valeur | Ce que ça veut dire |
|---|---|---|
| Chevauchement `parent_asin` train ∩ test | **0** | aucun produit partagé → pas de triche possible (anti-L1) |
| train ∩ val, val ∩ test | **0** | split product-level parfait |
| Patterns de fuite | **4 propres + 1 documenté** | le 5ᵉ (même *user_id* des 2 côtés) est **sans effet**: nos modèles n'utilisent pas l'utilisateur comme feature |
| Valeurs manquantes (avis) | **0 %** | colonnes d'avis toutes renseignées |
| Couverture produits ↔ avis | **99,98 %** (~80k avis orphelins perdus à l'inner join) | quasi tous les produits ont leurs métadonnées |
| Découpage | **70/15/15**, stratifié, seed 42 | proportions de catégories respectées dans chaque jeu |
| Tests CI | verts | `test_anti_leakage`, `test_pandera_schemas`, `test_clean_invariants`, `test_audit_invariants` |

> 📊 **Chiffres slide**: « 0 produit partagé train/test (GroupKFold) », « 99,98 % de couverture
> méta », « 0 % de valeurs manquantes sur les avis », « split 70/15/15 stratifié, seed 42 »,
> « 5 patterns de fuite vérifiés en CI ». 📸 **Captures**: le tableau des « 0 » de chevauchement
> (`anti_leakage_check.md`) + un graphe de distribution de `reports/01_audit/figures/`.

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ Découpage **avant** pré-traitement + stats sur train only → pas de fuite (principe n°1).
- ✅ **GroupKFold par produit** + **stratification catégorie** → la bonne méthode (principes 2 & B1).
- ✅ **Contrats Pandera** déclaratifs, mêmes schémas en CI (sample) et batch (full).
- ✅ Audit chiffré en amont + tests en CI → **reproductible**.
- ✅ Ingénierie efficace: `reviews_index` léger + inner join lazy (~10× le `is_in`).

**Limites assumées:**
- **Amazon ≠ Rakuten**: proxy d'itération; l'architecture est transposable, les chiffres
 exacts changeraient sur de vraies données Rakuten.
- **Données en anglais** → on traduit les requêtes FR avant la recherche (cf. rapport *Embeddings*).
- **Fuite « utilisateur » présente mais neutre**: pas de `GroupKFold(user_id)` — nécessaire
 seulement pour un futur modèle de préférence personnalisée.
- **Pas de monitoring continu de qualité** (style Great Expectations en service): on valide au
 build, pas en flux permanent → axe d'amélioration.

---

## 6. Références
- scikit-learn — *Common pitfalls and recommended practices* — https://scikit-learn.org/stable/common_pitfalls.html
- MachineLearningMastery — *Avoid data leakage in data preparation* — https://machinelearningmastery.com/data-preparation-without-data-leakage/
- CrowdStrike — *ML evaluation using data splitting* — https://www.crowdstrike.com/en-us/blog/machine-learning-evaluation-using-data-splitting/
- GeeksforGeeks — *Train-test split based on group ID (GroupKFold)* — https://www.geeksforgeeks.org/machine-learning/how-to-generate-a-train-test-split-based-on-a-group-id/
- endjin — *Pandera vs Great Expectations* — https://endjin.com/blog/a-look-into-pandera-and-great-expectations-for-data-validation

---

### En une phrase (pour la défense)
*« Nos données sont auditées en 4 portes (méta-first), nettoyées en 6 étapes, et découpées
product-level par GroupKFold sur `parent_asin` avec stratification catégorie: zéro produit
partagé entre train et test (vérifié), toutes les statistiques sur le train seul, et des
contrats Pandera qui bloquent toute donnée hors-règle — le tout re-testé automatiquement en CI. »*
