# 01 — Data engineering

> La matière première du projet : récupérer, comprendre, nettoyer et découper les données
> proprement, **avant** d'entraîner le moindre modèle.

---

## 1. La technologie : qu'est-ce que c'est ?

Le **data engineering**, c'est tout le travail qui précède l'entraînement d'un modèle :
- **récupérer** les données brutes,
- les **auditer** (combien y en a-t-il ? sont-elles complètes ? bien réparties ?),
- les **nettoyer** (corriger types, valeurs manquantes, doublons),
- les **découper** en trois jeux : **entraînement** (le modèle apprend dessus),
  **validation** (on règle le modèle dessus), **test** (on mesure dessus, une seule fois).

Image simple : avant de cuisiner, on choisit et on lave les ingrédients. Si les ingrédients
sont mauvais, le plat sera mauvais, quel que soit le talent du cuisinier. En IA :
**« garbage in, garbage out »**.

---

## 2. État de l'art (ce que disent les références)

Trois principes font consensus :

1. **Découper AVANT de pré-traiter.** On sépare train/test *d'abord*, puis on calcule les
   statistiques (moyenne, normalisation…) **uniquement sur le train**. Sinon une information
   du test « fuit » dans l'entraînement.
2. **Données groupées → découpage par groupe.** Quand plusieurs lignes appartiennent à une
   même entité (un patient, un produit), il faut garder **toute l'entité du même côté** du
   découpage. L'outil standard est **GroupKFold**.
3. **Valider les données avec des contrats de schéma.** Des outils comme **Pandera**
   vérifient automatiquement que chaque colonne a le bon type, les bonnes plages de valeurs,
   pas de trou interdit — *à chaque entrée* dans le système.

> **Le danger n°1 : la « fuite de données » (data leakage).** C'est quand le modèle voit, à
> l'entraînement, une information qu'il n'aurait pas dans la vraie vie. Résultat : il paraît
> excellent au test, puis s'effondre en production. C'est **l'erreur qui invalide une
> évaluation** — savoir l'éviter et en parler est un signal de sérieux fort.

---

## 3. Notre implémentation

Le pipeline data est une suite de scripts numérotés (on comprend l'ordre rien qu'en listant
les fichiers) :

| Étape | Scripts (`src/data/…`) | Rôle |
|---|---|---|
| **Audit** | `audit/01_load_full` → `04_audit_biais_leakage` | charger + mesurer qualité, distributions, biais, fuites |
| **Nettoyage** | `clean/01…06` | jointure méta+reviews, colonnes creuses, normalisation texte, plafonnage longueurs, features, lookup produit |
| **Découpage** | `split/01_split_stratified_groupkfold` | 70/15/15, **stratifié par catégorie** + **GroupKFold par produit** |
| **Validation** | `validate/01_anti_leakage_check`, `03_validate_processed`, `schemas.py` | vérif anti-fuite + contrats **Pandera** |

Choix structurants :
- **Méthode « méta-first »** : on interroge d'abord les métadonnées du dataset (tailles,
  comptes) *avant* de télécharger des dizaines de Go, pour ne pas calibrer à l'aveugle.
- **Deux jeux séparés** : un dataset **product-level** (1 ligne par produit, pour la
  classification/retrieval/prix) et un **index de reviews** léger `(produit, user, date)` —
  on ne duplique pas le texte des avis, on le joint à la demande.
- **Découpage par produit (`parent_asin`)** : toutes les lignes d'un même produit restent
  dans le même jeu. **En clair : un produit vu à l'entraînement ne peut pas réapparaître au
  test** → la note de test est honnête.
- **Données calculées sur le train uniquement** (médianes, TF-IDF, index FAISS).

---

## 4. Résultats (mesurés, vérifiables)

| Indicateur | Valeur | Ce que ça veut dire |
|---|---|---|
| Chevauchement produits train ↔ test | **0** | aucun produit en commun → pas de triche possible |
| Patterns de fuite vérifiés | **4 propres + 1 documenté** | le 5ᵉ (un même *utilisateur* des 2 côtés) est sans effet car nos modèles n'utilisent pas l'identité de l'utilisateur |
| Valeurs manquantes (avis) | **0 %** | les colonnes d'avis sont toutes renseignées |
| Couverture produits ↔ avis | **99,98 %** | quasi tous les produits ont leurs métadonnées |
| Découpage | **70 / 15 / 15**, stratifié catégorie | proportions de catégories respectées dans chaque jeu |
| Tests automatiques | verts en CI | `test_anti_leakage`, `test_pandera_schemas`, `test_clean_invariants`, `test_audit_invariants` |

> 📊 **Chiffres à mettre sur slide** : « 0 produit partagé train/test », « 99,98 % de
> couverture », « 0 % de valeurs manquantes sur les avis », « split 70/15/15 stratifié ».
> 📸 **Captures à prendre** : le tableau du rapport `reports/02_cleaning/anti_leakage_check.md`
> (les « 0 » de chevauchement) + un graphe de distribution de `reports/01_audit/figures/`.

---

## 5. Critique (état de l'art vs nous)

**Ce qui est solide (aligné sur les références) :**
- ✅ Découpage **avant** pré-traitement + stats sur train only → pas de fuite (principe n°1).
- ✅ **GroupKFold par produit** → la bonne méthode pour des données groupées (principe n°2).
- ✅ **Contrats Pandera** qui font échouer le pipeline si une donnée est hors-règle (principe n°3).
- ✅ Audit chiffré en amont + tests en CI → reproductible.

**Limites assumées (à dire avant qu'on nous les oppose) :**
- **Proxy Amazon, pas Rakuten** : pas de dump public Rakuten, scraping risqué. Biais
  documenté ; l'architecture est transposable, mais les chiffres exacts changeraient.
- **Données en anglais** → on traduit les requêtes françaises avant la recherche.
- **Fuite « utilisateur » présente mais neutre** : on n'a pas fait de découpage par
  utilisateur (`GroupKFold(user_id)`). C'est sans impact ici (nos modèles ignorent
  l'utilisateur), mais ce serait nécessaire pour un futur modèle de recommandation perso.
- **Pas de monitoring continu de qualité des données** (à la Great Expectations en service) :
  on valide au build, pas en flux permanent. C'est un axe d'amélioration.

---

## 6. Références
- scikit-learn — *Common pitfalls and recommended practices* — https://scikit-learn.org/stable/common_pitfalls.html
- MachineLearningMastery — *Avoid data leakage in data preparation* — https://machinelearningmastery.com/data-preparation-without-data-leakage/
- CrowdStrike — *ML evaluation using data splitting* — https://www.crowdstrike.com/en-us/blog/machine-learning-evaluation-using-data-splitting/
- GeeksforGeeks — *Train-test split based on group ID* — https://www.geeksforgeeks.org/machine-learning/how-to-generate-a-train-test-split-based-on-a-group-id/
- endjin — *Pandera vs Great Expectations* — https://endjin.com/blog/a-look-into-pandera-and-great-expectations-for-data-validation

---

### En une phrase (pour la défense)
*« Nos données sont auditées, nettoyées, et découpées par produit avec GroupKFold : aucun
produit n'est partagé entre entraînement et test (vérifié à 0), toutes les statistiques sont
calculées sur l'entraînement seul, et des contrats Pandera bloquent toute donnée hors-règle.
Le tout est re-testé automatiquement à chaque modification. »*
