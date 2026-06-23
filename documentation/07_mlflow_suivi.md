# 07 — Suivi d'entraînement (MLflow)

> « Entraînement monitoré »: enregistrer **chaque** entraînement (réglages, scores, artefacts,
> version du code) pour pouvoir **comparer, reproduire et auditer**. Sans ça, la science n'est
> pas reproductible.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
**MLflow** est le « carnet de laboratoire » du ML. Chaque entraînement est un **run** qui
enregistre automatiquement:
- les **paramètres** (réglages, graine aléatoire),
- les **métriques** (F1, ECE, temps…),
- les **artefacts** (le modèle entraîné, des graphes),
- le **contexte** (version du code = commit git, version des données).

Sans ça: impossible de comparer deux essais de façon fiable, ou de reproduire un bon résultat
trois mois plus tard (« c'était quels réglages déjà ? »).

### Pour l'expert
- Le **Model Registry** versionne les modèles (v1, v2…) et les relie au **run** qui les a
 produits → traçabilité complète (on remonte aux données + réglages exacts).
- Un **alias** (`@Production`) pointe vers la version servie → on change de modèle en bougeant un
 pointeur, sans toucher au code de serving.
- **Backend découplé**: le *tracking store* (métriques/params) et l'*artifact store* (fichiers)
 peuvent être locaux (SQLite + dossier) ou distribués (Postgres + S3/MinIO).

---

## 2. État de l'art

- **Logguer tout ce qui est pertinent**: pas que la métrique finale, mais aussi **commit git,
 version des données, graine, environnement**.
- **Noms cohérents** d'expériences/métriques; **interroger** les runs par programme.
- **Registry**: nom unique, versions incrémentales liées au run; étapes None → Staging →
 **Production** → Archived (ou alias).
- **Reproductibilité**: un run = tout ce qu'il faut pour le rejouer à l'identique.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

`src/mlops/mlflow_utils.py` centralise le suivi:
- **Expérience unique** `rakuten-mvp`, `setup_mlflow` **idempotent**.
- **`TRACKING_URI` paramétrable**: `MLFLOW_TRACKING_URI` (env) → serveur **Postgres+MinIO** en
 Compose, sinon **SQLite local** `mlflow.db` en dev hôte. Détection auto du backend HTTP
 (l'`artifact_location` est alors décidé par le serveur via `--default-artifact-root`).
- **`git_commit`**: le **SHA court du commit** est logué comme tag → **reproductibilité**
 (on sait exactement quel code a produit ce run).
- **`_flatten_metrics`**: aplatit `results.{val,test}.{f1_weighted,…}` → `test_f1_weighted`,
 etc. (noms cohérents, comparables).
- **« MLflow obligatoire »**: chaque classifieur (M1-M6) + pricing logue son run.
- **Registry** `rakuten-classifier` + alias **`@Production`**; consommé par le serving
 (cf. rapport *Registry*).

---

## 4. Résultats (mesurés, vérifiables)

- **13 runs** tracés dans l'expérience `rakuten-mvp` (M1-M6 + pricing + ré-essais), chacun avec
 ses métriques réelles (F1 pondéré/macro, accuracy, ECE, temps) **+ tag commit git**.
- **Registry** `rakuten-classifier` (versions v1→v5), alias **`@Production`** (résolution
 `models:/rakuten-classifier@Production` vérifiée).
- **Double backend réconcilié** : le serveur conteneur (`:5000`, Postgres+MinIO) a été
 aligné en **MLflow 3.x** (il était bloqué en 2. vs client 3.x); il contient désormais
 des runs réels + le modèle registré + `@Production` (artefact dans MinIO). Le store local
 `mlflow.db` reste la référence complète.

> 📊 **Chiffres slide**: « 13 entraînements tracés (params + métriques + **commit git**) »,
> « 6 modèles comparés dans MLflow », « modèle `@Production` = M5 ». 📸 **Capture**: l'UI MLflow
> (`mlflow ui --backend-store-uri sqlite:///mlflow.db`) — liste des runs triables par F1 + page
> *Models* avec l'alias `@Production`. **La preuve visuelle d'« entraînement monitoré ».**

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **Tous les entraînements tracés**, métriques riches, comparables, **+ commit git** →
 reproductibles.
- ✅ **Registry + alias `@Production`** → traçabilité run ↔ modèle, swap par pointeur.
- ✅ **URI paramétrable** (local SQLite ou serveur Postgres+MinIO) → même code, deux contextes.
- ✅ Trouvailles d'audit **corrigées** (alignement version 3.x, registry conteneur peuplé).

**Limites assumées:**
- **Alias `@Production` fragile** historiquement (a « disparu » lors de re-runs / bascule de
 backend): reposé, mais il manque un **test de garde** qui échoue si l'alias est absent
 (backlog — sinon le serving casse en silence).
- **Version des données pas systématiquement loguée** comme tag (le commit git oui; le hash du
 dataset serait un plus pour la repro totale).
- **`log_model` pas encore dans le DAG** de retrain (la consolidation a registré depuis le
 `.joblib` local) → pour que les futurs retrains peuplent le registry conteneur automatiquement.

---

## 6. Références
- MLflow — *Experiment tracking* — https://mlflow.org/docs/latest/ml/tracking/
- MLflow — *Model Registry* — https://mlflow.org/docs/latest/ml/model-registry/
- MLflow — *ML lifecycle management explained* — https://mlflow.org/articles/ml-lifecycle-management-explained-for-engineers/
- Medium (D. Patil) — *Demystifying MLflow: tracking & registry* — https://dspatil.medium.com/demystifying-mlflow-a-hands-on-guide-to-experiment-tracking-and-model-registry-d99b6bfd1bda

---

### En une phrase (pour la défense)
*« Chaque entraînement est tracé dans MLflow (13 runs, 6 modèles comparés, params + métriques +
**commit git** pour la repro), avec un Model Registry et l'alias `@Production` qui désigne le
modèle servi. L'URI est paramétrable (SQLite local ou serveur Postgres+MinIO), et j'ai aligné le
serveur conteneur en 3.x pour qu'il porte aussi le registry. »*
