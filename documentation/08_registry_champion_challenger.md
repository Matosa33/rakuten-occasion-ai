# 08 — Registre de modèles & champion/challenger

> Comment on choisit **le** modèle servi en production, et comment on ne le remplace **que** s'il
> est **prouvé meilleur** — automatiquement, sans jamais casser ce qui marche.

---

## 1. La technologie: qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
Le **Model Registry** est l'« étagère » centrale des modèles entraînés. Chaque modèle a un nom,
des **versions** numérotées, et une **étiquette** qui dit lequel est en production (chez nous
l'alias **`@Production`**).

Le pattern **champion / challenger**:
- le **champion** = le modèle actuellement en production,
- le **challenger** = un nouveau modèle candidat,
- on les compare sur les **mêmes données de test**,
- on **promeut** le challenger **seulement** s'il est **significativement meilleur**.

C'est ce qui évite de « casser la prod » en déployant à l'aveugle un modèle moins bon.

### Pour l'expert
- La promotion par **alias** (et non par copie de fichier) découple le code de serving du modèle:
 on bascule la prod en déplaçant un pointeur, avec **rollback** trivial (re-pointer l'alias).
- La comparaison peut être **offline** (sur un holdout, via le tracking) ou **online** (A/B,
 rollout progressif). On fait de l'**offline** — le plus simple et sûr pour un MVP.

---

## 2. État de l'art

- **Champion = prod, challenger = candidat**, testés sur le même holdout; promotion si meilleur.
 Géré par des **alias** dans le registre.
- **Gate de promotion automatisé**: confirmer d'abord que le candidat fait *au moins aussi bien*
 que la prod; étape d'approbation manuelle possible.
- **Toujours prévoir un rollback**; éviter le « 100 % du trafic d'un coup » (préférer rollout
 progressif / feature flags).

---

## 3. Notre implémentation (précisément ce qu'on a fait)

| Brique | Fichier | Rôle |
|---|---|---|
| Gate de promotion | `src/mlops/promote_gate.py` | compare challenger vs champion, bouge `@Production` **si meilleur** |
| Import pour servir | `src/serving/import_model.py` | charge `models:/rakuten-classifier@Production` pour le serving (BentoML) |
| Service de serving | `src/serving/service.py` | expose le modèle (API + métriques Prometheus) |
| Tests | `test_promote_gate.py`, `test_serving.py` | valident la logique de décision (sqlite temporaire) |

Logique exacte de `decide_and_promote(metric, epsilon)`:
1. Lire le **champion** (`@Production`) et le **challenger** (dernière version enregistrée).
2. Comparer leur métrique de référence (F1).
3. **Promouvoir seulement si `challenger ≥ champion + ε`** (ε = petit seuil → on ne bouge pas
 pour du bruit).
4. Cas « pas de nouveau challenger » (artefact non poussé → pas de nouvelle version) →
 décision `skipped_no_challenger`, **on ne touche à rien**.

C'est une **comparaison offline** (sur le jeu de test, via MLflow) — la forme la plus sûre du
pattern. Le serving (`import_model`) consomme **toujours** `@Production` → la prod suit
automatiquement la dernière promotion.

---

## 4. Résultats (mesurés) — et la preuve que le gate fonctionne

- Registre `rakuten-classifier`: **versions v1 → v5**, alias **`@Production` → v2 (M5)**.
- Les **ré-entraînements** (orchestrés par Airflow) ont **réellement créé** v3, v4, v5.
- **Preuve que le gate protège la prod**: v3/v4/v5 = des modèles SVM/MLP (F1 ≈ 0,931 / 0,949),
 **moins bons** que le champion v2 = M5 (F1 ≈ 0,950). Le gate a donc **refusé** de les promouvoir
 → `@Production` est resté sur v2. **Un gate qui ne promeut pas un challenger plus faible, c'est
 exactement ce qu'on veut.**
- **Backend conteneur peuplé** : le registry est désormais aussi rempli dans le serveur
 conteneur (`:5000`) après alignement en MLflow 3.x.

> 📊 **Chiffres slide**: « registre v1→v5 », « `@Production` = M5 », « les retrains ont créé
> v3-v5, le gate a **refusé** les moins bons (0,93/0,949 < 0,950) → prod protégée ». 📸 **Capture**:
> la page *Models* de MLflow (versions + alias) + un extrait de log de `promote_gate`
> (`skipped`/`promoted`).

---

## 5. Critique (état de l'art vs nous)

**Solide:**
- ✅ **Vrai gate champion/challenger** par alias + seuil ε → conforme au pattern standard.
- ✅ **Comparaison offline sur holdout** via MLflow → la bonne approche, simple et sûre.
- ✅ **Preuve par les faits**: des challengers réels ont été refusés à juste titre.
- ✅ **Import pour serving** depuis l'alias → la prod consomme toujours `@Production`, rollback
 trivial.

**Limites assumées:**
- **Pas de comparaison online (A/B / rollout progressif)**: on est en offline. Suffisant pour
 un MVP, mais l'A/B est l'étape suivante en vraie prod.
- **Pas de rollback automatisé formalisé** (on re-pointe l'alias à la main — trivial mais manuel).
- **Alias `@Production` fragile**: il a « disparu » plusieurs fois → un **test de garde** est à
 ajouter (backlog).
- **Pas d'étape d'approbation humaine** dans le gate (promotion 100 % automatique sur la métrique).

---

## 6. Références
- DataRobot — *Introducing MLOps champion/challenger models* — https://www.datarobot.com/blog/introducing-mlops-champion-challenger-models/
- Snowflake — *Automated retraining & champion/challenger deployment* — https://www.snowflake.com/en/developers/guides/ml-champion-challenger-model-deployment/
- Databricks — *MLOps workflows* — https://docs.databricks.com/aws/en/machine-learning/mlops/mlops-workflow
- MLflow — *Model Registry* — https://mlflow.org/docs/latest/ml/model-registry/

---

### En une phrase (pour la défense)
*« Le modèle servi est étiqueté `@Production` dans le registre; un gate champion/challenger
(`challenger ≥ champion + ε`, offline sur holdout) ne le remplace que si un candidat est
mesurablement meilleur. Preuve que ça marche: les ré-entraînements ont créé v3-v5, mais comme
ils étaient moins bons que M5, le gate a refusé de les promouvoir — la production a été protégée
automatiquement. »*
