# 07 — Suivi d'entraînement (MLflow)

> « Entraînement monitoré » : enregistrer **chaque** entraînement (réglages, scores,
> artefacts) pour pouvoir comparer, reproduire et auditer — au lieu de lancer des scripts
> dont on perd la trace.

---

## 1. La technologie : qu'est-ce que c'est ?

**MLflow** est le « carnet de laboratoire » du ML. À chaque entraînement (un **run**), il
enregistre automatiquement :
- les **paramètres** (réglages du modèle, graine aléatoire),
- les **métriques** (F1, précision, temps…),
- les **artefacts** (le modèle entraîné, des graphes),
- le contexte (version du code, des données).

Sans ça, on ne peut ni comparer deux essais de façon fiable, ni reproduire un bon résultat
trois mois plus tard. C'est la base de la **reproductibilité**.

---

## 2. État de l'art

- **Logguer tout ce qui est pertinent** : pas seulement la métrique finale, mais aussi la
  version du code (commit git), la version des données, la graine, l'environnement.
- **Noms cohérents** d'expériences et de métriques ; **interroger** les runs par programme.
- **Model Registry** : quand un modèle est bon, on l'enregistre sous un **nom unique** ; toute
  nouvelle version reçoit un numéro incrémental, **liée au run** qui l'a produite (traçabilité
  complète : on remonte aux données + réglages exacts).
- **Étapes** : None → Staging → **Production** → Archived (ou un **alias** `@Production`).

---

## 3. Notre implémentation

| Brique | Fichier | Rôle |
|---|---|---|
| Helper de tracking | `src/mlops/mlflow_utils.py` | configure l'URI, ouvre/ferme les runs, logge proprement |
| Entraînements tracés | `src/classifiers/01…06` | chaque modèle logge params + métriques dans MLflow (règle R5) |
| Promotion | `src/mlops/promote_gate.py` | champion/challenger (voir thème *Registry*) |
| Serving | `src/serving/import_model.py` | importe le modèle `@Production` pour le servir |

Choix : **R5 « MLflow obligatoire »** — aucun entraînement n'échappe au suivi. URI
paramétrable (`MLFLOW_TRACKING_URI`) : par défaut un store local **SQLite** (`mlflow.db`),
ou un **serveur** (Postgres + MinIO) en déploiement.

---

## 4. Résultats (mesurés, vérifiables)

Dans le store de référence (`mlflow.db`), via le client MLflow :

- **13 runs** tracés dans l'expérience `rakuten-mvp` (M1 k-NN, M2 SVM, M4 MLP, M5 TF-IDF,
  M6 fusion, M8 pricing + ré-essais), chacun avec ses métriques réelles (F1 pondéré/macro,
  accuracy, ECE, temps).
- **Registry** `rakuten-classifier` : versions v1→v5, alias **`@Production` → v2 (M5)**
  (résolution `models:/rakuten-classifier@Production` vérifiée OK).

> 📊 **Chiffres slide** : « 13 entraînements tracés », « 6 modèles comparés dans MLflow »,
> « modèle @Production = M5 ». 📸 **Capture** : l'interface MLflow (`mlflow ui
> --backend-store-uri sqlite:///mlflow.db`) montrant la liste des runs triables par F1 + la
> page Models avec l'alias @Production. C'est **la** preuve visuelle d'« entraînement monitoré ».

---

## 5. Critique (état de l'art vs nous) — avec deux trouvailles d'audit

**Solide :**
- ✅ **Tous les entraînements tracés** (R5), métriques riches, comparables, reproductibles.
- ✅ **Registry avec alias `@Production`** → traçabilité run ↔ modèle.
- ✅ URI paramétrable (local SQLite ou serveur Postgres+MinIO).

**Trouvailles d'audit (et leur correction) :**
1. **Deux backends qui divergeaient.** Les 13 runs de référence sont dans le **SQLite local**
   (`mlflow.db`) ; le **serveur conteneur** (Postgres+MinIO, `:5000`) ne contenait au départ
   que des runs de smoke. **Corrigé (C32.1)** : le serveur conteneur contient désormais des
   runs réels **+ le modèle `rakuten-classifier` enregistré + l'alias `@Production`** (artefact
   dans MinIO). Le `:5000` est maintenant une source cohérente.
2. **Mismatch de version MLflow** (cause racine) : client local **3.12** vs serveur conteneur
   **2.22.5** → la nouvelle API « logged-models » du client renvoyait 404 sur le serveur 2.x.
   **Corrigé (C32.1)** : image `Dockerfile.mlflow` bumpée en **3.x** ; serveur redémarré sans
   perte de données (les runs ont survécu) ; l'enregistrement de modèle fonctionne désormais.
3. **Alias `@Production` qui « disparaissait »** : observé plusieurs fois (re-runs, bascule de
   backend). Reposé (local v2 + conteneur v1). **Reste à durcir** : un test de garde qui échoue
   si l'alias manque (sinon le serving casse en silence) — backlog.
4. **Reste mineur** : faire logger l'artefact modèle directement par le DAG `train_classifiers`
   (aujourd'hui la consolidation enregistre le modèle depuis le `.joblib` local) — backlog.

**Autres limites :**
- On ne logge pas encore systématiquement le **commit git** + la **version des données** à
  chaque run (bonne pratique de reproductibilité avancée).

---

## 6. Références
- MLflow — *Experiment tracking* — https://mlflow.org/docs/latest/ml/tracking/
- MLflow — *Model Registry* — https://mlflow.org/docs/latest/ml/model-registry/
- Medium (D. Patil) — *Demystifying MLflow: tracking & registry* — https://dspatil.medium.com/demystifying-mlflow-a-hands-on-guide-to-experiment-tracking-and-model-registry-d99b6bfd1bda
- Let's Data Science — *MLflow: from experiment tracking to production* — https://letsdatascience.com/blog/mlflow-experiment-tracking-and-ml-lifecycle-management

---

### En une phrase (pour la défense)
*« Chaque entraînement est tracé dans MLflow (13 runs, 6 modèles comparés, métriques + modèle
enregistré au registry avec l'alias @Production). L'audit a révélé deux points d'infra — un
double backend et un écart de version client/serveur — que j'assume : le store local est la
source complète, et la convergence vers le serveur conteneur est une tâche identifiée. »*
