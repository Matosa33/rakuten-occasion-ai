# 09 — Orchestration & ré-entraînement (Airflow)

> Le « robot » qui ré-entraîne le modèle automatiquement, vérifie qu'il est bon, et ne le
> déploie que s'il mérite de remplacer l'ancien. C'est la **boucle de vie fermée** du modèle.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
**Apache Airflow** est un **planificateur de tâches**. On décrit un enchaînement d'étapes (un
**DAG** = graphe orienté de tâches) et Airflow les exécute dans l'ordre, à l'heure dite, en
gérant les dépendances, les échecs et les relances.

En MLOps, on s'en sert pour **automatiser le cycle de vie**: « chaque semaine, ré-entraîne,
évalue, et si c'est mieux, déploie ». Sans ça, le ré-entraînement serait manuel → donc oublié,
et le modèle vieillirait silencieusement.

### Pour l'expert
- Un **DAG** garantit l'ordre + l'idempotence + la visibilité (chaque tâche a un état:
 success/failed/skipped, des logs, des relances).
- Airflow est **agnostique**: il orchestre des outils ML (ici MLflow + BentoML) via des
 opérateurs Python/Bash.
- Patterns clés: **gate de qualité** (échouer le DAG si le modèle est mauvais) et
 **`max_active_runs=1`** (éviter deux ré-entraînements concurrents qui se marchent dessus).

---

## 2. État de l'art

- Airflow **orchestre entraînement → évaluation → déploiement**; des tâches surveillent la perf
 et **déclenchent un ré-entraînement** si elle baisse.
- **Planification**: cron (horaire) ou **data-aware** (un DAG part quand un jeu de données est
 mis à jour).
- Bonnes pratiques: **pools** pour limiter les tâches lourdes concurrentes, **notifier** les
 responsables, surveiller temps d'exécution + qualité.
- Workflow type: extraction → train → eval → registre → (scoring) → notification.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

Deux DAGs (`infra/airflow/dags/`):

**`rakuten_retrain`** — la boucle fermée, 5 étapes:
```
check_new_data → train_classifiers → evaluate_gate → promote_gate → reimport_bento
```
| Étape | Rôle exact |
|---|---|
| `check_new_data` | point d'entrée (encode les nouveautés; **no-op si embeddings en cache**) |
| `train_classifiers` | ré-entraîne **M5/M2/M4**, **logue dans MLflow** |
| `evaluate_gate` | **garde-fou qualité**: si F1 < seuil → le DAG **échoue** (on ne déploie pas un modèle cassé) |
| `promote_gate` | compare challenger vs champion `@Production` → promeut **si meilleur** (cf. *Registry*) |
| `reimport_bento` | **si** promotion → ré-importe `@Production` dans le serving BentoML (sinon `skipped`) |

**`rakuten_drift_check`** — surveille la dérive des données (cf. rapport *Drift*) et peut
déclencher le retrain.

Détails: exécution **CPU**, **`max_active_runs=1`** (un seul retrain à la fois → évite la course
sur les fichiers + la base MLflow), planification **hebdomadaire**. `reimport_bento` lit le retour
de `promote_gate` via **XCom** (`promoted: true/false`) pour ne ré-importer qu'en cas de promotion.

---

## 4. Résultats (mesurés) — la boucle a vraiment tourné

Historique réel (`infra/airflow/logs/dag_id=rakuten_retrain/`):
- **Runs programmés**: 2026-05-10, 05-17, 05-24, 06-14 (hebdo respectée).
- **Runs manuels**: 2026-05-22, 06-22.
- Ces ré-entraînements ont **créé v3, v4, v5** au registre (trace vivante de la boucle); le
 `promote_gate` a **correctement gardé** le champion M5 (les nouveaux étaient moins bons).

> 📊 **Chiffres slide**: « boucle fermée 5 étapes (train→eval→promote→redeploy) », « 4 runs
> programmés + 2 manuels », « les retrains ont créé v3-v5, le gate a protégé la prod ». 📸
> **Capture**: la vue *Grid/Graph* du DAG `rakuten_retrain` (les 5 tâches vertes) + l'historique
> des runs.

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **Vraie boucle fermée** (train → eval → promote → redeploy), pas un simple script.
- ✅ **Double garde-fou**: qualité (`evaluate_gate` échoue le DAG) + promotion conditionnelle.
- ✅ **Exécutions réelles tracées** (programmées + manuelles) → pas théorique.
- ✅ **Agnostique**: orchestre MLflow + BentoML; **XCom** pour le conditionnel reimport.
- ✅ Contrôle de ressources (`max_active_runs=1`).

**Limites assumées:**
- **Planification cron**, pas « pilotée par la donnée » (datasets Airflow) — évolution possible.
- **`check_new_data` est un stub**: pas de vraie détection de données neuves (démo). En prod il
 faudrait brancher l'arrivée de nouveaux produits.
- **Pas de notification** (e-mail/Slack) en cas d'échec — bonne pratique manquante.

---

## 6. Références
- Astronomer — *Best practices for orchestrating MLOps pipelines with Airflow* — https://www.astronomer.io/docs/learn/airflow-mlops
- Apache Airflow — *MLOps use case* — https://airflow.apache.org/use-cases/mlops/
- Apache Airflow — *XComs* — https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html
- ML Journey — *Automate model retraining with Airflow* — https://mljourney.com/how-to-automate-model-retraining-pipelines-with-airflow/

---

### En une phrase (pour la défense)
*« Un DAG Airflow exécute la boucle fermée — ré-entraîner, vérifier la qualité (gate qui échoue
si F1 trop bas), promouvoir si meilleur, re-déployer — automatiquement chaque semaine. Ce n'est
pas théorique: l'historique des runs (programmés et manuels) a créé v3-v5, et le garde-fou a
protégé la production en refusant les modèles moins bons. »*
