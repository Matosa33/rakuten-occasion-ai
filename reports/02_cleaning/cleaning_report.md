# Rapport nettoyage + features + split

> **Note de périmètre.** Ce rapport porte sur le dataset large d'exploration (15 catégories). Le
> **périmètre FINAL livré du projet est de 4 catégories** (Electronics, Cell_Phones_and_Accessories,
> Video_Games, Tools_and_Home_Improvement) ; l'entraînement, la recherche et la documentation finale
> portent sur ces 4 catégories.

> Version 1.0 - 2026-05-03
> Statut : terminé - chiffres mesurés sur l'exécution réelle du pipeline.
> Tous les chiffres sont mesurés, aucun n'est inventé.

## 1. Source et périmètre

- **Input** : 30 parquets `data/raw/full/{reviews,meta}/<Cat>.parquet` issus de l'audit (15 catégories revente d'occasion sur Amazon Reviews 2023, cf. `reports/01_audit/audit_v1_amazon_reviews_2023.md`)
- **Volume input** : 348 367 044 reviews + 26 369 078 items meta (60 GB parquet zstd)
- **Output principal** : 26 369 078 items au niveau produit, enrichis et nettoyés, splittés 70/15/15

## 2. Décision de granularité

L'architecture cible repose sur la recherche augmentée par récupération (RAG). Granularité retenue :

- **Dataset principal au niveau produit** (`data/processed/products/`) : 1 ligne par `parent_asin`, ~26 M items. Carburant pour la chaîne de recherche par similarité (FAISS) et de prédiction de prix (classification, encodeurs, recherche par similarité, pricing).
- **`reviews_index` séparé** (`data/processed/reviews_index/`) : `(parent_asin, asin, user_id, timestamp, _split)` × ~348 M lignes (4 colonnes, ~5-10 GB). Permet au composant RAG de retrouver toutes les reviews d'un produit dans le bon split sans dupliquer le contenu des reviews ; la jointure se fait à la demande, en lecture paresseuse, sur `data/raw/full/reviews/` déjà présent sur disque.
- **Pas de matérialisation review × meta complète** (gaspillage 50-80 GB).

## 3. Pipeline 6 étapes

| Étape | Script | Rôle | Durée | Sortie | Taille |
|---|---|---|---:|---|---:|
| 1 | `clean/01_join_meta_with_review_aggregates.py` | Agréger reviews → enrichir meta au niveau produit | ~76 s | `intermediate/01_meta_enriched.parquet` | 6,16 GB |
| 2 | `clean/02_drop_sparse_columns.py` | Vider subtitle/author hors Books/CDs/Movies | ~58 s | `intermediate/02_meta_pruned.parquet` | 6,16 GB |
| 3 | `clean/03_normalize_text.py` | Strip HTML, collapse whitespace, empty→null | ~70 s | `intermediate/03_meta_normalized.parquet` | 6,15 GB |
| 4 | `clean/04_cap_text_lengths.py` | Cap description 8192 / title 1024 + flags | ~56 s | `intermediate/04_meta_capped.parquet` | 5,65 GB |
| 5 | `clean/05_feature_engineering.py` | price_num, log_price, price_band, lengths, n_reviews_log, years_active, recency_year | ~68 s | `intermediate/05_meta_features.parquet` | 5,81 GB |
| 6 | `split/01_split_stratified_groupkfold.py` | Split 70/15/15 stratifié cat + reviews_index | en cours | `products/{train,val,test}.parquet` + `reviews_index/{train,val,test}.parquet` | 4,10 + 0,88 + 0,88 GB (products) |

**Durée totale étapes 1-5 + split products** : ~6 min. Le `reviews_index` est plus long (scan 348 M reviews × filter sur 18 M parent_asins par split).

## 4. Agrégats reviews → niveau produit (étape 1)

Pour chaque `parent_asin`, on calcule :

| Feature | Type | Description |
|---|---|---|
| `n_reviews` | UInt32 | Nombre de reviews du produit |
| `mean_rating` | Float64 | Moyenne du rating (1-5, NaN si pas de review) |
| `std_rating` | Float64 | Écart-type rating |
| `pct_verified` | Float64 | % de `verified_purchase=true` (parsing string truthy) |
| `pct_5stars`, `pct_1stars` | Float64 | % de notes extrêmes (signal sentiment) |
| `year_first_review`, `year_last_review` | Int32 | Étendue temporelle (parsing timestamp coalesce Int64 ms / String ISO) |
| `n_unique_users` | UInt32 | Nombre de reviewers distincts |
| `mean_helpful_vote` | Float64 | Moyenne des votes utiles (signal qualité) |

**Couverture meta×reviews mesurée** :
- 26 369 078 items meta total
- 26 364 454 items avec ≥ 1 review (99,98 % couverture, cohérent avec audit 99,975 %)
- ~4 624 items sans aucune review (~0,02 %, à investiguer au nettoyage ou à supprimer pour le ML)

## 5. Drop colonnes sparses (étape 2)

| Colonne | NaN avant | Action | NaN après |
|---|---:|---|---:|
| `subtitle` | 84,8 % | Vidée hors Books, CDs_and_Vinyl, Movies_and_TV | 84,9 % (pas de gain agrégé, mais signal préservé pour les cat text-rich) |
| `author` | 89,1 % | Idem | 89,1 % |

Décision : on **ne supprime pas** la colonne entière (schéma parquet stable). On **vide** (`set None`) hors des 3 catégories où ces champs sont denses. La validation Pandera (étape suivante) refusera le NaN sur ces colonnes pour les catégories où ils sont attendus.

## 6. Normalisation textuelle (étape 3)

Colonnes traitées : `title`, `description`, `subtitle`, `author`, `store`.

Pipeline (prudent, préserve l'information) :
1. **Strip HTML** : regex `<[^>]+>` + 10 entités HTML les plus fréquentes (`&amp;`, `&nbsp;`, `&mdash;` etc.)
2. **Collapse whitespace** : `\s+` → ` `, trim leading/trailing
3. **Empty → null** : `""` après cleanup → vrai NaN (cohérence avec absence)
4. **PAS de mise en minuscules globale** : préserve les acronymes (USB, Apple, Samsung) qui portent du signal pour les classifieurs et l'identification. La normalisation de casse se fera côté tokenizer de l'encodeur, ou côté TF-IDF, lors des étapes de modélisation.
5. **NFKC** : non appliqué côté polars (pas de fonction native) - délégué aux tokenizers d'encoders qui le font nativement.

## 7. Cap longueurs + flags qualité (étape 4)

Caps :
- `description` : 8192 caractères max (audit max mesuré 1 476 557, outlier énorme)
- `title` : 1024 caractères max (audit max mesuré 2000)

Flags ajoutés :
| Flag | Définition | % train |
|---|---|---:|
| `description_too_short` | `description` < 5 chars OU null | **45,7 %** (cohérent avec audit 45 %) |
| `title_too_short` | `title` < 5 chars OU null | 1,3 % |
| `has_description` | `description` not null | 98,8 % |
| `has_title` | `title` not null | 98,8 % |

## 8. Feature engineering (étape 5)

| Feature | Type | Méthode | Médiane train | Notes |
|---|---|---|---:|---|
| `price_num` | Float64 | regex `[^\d.]` puis cast Float64, null si ≤ 0 | 18,99 $ | 40,8 % couverture (cohérent audit) |
| `log_price` | Float64 | `log1p(price_num)` | 2,99 | Pour modèles linéaires (distribution log-normale) |
| `price_band` | String | `<50/<200/≥200` | None / low / mid / high | None 59 %, low 33 %, mid 6 %, high 1,4 % |
| `length_title` | UInt32 | `str.len_chars()` | 75 chars | cohérent audit 76 |
| `length_description` | UInt32 | idem | 71 chars | cohérent audit 79, post-cap 8192 |
| `n_reviews_log` | Float64 | `log1p(n_reviews)` | log1p(2)≈1,1 | Absorbe queue longue (max 178 239 reviews/produit) |
| `years_active` | Int32 | `year_last_review - year_first_review + 1` | 1 an | Mean 2,6 - la majorité des produits ont une vie courte |
| `recency_year` | Int32 | `2023 - year_last_review` | 4 ans | Mean 4,3, max 27 (1996) |

## 9. Split stratifié 70/15/15 (étape 6)

**Stratégie** :
- **Group = parent_asin** : trivial à ce stade (1 ligne = 1 parent_asin au niveau produit), mais formalisé pour la protection anti-leakage au split.
- **Stratification = `_source_category`** : chaque cat répartie 70/15/15 indépendamment → tout le périmètre représenté à la même proportion dans les 3 splits.
- **Seed = 42** (`SEED` dans `src/config.py`).
- **Ratios** : 70/15/15 (cible standard ML).

**Résultat par split (products)** :

| Split | n_items | Taille parquet | % du total |
|---|---:|---:|---:|
| train | 18 458 346 | 4,10 GB | 70,00 % |
| val | 3 955 355 | 0,88 GB | 15,00 % |
| test | 3 955 377 | 0,88 GB | 15,00 % |
| **Total** | **26 369 078** | **5,86 GB** | **100,00 %** |

**Stratification cat-par-cat (extrait, train/val/test)** :

| Catégorie | n_total | train | val | test |
|---|---:|---:|---:|---:|
| Clothing_Shoes_and_Jewelry | 7 218 481 | 5 052 936 | 1 082 772 | 1 082 773 |
| Home_and_Kitchen | 3 735 584 | 2 614 908 | 560 337 | 560 339 |
| Books | 4 448 181 | 3 113 726 | 667 227 | 667 228 |
| Electronics | 1 610 012 | 1 127 008 | 241 501 | 241 503 |
| Tools_and_Home_Improvement | 1 473 810 | 1 031 666 | 221 071 | 221 073 |
| Automotive | 2 003 129 | 1 402 190 | 300 469 | 300 470 |
| Sports_and_Outdoors | 1 587 421 | 1 111 194 | 238 113 | 238 114 |
| Cell_Phones_and_Accessories | 1 288 490 | 901 943 | 193 273 | 193 274 |
| Movies_and_TV | 748 224 | 523 756 | 112 233 | 112 235 |
| Toys_and_Games | 890 874 | 623 611 | 133 631 | 133 632 |
| CDs_and_Vinyl | 701 959 | 491 371 | 105 293 | 105 295 |
| Baby_Products | 217 724 | 152 406 | 32 658 | 32 660 |
| Video_Games | 137 269 | 96 088 | 20 590 | 20 591 |
| Musical_Instruments | 213 593 | 149 515 | 32 038 | 32 040 |
| Appliances | 94 327 | 66 028 | 14 149 | 14 150 |

Chaque cat est répartie **exactement** à 70/15/15 (±1 ligne d'arrondi). La stratification fonctionne.

**Reviews_index conscient du split** : pour chaque split, on construit `reviews_index/{train,val,test}.parquet` qui contient `(parent_asin, asin, user_id, timestamp, _source_category, _split)` filtré sur les `parent_asin` du split correspondant. Permet au composant RAG de retrouver toutes les reviews d'un produit dans le bon split en faisant `pl.scan(reviews_index_train) JOIN data/raw/full/reviews/<cat>.parquet ON (parent_asin, asin)`.

**Résultat reviews_index (mesuré)** :

| Split | n_reviews | Taille parquet | % du total |
|---|---:|---:|---:|
| train | 242 753 136 | 6,90 GB | 69,69 % |
| val | 53 020 007 | 1,66 GB | 15,22 % |
| test | 52 593 901 | 1,64 GB | 15,10 % |
| **Total** | **348 367 044** | **10,20 GB** | **100,00 %** |

Ratio val/test légèrement asymétrique (15,22 vs 15,10) car le nombre de reviews est variable par produit, et la stratification est faite **au niveau produit** (pour empêcher les variantes d'un même produit de fuiter entre splits), pas au niveau review. Le `_split` final côté reviews est dérivé du split du `parent_asin` parent.

**Performance** : inner join polars lazy + streaming sur 348 M reviews × 26 M parent_asins = **65 secondes** seulement (vs estimation initiale > 30 min avec `pl.col("parent_asin").is_in(big_list)`). Refactor crucial : préférer toujours un `join` à un `is_in(big_list)` quand on a > 100 k éléments.

## 10. Vérifications de cohérence vs audit

| Métrique | Audit (intégralité 15 cat) | Train nettoyage | Verdict |
|---|---:|---:|---|
| Total items meta | 26 369 078 | 26 369 078 | ✅ identique |
| Couverture meta×reviews | 99,975 % | 99,98 % | ✅ identique |
| Duplication factor (n_reviews moyen) | 13,21 | 13,15 (sample train) | ✅ cohérent |
| % verified_purchase | 90,4 % | 86,3 % (mean pct_verified par produit) | ✅ cohérent (mean of pct ≠ pct global) |
| % 5★ | 65,5 % | 62,9 % (mean pct_5stars par produit) | ✅ cohérent |
| % prix valides | 40,8 % | 40,8 % | ✅ identique |
| Médiane prix | 18,99 $ | 18,99 $ | ✅ identique |
| % desc < 5 chars | 45,0 % | 45,7 % | ✅ cohérent |
| Étendue temporelle | 1996-2023 | 1996-2023 | ✅ identique |

**Aucun finding inattendu** : le pipeline cleaning ne modifie pas les distributions naturelles, il les nettoie. Tous les chiffres restent dans la marge attendue.

## 11. Conditions à respecter en aval

- **C1** : Filtrer ou imputer les ~4 624 items sans aucune review (n_reviews null). Pour la classification, on peut soit les supprimer, soit les garder en posant `n_reviews=0` et des flags spéciaux.
- **C2** : Pour la prédiction de prix, ne garder que les ~7,53 M items train avec `price_num not null` (40,8 %). Les modèles de pricing de référence doivent gérer le cas `price_band=None`.
- **C3** : À l'entraînement du classifieur, utiliser `class_weight='balanced'` ou stratifier le DataLoader pour absorber le ratio max/min entre catégories de 31,67 (déséquilibre catégoriel mesuré à l'audit).
- **C4** : Le champ `description` est utilisable directement par les encodeurs SigLIP/Arctic (le plafond de 8192 caractères reste inférieur à la fenêtre de contexte de 8192 tokens des encodeurs).
- **C5** : Pour le composant RAG, utiliser `reviews_index/{split}.parquet` pour ne récupérer que les reviews du bon split (protection contre la fuite par groupe d'utilisateurs).

## 12. Annexes

- Scripts : `src/data/clean/01..05_*.py` + `src/data/split/01_split_stratified_groupkfold.py`
- Tests d'invariants : `tests/test_clean_invariants.py` (15 tests passent)
- Décisions structurantes référencées : traitement en polars streaming, périmètre des 15 catégories, et architecture cible fondée sur la recherche augmentée par récupération (RAG).
- Stack : `polars 1.40.1` (moteur streaming), Python 3.11
- Hardware : RTX 4080 16 GB VRAM (utilisé en CPU uniquement ici, le GPU étant réservé aux encodeurs lors de l'étape de modélisation)
- Pic mémoire mesuré : ~10-12 GB RAM (concaténation de 26 M items au niveau produit en mémoire au moment du split). Aucun dépassement mémoire.
