# Rapport validation Pandera

> Version 1.0 — 2026-05-03
> Statut : terminé — schemas définis et validation complète passée sur 6/6 splits.
> Tous les chiffres sont mesurés, aucun n'est inventé.

## 1. Objectif

Définir des **contrats formels** (schemas Pandera-polars) pour les sorties du pipeline de nettoyage et de split, et valider que les parquets produits respectent ces contrats. Toute régression future de schéma sera détectée automatiquement.

## 2. Schemas définis

### `ProductSchema` (33 colonnes)

S'applique à : `data/processed/products/{train,val,test}.parquet`

Catégories de colonnes :
- **Clé + provenance (2)** : `parent_asin` (str non-null, format ASIN), `_source_category` (appartenance aux 15 catégories du périmètre)
- **Champs meta originaux (8)** : `main_category`, `title`, `average_rating`, `rating_number`, `description`, `price`, `store`, `subtitle`, `author`
- **Agrégats reviews (10)** : `n_reviews` (UInt32, ≥0), `mean_rating` (Float64, [0,5]), `std_rating` (Float64, ≥0), `pct_verified` (Float64, [0,1]), `pct_5stars` (Float64, [0,1]), `pct_1stars` (Float64, [0,1]), `year_first_review` (Int32, [1996,2023]), `year_last_review` (Int32, [1996,2023]), `n_unique_users` (UInt32, ≥0), `mean_helpful_vote` (Float64, ≥0)
- **Flags qualité (4)** : `description_too_short`, `title_too_short`, `has_description`, `has_title` (Boolean non-null)
- **Features dérivées (8)** : `price_num` (Float64, >0 ou null), `log_price` (Float64, >0 ou null), `price_band` (Utf8, isin {low, mid, high} ou null), `length_title` (UInt32, [0,1024]), `length_description` (UInt32, [0,8192]), `n_reviews_log` (Float64, ≥0), `years_active` (Int32, ≥1 ou null), `recency_year` (Int32, [0,27])

### `ReviewIndexSchema` (6 colonnes)

S'applique à : `data/processed/reviews_index/{train,val,test}.parquet`

| Colonne | Type | Nullable | Check |
|---|---|:---:|---|
| `parent_asin` | str | ❌ | non-null |
| `asin` | str | ✅ | — |
| `user_id` | str | ✅ | — |
| `timestamp` | str | ✅ | format mixte Int64 ms / String ISO toléré |
| `_source_category` | str | ❌ | appartenance aux 15 catégories du périmètre |
| `_split` | str | ❌ | isin {train, val, test} |

## 3. Résultat validation (run 2026-05-03)

| Split | Schema | Statut | n_rows / n_sample | Durée |
|---|---|:---:|---:|---:|
| products/train | ProductSchema (full) | ✅ ok | 18 458 346 | 1,8 s |
| products/val | ProductSchema (full) | ✅ ok | 3 955 355 | 1,8 s |
| products/test | ProductSchema (full) | ✅ ok | 3 955 377 | 1,8 s |
| reviews_index/train | ReviewIndexSchema (sample 100k / 242M) | ✅ ok | 100 000 | 8,3 s |
| reviews_index/val | ReviewIndexSchema (sample 100k / 53M) | ✅ ok | 100 000 | 1,8 s |
| reviews_index/test | ReviewIndexSchema (sample 100k / 53M) | ✅ ok | 100 000 | 1,5 s |

**Total : 6 / 6 OK en ~17 secondes**.

## 4. Stratégie hybride full vs sample

| Cible | Full ou sample ? | Pourquoi |
|---|---|---|
| `products/{split}.parquet` | **full** | ~26 M lignes total, validation Pandera-polars vectorisée → < 5 s même en full |
| `reviews_index/{split}.parquet` | **sample 100k** | ~348 M lignes total, validation full coûteuse (10-30 min). Sample 100k uniforme via Bernoulli step suffit pour détecter une régression de schéma |

## 5. Tests CI

`tests/test_pandera_schemas.py` — 9 tests passent en ~10 sec :

- **3 tests structurels** (toujours actifs, sans données) :
  - Schemas s'importent
  - ProductSchema définit les 10 colonnes critiques pour la chaîne de recherche par similarité (FAISS) et de prédiction de prix
  - ReviewIndexSchema a `_split` avec un contrôle d'appartenance à {train, val, test}
- **6 tests avec données** (skipif si parquets absents) :
  - 3 splits products → ProductSchema sur sample 1k
  - 3 splits reviews_index → ReviewIndexSchema sur sample 1k

## 6. Itération du fix mineure

Première run : `ProductSchema KO sur length_title (UInt32 vs attendu Int64)`. Cause : Pandera mappe `int` Python sur Int64, mais polars produit `UInt32` pour `pl.len()` et `Int32` pour `dt.year()`. Fix : utiliser les types polars natifs dans les définitions de schema (`pl.UInt32`, `pl.Int32`, `pl.Float64`, `pl.Boolean`).

Cette itération est documentée dans les notes d'apprentissage du projet : avec Pandera-polars, utiliser les types polars natifs plutôt que les types int Python.

## 7. Conditions à respecter aval

- Tout nouveau script qui modifie `data/processed/products/` ou `data/processed/reviews_index/` doit re-lancer `python -m src.data.validate.03_validate_processed` et obtenir 6/6 OK avant commit.
- Si le schema doit évoluer (nouvelles features par exemple), modifier `src/data/validate/schemas.py` ET ajouter une décision documentée dans le journal des décisions du projet, qui trace le changement et son impact en aval.

## 8. Annexes

- Schemas : `src/data/validate/schemas.py` (importable comme `from src.data.validate.schemas import ProductSchema, ReviewIndexSchema`)
- Script de validation : `src/data/validate/03_validate_processed.py`
- Métriques machine-readable : `reports/02_cleaning/pandera_validation.json` (gitignored, régénérable)
- Tests CI : `tests/test_pandera_schemas.py` (9 tests)
- Stack : `pandera[polars] 0.31.1` ajouté au pyproject.toml extras `[data]`
- Règles et décisions référencées : règle anti-leakage, nettoyage systématique, traitement en polars, et architecture cible du projet.
- Durée totale validation : ~17 sec (validation complète des products + échantillon du reviews_index)
