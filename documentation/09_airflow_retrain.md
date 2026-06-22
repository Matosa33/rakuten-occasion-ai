# 09 — Orchestration & ré-entraînement (Airflow)

> Le « robot » qui ré-entraîne le modèle automatiquement, vérifie qu'il est bon, et ne le
> déploie que s'il mérite de remplacer l'ancien. C'est la **boucle de vie fermée**.

---

## 1. La technologie : qu'est-ce que c'est ?

**Apache Airflow** est un **planificateur de tâches**. On décrit un enchaînement d'étapes
(un **DAG** = graphe de tâches) et Airflow les exécute dans l'ordre, à l'heure dite, en
gérant les dépendances, les erreurs et les relances.

En MLOps, on s'en sert pour **automatiser le cycle de vie** : « chaque semaine, ré-entraîne,
évalue, et si c'est mieux, déploie ». Sans ça, le ré-entraînement serait manuel (donc oublié).

---

## 2. État de l'art

- Airflow **orchestre l'entraînement, l'évaluation et le déploiement** ; des tâches peuvent
  surveiller la performance et **déclencher un ré-entraînement** si elle baisse.
- **Planification** : par horaire (cron) ou « pilotée par la donnée » (un DAG part quand un
  jeu de données est mis à jour).
- Airflow est **agnostique** : il orchestre des outils ML (MLflow, etc.).
- Bonnes pratiques : limiter les tâches lourdes concurrentes (**pools**), **notifier** les
  responsables, surveiller temps d'exécution et qualité.
- Workflow type : extraction → entraînement → évaluation → registre → (scoring) → notification.

---

## 3. Notre implémentation

Deux DAGs (`infra/airflow/dags/`) :

**`rakuten_retrain`** — la boucle fermée, en 5 étapes :
```
check_new_data → train_classifiers → evaluate_gate → promote_gate → reimport_bento
```
| Étape | Rôle |
|---|---|
| `check_new_data` | point d'entrée (encode les nouveautés ; no-op si déjà en cache) |
| `train_classifiers` | ré-entraîne M5/M2/M4, **logge dans MLflow** (R5) |
| `evaluate_gate` | **garde-fou qualité** : si F1 < seuil, le DAG **échoue** (on ne déploie pas un modèle cassé) |
| `promote_gate` | compare challenger vs champion `@Production` → promeut **si meilleur** |
| `reimport_bento` | si promotion → ré-importe `@Production` dans le serving (BentoML) |

**`rakuten_drift_check`** — surveille la dérive des données (cf. thème *Drift*).

Détails : exécution **CPU**, `max_active_runs=1` (un seul ré-entraînement à la fois, évite la
course sur les fichiers), planification hebdomadaire.

---

## 4. Résultats (mesurés) — la boucle a vraiment tourné

Historique réel des exécutions (`infra/airflow/logs/dag_id=rakuten_retrain/`) :
- **Runs programmés** : 2026-05-10, 05-17, 05-24, 06-14 (planification hebdo respectée).
- **Runs manuels** : 2026-05-22, 06-22.
- Ces ré-entraînements ont **créé les versions v3, v4, v5** dans le registre (la trace vivante
  de la boucle), et le `promote_gate` a **correctement gardé** le champion M5 (les nouveaux
  étaient moins bons) — cf. thème *Registry*.

> 📊 **Chiffres slide** : « boucle fermée 5 étapes », « 4 runs programmés + 2 manuels », « les
> retrains ont créé v3-v5, le gate a protégé la prod ». 📸 **Capture** : la vue *Grid/Graph*
> du DAG `rakuten_retrain` dans Airflow (les 5 tâches vertes) + l'historique des runs.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Vraie boucle fermée** (train → eval → promote → redeploy), pas juste un script — conforme
  au pattern MLOps.
- ✅ **Double garde-fou** : qualité (`evaluate_gate`) + promotion conditionnelle (`promote_gate`).
- ✅ **Exécutions réelles tracées** (programmées + manuelles) → ce n'est pas théorique.
- ✅ **Agnostique** : orchestre MLflow + BentoML.
- ✅ Contrôle de ressources (`max_active_runs=1`).

**Limites assumées :**
- **Planification par cron**, pas « pilotée par la donnée » (datasets Airflow) — évolution possible.
- **`check_new_data` est un stub** : pas de vraie détection de données neuves (la démo
  ré-encode/skip). En prod réelle il faudrait brancher l'arrivée de nouveaux produits.
- **Pas de notification** (e-mail/Slack) en cas d'échec — bonne pratique manquante.
- **`train_classifiers` ne logge pas l'artefact modèle** dans le backend conteneur (cf. thème
  MLflow) → à corriger pour que le registre conteneur se peuple.

---

## 6. Références
- Astronomer — *Best practices for orchestrating MLOps pipelines with Airflow* — https://www.astronomer.io/docs/learn/airflow-mlops
- Apache Airflow — *MLOps use case* — https://airflow.apache.org/use-cases/mlops/
- ML Journey — *Automate model retraining with Airflow* — https://mljourney.com/how-to-automate-model-retraining-pipelines-with-airflow/
- Astronomer — *Orchestrating ML pipelines with Airflow* — https://www.astronomer.io/blog/orchestrating-machine-learning-pipelines-with-airflow/

---

### En une phrase (pour la défense)
*« Un DAG Airflow exécute la boucle fermée — ré-entraîner, vérifier la qualité, promouvoir si
meilleur, re-déployer — automatiquement chaque semaine. Ce n'est pas théorique : on a
l'historique des runs (programmés et manuels) qui ont créé v3-v5, et le garde-fou a protégé la
production en refusant les modèles moins bons. »*
