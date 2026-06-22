# 03 — Classification & benchmark de modèles

> Comment on **entraîne plusieurs modèles, on les compare** sur les mêmes données, et on
> choisit le meilleur — en mesurant tout, sans tricher.

---

## 1. La technologie : qu'est-ce que c'est ?

**Classifier**, c'est apprendre à un modèle à ranger un produit dans la bonne **catégorie**
(ex. « Téléphones », « Jeux vidéo »). On lui montre beaucoup d'exemples étiquetés
(entraînement), puis on mesure s'il range correctement des exemples qu'il n'a jamais vus (test).

**Benchmark** = ne pas se contenter d'UN modèle, mais en entraîner **plusieurs** et les
comparer équitablement sur les mêmes jeux de données, avec les mêmes métriques.

Les métriques clés :
- **F1-score** : combine précision et rappel en une note de 0 à 1 (1 = parfait).
  - **F1 pondéré (weighted)** : moyenne pondérée par le nombre d'exemples de chaque catégorie.
  - **F1 macro** : moyenne simple, **traite toutes les catégories à égalité** (sévère sur les
    catégories rares).
- **ECE (Expected Calibration Error)** : mesure si le modèle est **honnête sur sa confiance**.
  Un modèle « calibré » qui dit « 80 % sûr » a effectivement raison ~80 % du temps. Plus l'ECE
  est bas, mieux c'est.

---

## 2. État de l'art

- **Comparer F1 macro ET pondéré** : quand le macro s'écarte beaucoup du pondéré, c'est un
  signal que le modèle gère mal les **catégories rares** (« longue traîne »).
- **Reporter le macro-F1 avec le détail par classe** (transparence).
- **Calibration (ECE)** : un bon modèle ne doit pas seulement avoir raison, il doit
  **connaître** sa propre incertitude (utile pour décider quand demander une confirmation
  humaine).
- **Principe** : comparer plusieurs modèles sur un protocole identique, sans fuite de données.

---

## 3. Notre implémentation

On a entraîné et comparé **6 modèles** (largement au-delà du minimum « ≥ 3 » exigé en interne, R4) :

| Code | Fichier | Type de modèle |
|---|---|---|
| **M1** | `src/classifiers/02_knn.py` | k plus proches voisins via l'index FAISS (cosinus) |
| **M2** | `src/classifiers/03_svm.py` | SVM linéaire |
| M3 | `src/classifiers/04_rf.py` | Random Forest (*écarté*, peu efficace en haute dimension, D-015) |
| **M4** | `src/classifiers/05_mlp.py` | petit réseau de neurones (perceptron multicouche) |
| **M5** | `src/classifiers/01_tfidf_linsvc.py` | TF-IDF + SVM linéaire + calibration Platt |
| **M6** | `src/classifiers/06_fusion_adaptive.py` | fusion (combinaison de plusieurs modèles) |
| — | `src/classifiers/07_bench_report.py` + `metrics.py` | génère le tableau comparatif + calcule les métriques |

Règles respectées :
- **Anti-fuite (R3)** : chaque modèle s'entraîne sur le train et prédit sur val/test ; rien
  n'est ajusté sur le test.
- **Tout est tracé dans MLflow** (R5) : réglages, métriques, temps d'entraînement (détaillé
  dans le thème *MLflow*).

---

## 4. Résultats (mesurés)

Tableau du benchmark (`reports/04_classifiers_bench/bench_v1.md`), trié par F1 pondéré test :

| Rang | Modèle | F1 pondéré (test) | F1 macro (test) | ECE | Temps d'entraînement |
|---|---|---|---|---|---|
| 🥇 | **M1 k-NN (FAISS)** | **0,954** | 0,942 | 0,007 | ~0 s (utilise l'index) |
| 🥈 | M6 fusion | 0,952 | 0,942 | 0,023 | ~0 s |
| 🥉 | **M5 TF-IDF + LinSVC** | **0,950** | 0,938 | 0,009 | 956 s |
| 4 | M4 MLP | 0,949 | 0,938 | **0,001** (meilleure calibration) | ~514 s |
| 5 | M2 SVM | 0,931 | 0,919 | 0,015 | ~924 s |

**Lecture clé** : F1 pondéré ≈ F1 macro partout (écart faible) → le modèle gère **bien les
catégories rares**, pas seulement les grosses. Objectif interne « F1 > 0,90 » : **largement
atteint**.

> **Pourquoi M5 (et pas M1, pourtant meilleur) est en production ?** M1 est le plus précis,
> mais il **dépend de l'index FAISS** pour fonctionner. M5 est un modèle **autonome et
> portable** (un seul fichier), donc plus simple à servir et à versionner. On garde M1 comme
> moteur du *retrieval* (cœur du produit) et M5 comme classifieur « étiquette » servi au
> Registry. C'est un choix d'ingénierie, pas un hasard.

> 📊 **Chiffres slide** : « 6 modèles comparés », « F1 pondéré 0,954 (M1) », « F1 > 0,90
> atteint », « calibration ECE 0,001 (M4) ». 📸 **Capture** : le tableau du benchmark + la
> liste des runs dans l'interface MLflow.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **6 modèles comparés** sur protocole identique, anti-fuite → dépasse l'exigence (R4).
- ✅ On reporte **F1 pondéré + F1 macro + ECE + top-3 + temps** → métriques riches, conformes
  aux recommandations.
- ✅ Macro ≈ pondéré → bonne couverture des catégories rares.
- ✅ Tout est tracé (MLflow) → reproductible et comparable.

**Limites assumées :**
- **Pas de réseau de neurones profond entraîné from scratch** : nos modèles sont du ML
  classique (k-NN, SVM, MLP léger, TF-IDF). C'est **adapté** ici (le retrieval ancré fait le
  gros du travail), mais à dire clairement : la valeur n'est pas « j'ai entraîné un gros
  réseau », elle est « j'ai comparé rigoureusement et choisi par la mesure ».
- **Random Forest (M3) écarté** : inefficace en haute dimension (1024) — décision documentée
  (D-015), pas un oubli.
- **Pas de détail par classe** publié dans le rapport courant (le macro le résume) — axe
  d'amélioration transparence.

---

## 6. Références
- EmergentMind — *Macro-F1 score overview* — https://www.emergentmind.com/topics/macro-f1-score
- NCBI Bookshelf — *Evaluating ML models and their diagnostic value* — https://www.ncbi.nlm.nih.gov/books/NBK597473/
- Springer — *Evaluating machine learning models* — https://link.springer.com/protocol/10.1007/978-1-0716-3195-9_20
- arXiv 2310.10655 — *Uncertainty quantification & calibration (ECE)* — https://arxiv.org/pdf/2310.10655

---

### En une phrase (pour la défense)
*« On n'a pas parié sur un seul modèle : on en a entraîné six, comparés sur le même protocole
anti-fuite, en mesurant F1 pondéré, F1 macro, calibration et temps. Le meilleur atteint 0,954
de F1 et la calibration descend à 0,001 ; on choisit le modèle servi par un critère
d'ingénierie (portabilité), pas par hasard. »*
