# Rapport anti-leakage

> Version 1.0 - 2026-05-03
> Statut : terminé - chiffres mesurés sur les splits products + reviews_index générés à l'étape de nettoyage et de split.
> Tous les chiffres sont mesurés, aucun n'est inventé.

## En une phrase

Sur les 5 patterns canoniques de fuite de données (data leakage), **4 sont OK** (P1, P2, P3, P5) et **1 est attendu et explicitement documenté** (P4 - chevauchement des user_id dans le reviews_index). Le pipeline de nettoyage et de split est protégé contre les fuites **au niveau produit** (protection contre les variantes d'un même produit, et stratification par catégorie contre le déséquilibre catégoriel). Pour de futurs modèles de "préférence utilisateur", un split dédié GroupKFold(user_id) sera nécessaire.

## Pattern 1 - Doublons parent_asin train/test ✅

| Métrique | Valeur | Verdict |
|---|---:|---|
| Overlap parent_asin train ∩ test | **0** | ✅ |
| Overlap parent_asin train ∩ val | **0** | ✅ |
| Overlap parent_asin val ∩ test | **0** | ✅ |
| n_unique parent_asin train | 3 156 705 | - |
| n_unique parent_asin val | 676 435 | - |
| n_unique parent_asin test | 676 441 | - |

GroupKFold(parent_asin) trivial à respecter au niveau produit (1 ligne = 1 parent_asin). Strict 0 partout : split parfait pour empêcher qu'un même produit (et ses variantes) se retrouve dans deux splits.

## Pattern 2 - Métadonnées qui contiennent le label ✅

Vérification : pour chaque catégorie, % de produits dont le `title` ou la `description` contient un mot-clé évident de la catégorie (ex: "phone" pour Cell_Phones, "game" pour Video_Games). Si > 80 %, alerte (le classifier triche).

| Catégorie | n_train | % title contient kw | % description contient kw | Alerte |
|---|---:|---:|---:|:---:|
| Electronics | 1 127 008 | 2,0 % | 10,5 % | - |
| **Cell_Phones_and_Accessories** | 901 943 | **51,3 %** | 30,6 % | - (sous le seuil 80 %) |
| Video_Games | 96 088 | 24,4 % | 34,2 % | - |
| Tools_and_Home_Improvement | 1 031 666 | 9,2 % | 9,7 % | - |

**Verdict P2** : `n_alerts = 0`. Aucune cat ne dépasse 80 %. Le maximum est Cell_Phones à 51,3 % (parce que "phone" est littéralement dans le nom commercial de chaque smartphone) - acceptable et représentatif du monde réel. Le classifier ne pourra pas tricher juste en cherchant un mot-clé évident.

## Pattern 3 - Fuite temporelle (médianes year_last_review entre splits) ✅

| Split | min_year | max_year | median_year | mean_year |
|---|---:|---:|---:|---:|
| train | 1999 | 2023 | **2020,0** | 2019,23 |
| val | 1999 | 2023 | **2020,0** | 2019,23 |
| test | 1999 | 2023 | **2020,0** | 2019,23 |

| Métrique | Valeur | Verdict |
|---|---:|---|
| Spread des médianes (max - min) | **0,0 an** | ✅ Parfait |

La stratification cat-par-cat préserve naturellement la distribution temporelle (les produits d'une cat ont la même distribution dans les 3 splits). Aucun risque de bias temporel dans les modèles.

## Pattern 4 - Overlap user_id train/test (reviews_index) ⚠️ EXPECTED

| Métrique | Valeur |
|---|---:|
| n_unique users train (reviews_index) | 24 181 207 |
| n_unique users test (reviews_index) | 9 296 795 |
| n_overlap users (test ∩ train) | **6 844 830** |
| **% test_users dans train** | **73,6 %** |

⚠️ **Verdict P4** : sévérité = attendu. **C'est attendu et documenté comme limitation de conception**.

**Pourquoi c'est attendu** :
- Le split est réalisé **au niveau produit** (pour empêcher les variantes d'un même produit de fuiter entre splits)
- Conséquence : un utilisateur qui a noté 10 produits peut très bien voir 7 de ces produits dans train et 3 dans test (avec des `parent_asin` différents)
- Du coup ses reviews train et test partagent le même `user_id`

**Conséquence pratique** :
- ✅ **Sans impact pour la chaîne de recherche par similarité (FAISS) et de prédiction de prix au niveau produit** : les classifieurs et la recherche par similarité n'utilisent pas `user_id` comme feature, donc pas de fuite.
- ⚠️ **À traiter plus tard** si on entraîne un **modèle de préférence utilisateur** (recommandation, sentiment personnalisé par utilisateur) : refaire un split dédié `GroupKFold(user_id)` qui forcera train_users ∩ test_users = ∅.

**Documentation** : ce point est inscrit comme condition aval dans `reports/02_cleaning/cleaning_report.md` §11. À rappeler dès la première étape qui voudrait apprendre des préférences utilisateur.

## Pattern 5 - Feature engineering stateless ✅

Vérification : grep dans `src/data/clean/05_feature_engineering.py` des opérations stateful (`mean()`, `std()`, `quantile()`, `min()`, `max()`, `median()`) qui dériveraient une feature de l'ensemble du dataset (au lieu du seul train).

| Métrique | Valeur | Verdict |
|---|---|---|
| Statefuls trouvés dans le code | **[]** (aucun) | ✅ |

Toutes les features dérivées en étape 5 sont **purement pointwise** (calculées ligne-par-ligne) :
- `price_num` : regex `[^\d.]` + cast Float64
- `log_price` : `log1p(price_num)` (ligne par ligne)
- `price_band` : seuils constants 50 / 200 (pas dérivés du dataset)
- `length_title`, `length_description` : `str.len_chars()` (ligne par ligne)
- `n_reviews_log` : `log1p(n_reviews)` (ligne par ligne - `n_reviews` est lui-même un agrégat des reviews par produit, donc déjà au niveau produit, pas global)
- `years_active` = `year_last_review - year_first_review + 1` (ligne par ligne)
- `recency_year` = `2023 - year_last_review` avec **2023 = constante hardcodée** (`DATASET_LAST_YEAR`), pas dérivée du dataset → OK

**Aucun risque de fuite par feature engineering**. Si on ajoute des features statefuls plus tard (z-score, normalisation, target encoding), elles devront être calculées **sur le train uniquement** et passées explicitement, conformément à la règle anti-leakage.

## Synthèse

| ID | Pattern | Sévérité | Action |
|---|---|---|---|
| **P1** | Doublons parent_asin train/test | **OK** (0 chevauchement) | aucune |
| **P2** | Les métadonnées contiennent le label | **OK** (0 alerte > 80 %) | aucune |
| **P3** | Fuite temporelle | **OK** (écart de 0 an) | aucune |
| **P4** | Chevauchement des user_id dans le reviews_index | **attendu** (73,6 % de chevauchement, choix de conception) | refaire GroupKFold(user_id) si modèle de préférence utilisateur |
| **P5** | Feature engineering sans état (stateless) | **OK** (0 opération avec état détectée) | maintenir la discipline si nouvelles features |

**Verdict global** : le pipeline de nettoyage et de split est protégé contre les fuites **au niveau requis pour la chaîne de recherche par similarité (FAISS) et de prédiction de prix au niveau produit** (cf. `docs/modeles.md`). La limitation P4 est explicitement documentée et n'impacte pas le périmètre nominal du projet.

## Annexes

- Script : `src/data/validate/01_anti_leakage_check.py`
- Métriques machine-readable : `reports/02_cleaning/anti_leakage_metrics.json` (gitignored, régénérable)
- Tests CI : `tests/test_anti_leakage.py` (à créer dans le commit suivant) - vérifie P1, P3, P5 (rapides) sans recalculer P2/P4 (lourds)
- Règles méthodologiques appliquées : règle anti-leakage, et nettoyage systématique en fin d'étape.
- Décisions structurantes référencées : architecture cible fondée sur la recherche augmentée par récupération (RAG), et périmètre du projet.
- Stack : `polars 1.40.1` streaming
- Durée check : ~1 min sur les 5 patterns
