# 08 — Registre de modèles & champion/challenger

> Comment on choisit **le** modèle servi en production, et comment on ne le remplace
> **que** s'il est prouvé meilleur — automatiquement, sans casser ce qui marche.

---

## 1. La technologie : qu'est-ce que c'est ?

Le **Model Registry** est l'« étagère » centrale des modèles entraînés. Chaque modèle a un
nom, des **versions** numérotées, et une **étiquette** qui dit lequel est « en production »
(chez nous l'alias **`@Production`**).

Le pattern **champion / challenger** :
- le **champion** = le modèle actuellement en production,
- le **challenger** = un nouveau modèle candidat,
- on les compare sur les **mêmes données de test**,
- on **promeut** le challenger **seulement** s'il est **significativement meilleur**.

C'est ce qui évite de « casser la prod » en déployant à l'aveugle un modèle moins bon.

---

## 2. État de l'art

- **Champion = prod, challenger = candidat**, testés sur le même jeu *holdout* ; on promeut si
  le challenger est meilleur. Géré par des **alias** dans le registre.
- **Comparaison offline** (sur jeu de test, via le serveur de tracking) ou **online** (A/B,
  rollout progressif).
- **Gate de promotion automatisé** : on confirme d'abord que le candidat fait *au moins aussi
  bien* que la prod ; possibilité d'étape d'approbation manuelle.
- **Toujours prévoir un chemin de rollback** ; éviter le « 100 % du trafic d'un coup ».

---

## 3. Notre implémentation

| Brique | Fichier | Rôle |
|---|---|---|
| Gate de promotion | `src/mlops/promote_gate.py` | compare challenger vs champion, bouge `@Production` **si meilleur** |
| Import pour servir | `src/serving/import_model.py` | charge `models:/rakuten-classifier@Production` pour le serving (BentoML) |
| Tests | `tests/test_promote_gate.py`, `test_serving.py` | valident la logique de décision |

Logique du gate (`decide_and_promote`) :
1. Lire le **champion** actuel (`@Production`) et le **challenger** (dernière version enregistrée).
2. Comparer leur métrique de référence (F1).
3. **Promouvoir seulement si** `challenger ≥ champion + ε` (un petit seuil ε pour ne pas
   bouger pour du bruit).
4. Cas « pas de nouveau challenger » → on ne touche à rien (décision `skipped_no_challenger`).

C'est une **comparaison offline** (sur le jeu de test, via MLflow) — la forme la plus simple
et sûre du pattern.

---

## 4. Résultats (mesurés) — et la preuve que le gate fonctionne

- Registre `rakuten-classifier` : **versions v1 → v5**, alias **`@Production` → v2 (M5)**.
- Les **ré-entraînements** (orchestrés par Airflow, cf. thème suivant) ont **réellement créé**
  v3, v4, v5 — c'est la trace vivante de la boucle.
- **Preuve que le gate protège la prod** : v3/v4/v5 correspondent à des modèles SVM/MLP
  (F1 ≈ 0,931 / 0,949), **moins bons** que le champion v2 = M5 (F1 ≈ 0,950). Le gate a donc
  **correctement refusé** de les promouvoir → `@Production` est resté sur v2. **Un gate qui
  ne promeut pas un challenger plus faible, c'est exactement ce qu'on veut.**

> 📊 **Chiffres slide** : « registre v1→v5 », « @Production = M5 », « les retrains ont créé
> v3-v5, le gate a refusé les moins bons (0,93/0,949 < 0,950) ». 📸 **Capture** : la page
> *Models* de MLflow (versions + alias @Production) + un extrait de log de `promote_gate`.

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Vrai gate champion/challenger** par alias + seuil ε → conforme au pattern standard.
- ✅ **Comparaison offline sur holdout** via MLflow → la bonne approche, simple et sûre.
- ✅ **Preuve par les faits** : des challengers réels ont été refusés à juste titre.
- ✅ **Import pour serving** depuis l'alias → la prod consomme toujours `@Production`.

**Limites assumées :**
- **Pas de comparaison online (A/B / rollout progressif)** : on est en offline. Suffisant pour
  un MVP, mais l'A/B est l'étape suivante en vraie prod.
- **Pas de rollback automatisé formalisé** (on peut re-pointer l'alias à la main).
- **Alias `@Production` fragile** : il a « disparu » plusieurs fois (re-runs, bascule de
  backend) → il faut un **test de garde** qui échoue si l'alias manque (sinon le serving casse
  en silence). Identifié, dans le backlog.
- **Registry du serveur conteneur non peuplé** (cf. thème MLflow : écart de version + artefact
  modèle non loggé par le DAG) — la source complète est le store local.

---

## 6. Références
- DataRobot — *Introducing MLOps champion/challenger models* — https://www.datarobot.com/blog/introducing-mlops-champion-challenger-models/
- Snowflake — *Automated model retraining & champion/challenger deployment* — https://www.snowflake.com/en/developers/guides/ml-champion-challenger-model-deployment/
- Databricks — *MLOps workflows* — https://docs.databricks.com/aws/en/machine-learning/mlops/mlops-workflow
- MLflow — *ML lifecycle management explained* — https://mlflow.org/articles/ml-lifecycle-management-explained-for-engineers/

---

### En une phrase (pour la défense)
*« Le modèle servi est étiqueté `@Production` dans le registre ; un gate champion/challenger
ne le remplace que si un candidat est mesurablement meilleur. La preuve que ça marche : les
ré-entraînements ont créé v3-v5, mais comme ils étaient moins bons que le champion M5, le gate
a refusé de les promouvoir — la production a été protégée automatiquement. »*
