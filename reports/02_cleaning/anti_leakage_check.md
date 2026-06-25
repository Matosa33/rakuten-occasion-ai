# Rapport anti-leakage — Sous-todo 1.3

> Version 1.0 — 2026-05-03
> Statut : `completed` — chiffres mesurés sur les splits products + reviews_index générés en sous-todo 1.2.
> Aucun chiffre inventé (R8).

## En une phrase

Sur les 5 patterns canoniques de data leakage, **4 sont OK** (P1, P2, P3, P5) et **1 est attendu et explicitement documenté** (P4 — overlap user_id reviews_index). Le pipeline 1.2 est anti-leakage **au niveau product** (anti-L1 variantes + anti-B1 stratification cat). Pour les modèles "préférence user" futurs, un split dédié GroupKFold(user_id) sera nécessaire.

## Pattern 1 — Doublons parent_asin train/test ✅

| Métrique | Valeur | Verdict |
|---|---:|---|
| Overlap parent_asin train ∩ test | **0** | ✅ |
| Overlap parent_asin train ∩ val | **0** | ✅ |
| Overlap parent_asin val ∩ test | **0** | ✅ |
| n_unique parent_asin train | 18 458 346 | — |
| n_unique parent_asin val | 3 955 355 | — |
| n_unique parent_asin test | 3 955 377 | — |

GroupKFold(parent_asin) trivial à respecter au product-level (1 ligne = 1 parent_asin). Strict 0 partout — split parfait pour anti-L1.

## Pattern 2 — Métadonnées qui contiennent le label ✅

Vérification : pour chaque catégorie, % de produits dont le `title` ou la `description` contient un mot-clé évident de la catégorie (ex: "phone" pour Cell_Phones, "book" pour Books). Si > 80 %, alerte (le classifier triche).

| Catégorie | n_train | % title contient kw | % description contient kw | Alerte |
|---|---:|---:|---:|:---:|
| Clothing_Shoes_and_Jewelry | 5 052 936 | 32,2 % | 19,6 % | — |
| Home_and_Kitchen | 2 614 908 | 20,1 % | 16,7 % | — |
| Books | 3 113 726 | 12,2 % | 28,3 % | — |
| Electronics | 1 127 008 | 2,0 % | 10,5 % | — |
| Tools_and_Home_Improvement | 1 031 666 | 9,3 % | 9,7 % | — |
| Automotive | 1 402 190 | 23,9 % | 31,8 % | — |
| Sports_and_Outdoors | 1 111 194 | 11,0 % | 10,2 % | — |
| **Cell_Phones_and_Accessories** | 901 943 | **51,3 %** | 30,6 % | — (sous le seuil 80 %) |
| Movies_and_TV | 523 756 | 14,7 % | 18,6 % | — |
| Toys_and_Games | 623 611 | 29,0 % | 20,3 % | — |
| CDs_and_Vinyl | 491 371 | 2,3 % | 30,9 % | — |
| **Baby_Products** | 152 406 | **46,9 %** | 30,6 % | — (sous le seuil 80 %) |
| Video_Games | 96 088 | 24,4 % | 34,2 % | — |
| Musical_Instruments | 149 515 | 32,9 % | 27,6 % | — |
| **Appliances** | 66 028 | **47,1 %** | 27,4 % | — (sous le seuil 80 %) |

**Verdict P2** : `n_alerts = 0`. Aucune cat ne dépasse 80 %. Le maximum est Cell_Phones à 51,3 % (parce que "phone" est littéralement dans le nom commercial de chaque smartphone) — acceptable et représentatif du monde réel. Le classifier ne pourra pas tricher juste en cherchant un mot-clé évident.

## Pattern 3 — Fuite temporelle (médianes year_last_review entre splits) ✅

| Split | min_year | max_year | median_year | mean_year |
|---|---:|---:|---:|---:|
| train | 1996 | 2023 | **2019,0** | 2018,73 |
| val | 1996 | 2023 | **2019,0** | 2018,73 |
| test | 1997 | 2023 | **2019,0** | 2018,73 |

| Métrique | Valeur | Verdict |
|---|---:|---|
| Spread des médianes (max - min) | **0,0 an** | ✅ Parfait |

La stratification cat-par-cat préserve naturellement la distribution temporelle (les produits d'une cat ont la même distribution dans les 3 splits). Aucun risque de bias temporel dans les modèles.

## Pattern 4 — Overlap user_id train/test (reviews_index) ⚠️ EXPECTED

| Métrique | Valeur |
|---|---:|
| n_unique users train (reviews_index) | 43 987 212 |
| n_unique users test (reviews_index) | 22 605 023 |
| n_overlap users (test ∩ train) | **19 935 467** |
| **% test_users dans train** | **88,2 %** |

⚠️ **Verdict P4** : `severity = expected`. **C'est attendu et documenté comme limitation de design**.

**Pourquoi c'est attendu** :
- Le split de la sous-todo 1.2 est **product-level** (anti-L1 variantes du même produit)
- Conséquence : un user qui a noté 10 produits peut très bien voir 7 de ces produits dans train et 3 dans test (avec des `parent_asin` différents)
- Du coup ses reviews train et test partagent le même `user_id`

**Conséquence pratique** :
- ✅ **OK pour knn-faiss à pricing-cascade product-level** : les classifieurs et le retrieval n'utilisent pas `user_id` comme feature, donc pas de fuite.
- ⚠️ **À traiter au Cycle 7+** si on entraîne un **modèle préférence user** (recommendation, sentiment user-personnalisé) : refaire un split dédié `GroupKFold(user_id)` qui forcera train_users ∩ test_users = ∅.

**Documentation** : ce point est inscrit comme **C4-bis** dans `reports/02_cleaning/cleaning_report.md` §11. À rappeler lors de la première sous-todo qui voudrait apprendre des préférences user.

## Pattern 5 — Feature engineering stateless ✅

Vérification : grep dans `src/data/clean/05_feature_engineering.py` des opérations stateful (`mean()`, `std()`, `quantile()`, `min()`, `max()`, `median()`) qui dériveraient une feature de l'ensemble du dataset (au lieu du seul train).

| Métrique | Valeur | Verdict |
|---|---|---|
| Statefuls trouvés dans le code | **[]** (aucun) | ✅ |

Toutes les features dérivées en étape 5 sont **purement pointwise** (calculées ligne-par-ligne) :
- `price_num` : regex `[^\d.]` + cast Float64
- `log_price` : `log1p(price_num)` (ligne par ligne)
- `price_band` : seuils constants 50 / 200 (pas dérivés du dataset)
- `length_title`, `length_description` : `str.len_chars()` (ligne par ligne)
- `n_reviews_log` : `log1p(n_reviews)` (ligne par ligne — `n_reviews` est lui-même un agrégat reviews-par-produit, donc déjà product-level, pas global)
- `years_active` = `year_last_review - year_first_review + 1` (ligne par ligne)
- `recency_year` = `2023 - year_last_review` avec **2023 = constante hardcodée** (`DATASET_LAST_YEAR`), pas dérivée du dataset → OK

**Aucun risque de fuite feature engineering**. Si on ajoute des features statefuls plus tard (z-score, normalisation, target encoding), elles devront être calculées **sur le train uniquement** et passées explicitement (R3).

## Synthèse

| ID | Pattern | Severity | Action |
|---|---|---|---|
| **P1** | Doublons parent_asin train/test | **ok** (0 overlap) | aucune |
| **P2** | Metadata contient le label | **ok** (0 alerte > 80 %) | aucune |
| **P3** | Fuite temporelle | **ok** (spread 0 an) | aucune |
| **P4** | Overlap user_id reviews_index | **expected** (88,2 % overlap, design choice) | refaire GroupKFold(user_id) si modèle préférence user |
| **P5** | Feature engineering stateless | **ok** (0 stateful détecté) | maintenir la discipline si nouvelles features |

**Verdict global** : pipeline 1.2 anti-leakage **au niveau requis pour les modèles knn-faiss à pricing-cascade product-level** (cf. `docs/modeles.md`). La limitation P4 est explicitement documentée et n'impacte pas le scope nominal du projet.

## Annexes

- Script : `src/data/validate/01_anti_leakage_check.py`
- Métriques machine-readable : `reports/02_cleaning/anti_leakage_metrics.json` (gitignored, régénérable)
- Tests CI : `tests/test_anti_leakage.py` (à créer dans le commit suivant) — vérifie P1, P3, P5 (rapides) sans recalculer P2/P4 (lourds)
- Décisions / règles référencées : R3 (anti-leakage), R20 (cleanup fin cycle)
- ADR référencées : D-009 (architecture cible RAG-grounded), D-008 (périmètre)
- Stack : `polars 1.40.1` streaming
- Durée check : ~1 min sur les 5 patterns
