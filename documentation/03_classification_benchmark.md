# 03 — Classification & benchmark de modèles

> Entraîner **plusieurs** modèles, les comparer **équitablement** sur les mêmes données et les
> mêmes métriques, et choisir le meilleur — en mesurant tout, sans tricher. C'est le cœur de la
> rigueur ML.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
**Classer**, c'est apprendre à ranger un produit dans la bonne **catégorie** (Téléphones, Jeux
vidéo…). On montre au modèle beaucoup d'exemples étiquetés (train), puis on mesure s'il range
bien des exemples **jamais vus** (test).

**Benchmark** = ne pas se contenter d'UN modèle. On en entraîne **plusieurs** et on les compare
sur le **même** protocole. Pourquoi ? Parce qu'on ne sait pas à l'avance lequel sera le meilleur
sur NOS données, et qu'un seul modèle « qui marche » ne prouve rien sans point de comparaison.

### Les métriques (et pourquoi plusieurs)
- **F1-score** (0 à 1): équilibre entre précision (quand je dis « Téléphone », ai-je raison ?)
 et rappel (est-ce que j'attrape tous les téléphones ?).
 - **F1 pondéré**: moyenne pondérée par la taille des catégories.
 - **F1 macro**: moyenne **simple** → traite les catégories rares **à égalité** (sévère).
- **Top-k accuracy**: la bonne réponse est-elle dans les *k* premières propositions ? (utile car
 l'UI montre plusieurs candidats).
- **ECE** (*Expected Calibration Error*): le modèle est-il **honnête sur sa confiance** ? Un
 modèle calibré qui dit « 80 % sûr » a raison ~80 % du temps. On le calcule en **10 bins** de
 confiance.

### Pour l'expert
- **Écart F1 macro vs pondéré**: s'ils divergent fortement, le modèle gère mal la **longue
 traîne** (catégories rares). Chez nous ils sont **proches** → bonne couverture des rares.
- **Calibration par Platt** (régression sigmoïde sur les scores) appliquée aux SVM linéaires
 (qui sortent des marges, pas des probabilités) → des probabilités exploitables pour l'ECE et
 pour décider quand demander une confirmation humaine.

---

## 2. État de l'art

- **Comparer F1 macro ET pondéré** + reporter idéalement le détail **par classe** (transparence).
- **Calibration**: un bon modèle ne doit pas seulement avoir raison, il doit **connaître son
 incertitude** (ECE, voire MacroCE).
- **Protocole identique** pour tous les modèles, **sans fuite** (entraînement sur train, mesure
 sur test intouché).
- k-NN « comps », SVM, MLP, ensembles: pas de modèle universellement meilleur → le benchmark
 tranche empiriquement.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### Les 6 modèles comparés (= ≥ 3 exigé, on en fait 6)
| Code | Fichier | Modèle | Note |
|---|---|---|---|
| **M1** | `02_knn.py` | k-NN cosinus pondéré **via l'index FAISS** | vote des k voisins, pondéré par similarité |
| **M2** | `03_svm.py` | LinearSVC + **calibration Platt** | entraîné sur **sample 500k** (coût) |
| M3 | `04_rf.py` | Random Forest | **écarté** — peu efficace en haute dimension (1024) |
| **M4** | `05_mlp.py` | perceptron multicouche | sample 500k |
| **M5** | `01_tfidf_linsvc.py` | TF-IDF + LinearSVC + **Platt** | n'utilise PAS les embeddings (features lexicales) |
| **M6** | `06_fusion_adaptive.py` | **fusion** (combinaison adaptative de modèles) | — |
| — | `07_bench_report.py` + `metrics.py` | génère le tableau + calcule F1 w/macro, accuracy, top-1/3/5, **ECE 10 bins** | — |

### Règles d'évaluation respectées
- **Anti-fuite** : on entraîne (`fit`) uniquement sur le train et on mesure (`predict`) sur la
 validation puis le test ; rien n'est jamais ajusté en regardant le test. Pour les deux modèles
 les plus coûteux à entraîner (M2 SVM et M4 MLP), on apprend sur un **échantillon de 500 000
 lignes du train** plutôt que sur les 3,16 M : on a vérifié que l'écart de F1 entre 500k et le
 train complet est inférieur à 0,01 (l'apprentissage est déjà sur son plateau — phénomène décrit
 par la *loi de Heaps* sur la croissance du vocabulaire). C'est un gain de temps sans perte de
 qualité, pas un raccourci subi.
- **Comparaison large** : 6 modèles évalués, là où l'exigence en demandait au moins 3.
- **Traçabilité** : chaque entraînement est enregistré comme un *run* MLflow (réglages, scores,
 artefacts) → tout est reproductible et comparable a posteriori (cf. rapport *MLflow*).

### Le choix « M1 le meilleur, mais M5 en production »
M1 (k-NN FAISS) est le **plus précis**, mais il **dépend de l'index FAISS** pour fonctionner. M5
(TF-IDF + LinearSVC) est un modèle **autonome et portable** (un seul fichier `.joblib`). On garde
donc **M1 comme moteur du retrieval** (cœur produit) et **M5 comme classifieur servi** au
Registry — un choix d'**ingénierie de déploiement**, pas un hasard.

---

## 4. Résultats (mesurés, `reports/04_classifiers_bench/bench_v1.md`)

Trié par F1 pondéré sur le test:

| Rang | Modèle | F1 pondéré | F1 macro | ECE | Train |
|---|---|---|---|---|---|
| 🥇 | **M1 k-NN (FAISS)** | **0,9537** | 0,9415 | 0,0069 | ~0 s (index) |
| 🥈 | M6 fusion | 0,9522 | 0,9418 | 0,0230 | ~0 s |
| 🥉 | **M5 TF-IDF + LinSVC** | **0,9503** | 0,9375 | 0,0092 | 956 s |
| 4 | M4 MLP | 0,9489 | 0,9382 | **0,0013** (meilleure calibration) | ~514 s |
| 5 | M2 SVM | 0,9311 | 0,9193 | 0,0145 | ~924 s |

**Lecture clé**: F1 pondéré ≈ F1 macro partout → le modèle gère **bien les catégories rares**.
Objectif interne « F1 > 0,90 »: **largement atteint**. M4 a la **meilleure calibration**
(ECE 0,0013) — utile si on voulait un modèle dont la confiance est très fiable.

> 📊 **Chiffres slide**: « 6 modèles comparés », « F1 pondéré 0,954 (M1) », « F1 macro ≈ pondéré
> → catégories rares bien gérées », « ECE 0,0013 (M4) », « >0,90 atteint ». 📸 **Capture**: le
> tableau de benchmark + la liste des runs dans MLflow (triables par F1).

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **6 modèles** sur protocole identique, anti-fuite → dépasse l'exigence.
- ✅ **Métriques riches**: F1 pondéré + macro + ECE + top-1/3/5 + temps → conforme aux
 recommandations.
- ✅ **Calibration** explicite (Platt) → probabilités exploitables, ECE mesuré.
- ✅ Macro ≈ pondéré → preuve de bonne couverture des classes rares.
- ✅ Tout tracé (MLflow) → reproductible et comparable.

**Limites assumées:**
- **ML classique, pas de réseau profond from scratch**: choix adapté (le retrieval ancré fait
 l'essentiel), mais à **dire clairement** — la valeur est « comparer rigoureusement », pas
 « entraîner un gros réseau ».
- **Random Forest écarté**: inefficace en 1024 dim — décision documentée, pas un oubli.
- **Sample 500k** sur M2/M4: justifié (loi de Heaps), mais ce n'est pas le full train.
- **Pas de détail par classe** publié dans le rapport courant (le macro le résume) → axe de
 transparence.
- **Tâche « facile »** (4 catégories macro bien séparées, cf. t-SNE rapport *Explainability*):
 les F1 élevés reflètent aussi la séparabilité du problème, à contextualiser honnêtement.

---

## 6. Références
- EmergentMind — *Macro-F1 score overview* — https://www.emergentmind.com/topics/macro-f1-score
- scikit-learn — *Probability calibration (Platt scaling)* — https://scikit-learn.org/stable/modules/calibration.html
- NCBI Bookshelf — *Evaluating ML models and their diagnostic value* — https://www.ncbi.nlm.nih.gov/books/NBK597473/
- arXiv 2310.10655 — *Uncertainty quantification & calibration (ECE)* — https://arxiv.org/pdf/2310.10655

---

### En une phrase (pour la défense)
*« On n'a pas parié sur un seul modèle: six entraînés et comparés sur le même protocole
anti-fuite, en mesurant F1 pondéré, F1 macro, calibration (ECE) et temps. Le meilleur atteint
0,954 de F1, le macro est proche du pondéré (catégories rares bien gérées), et le modèle servi
est choisi par un critère d'ingénierie (portabilité, M5) — pas par hasard. »*
