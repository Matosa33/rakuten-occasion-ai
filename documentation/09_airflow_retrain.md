# 09 - Orchestration et ré-entraînement automatique (Airflow)

> Le « robot » qui ré-entraîne le modèle tout seul à intervalle régulier, vérifie qu'il est bon,
> et ne le met en service que s'il mérite vraiment de remplacer l'ancien. C'est la boucle de vie
> complète du modèle, du nouvel apprentissage jusqu'à la mise en production, sans intervention
> humaine.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre, à partir de zéro

Un modèle de machine learning (un programme qui a appris à reconnaître des choses à partir
d'exemples) n'est pas figé une fois pour toutes. Avec le temps, les données du monde réel
changent : de nouveaux produits arrivent, les façons de les décrire évoluent. Le modèle, lui,
reste bloqué sur ce qu'il a appris au départ. Il faut donc le ré-entraîner régulièrement, c'est
à dire lui refaire apprendre les leçons sur des données plus récentes.

Le problème : si on doit le faire à la main, on finit par oublier, et le modèle vieillit en
silence sans que personne ne s'en rende compte. La solution est d'automatiser.

**Apache Airflow** est l'outil qui automatise cela. C'est un planificateur de tâches : on lui
décrit une suite d'étapes à exécuter, et il les lance dans l'ordre, à l'heure prévue, en gérant
les dépendances entre elles, les échecs et les nouvelles tentatives. On peut le voir comme un
chef d'orchestre : il ne joue pas de la musique lui même, mais il fait jouer chaque musicien au
bon moment.

Cette suite d'étapes s'appelle un **DAG**. Le mot vient de l'anglais « Directed Acyclic Graph »,
soit « graphe orienté sans boucle ». Concrètement, c'est une carte des étapes avec des flèches
qui disent « fais d'abord ceci, puis cela ». Le terme « sans boucle » signifie qu'on ne peut pas
revenir en arrière indéfiniment : le travail avance toujours vers la fin.

Notre objectif avec Airflow est simple à formuler : « chaque semaine, ré-entraîne le modèle,
évalue-le, et s'il est meilleur, déploie-le ; sinon, garde l'ancien ».

### Pour l'expert

- Un DAG apporte trois garanties : l'ordre d'exécution, la visibilité (chaque tâche a un état
  succès, échec ou ignoré, avec ses logs et ses relances), et la reproductibilité.
- Airflow est agnostique : il ne fait pas le calcul lui même, il orchestre des outils externes.
  Ici, il pilote MLflow (l'outil qui enregistre et versionne les modèles entraînés) et BentoML
  (l'outil qui sert le modèle en production via une API).
- Deux motifs de conception sont au cœur de notre implémentation. Premièrement, la barrière de
  qualité (« quality gate ») : si le modèle ré-entraîné est mauvais, on fait échouer
  volontairement le DAG pour empêcher tout déploiement. Deuxièmement, la limite à un seul
  ré-entraînement à la fois, pour éviter que deux exécutions simultanées ne se marchent dessus
  en écrivant dans les mêmes fichiers.

---

## 2. État de l'art : comment fait l'industrie

- Airflow orchestre la chaîne complète : extraction des données, entraînement, évaluation,
  enregistrement au registre des modèles, puis notification. Des tâches dédiées surveillent la
  performance et peuvent déclencher un ré-entraînement quand elle baisse.
- La planification se fait de deux manières. Soit par horaire fixe, à la manière d'un réveil
  réglé (« cron » désigne ce type de planification calendaire). Soit « pilotée par la donnée » :
  le ré-entraînement part automatiquement dès qu'un nouveau jeu de données est disponible.
- Les bonnes pratiques recommandées : limiter le nombre de tâches lourdes en parallèle pour ne
  pas saturer la machine, prévenir les responsables en cas de problème (par e-mail ou messagerie
  d'équipe), et surveiller à la fois la durée d'exécution et la qualité du résultat.

---

## 3. Notre implémentation : précisément ce qu'on a fait

Le projet contient deux DAGs, rangés dans le dossier `infra/airflow/dags/`. Le premier
ré-entraîne le modèle. Le second surveille les données et peut réveiller le premier.

### 3.1 Le DAG `rakuten_retrain` : la boucle de ré-entraînement

Fichier : `infra/airflow/dags/rakuten_retrain_dag.py`. Il enchaîne cinq étapes dans cet ordre :

```
check_new_data → train_classifiers → evaluate_gate → promote_gate → reimport_bento
```

| Étape | Ce qu'elle fait exactement |
|---|---|
| `check_new_data` | Point d'entrée. Vérifie la présence des données préparées (les « embeddings », c'est à dire les descriptions de produits transformées en listes de nombres que le modèle sait lire). Si elles sont déjà là, l'étape ne fait rien et continue. En production réelle, c'est ici qu'on lancerait le calcul des nouvelles données sur une carte graphique. |
| `train_classifiers` | Ré-entraîne trois modèles de classification (nommés M5, M2 et M4 dans le projet) sur les données, et enregistre chaque entraînement dans MLflow. M5 est le modèle principal destiné à la production. |
| `evaluate_gate` | La barrière de qualité. Elle lit le score du modèle fraîchement entraîné. Si ce score passe sous un seuil fixé, elle fait échouer tout le DAG : on refuse ainsi de déployer un modèle dégradé. |
| `promote_gate` | Compare le nouveau modèle (le « challenger ») au modèle actuellement en production (le « champion »). Elle ne fait passer le nouveau en production que s'il est réellement meilleur. |
| `reimport_bento` | Uniquement si une promotion a eu lieu : recharge le nouveau modèle de production dans le service qui répond aux requêtes (BentoML). Si aucune promotion n'a eu lieu, cette étape est ignorée. |

Quelques choix techniques importants, lisibles directement dans le code :

- **Le seuil de qualité est fixé à un score F1 de 0,85.** Le score F1 mesure la justesse globale
  d'un classifieur (combinaison de sa précision et de sa capacité à ne rien rater), sur une
  échelle de 0 à 1 où 1 est parfait. Si le modèle ré-entraîné tombe sous 0,85, le DAG échoue et
  rien n'est déployé.
- **La règle de promotion est exigeante mais juste.** Le challenger ne remplace le champion que
  si son score F1 est supérieur ou égal à celui du champion, plus une petite marge de sécurité
  de 0,001. Cette marge évite de changer de modèle pour une différence due au simple hasard. La
  métrique comparée est précisément le « F1 pondéré sur le jeu de test » (`test_f1_weighted`).
- **Un seul ré-entraînement à la fois.** Le paramètre `max_active_runs=1` interdit deux
  exécutions simultanées, ce qui évite qu'elles n'écrivent en même temps dans les mêmes fichiers
  de modèle et dans la base de données de MLflow.
- **La planification est hebdomadaire** (réglage `@weekly`) : le modèle se ré-entraîne tout seul
  une fois par semaine.
- **Tout tourne sur le processeur** (CPU), pas sur la carte graphique. Les trois modèles
  ré-entraînés ici sont des modèles légers qui n'ont pas besoin de GPU.
- **La communication entre étapes passe par XCom.** XCom est le mécanisme d'Airflow qui permet à
  une étape de transmettre un petit message à la suivante. L'étape `reimport_bento` lit ainsi le
  résultat de `promote_gate` (une valeur `promoted` qui vaut vrai ou faux) pour décider si elle
  doit recharger le modèle ou bien s'ignorer.

### 3.2 Le DAG `rakuten_drift_check` : la surveillance des données

Fichier : `infra/airflow/dags/rakuten_drift_check_dag.py`. Son rôle est de détecter la
« dérive » des données. La dérive (« drift » en anglais) désigne le fait que les données
récentes ne ressemblent plus à celles sur lesquelles le modèle a appris : par exemple, des
descriptions de produits plus longues, ou une répartition des catégories différente. Quand cela
arrive, le modèle devient moins fiable.

Ce DAG tourne tous les jours (réglage `@daily`). Il fonctionne en deux étapes :

```
detect_drift → trigger_retrain
```

- `detect_drift` calcule la dérive à l'aide d'Evidently (une bibliothèque spécialisée dans la
  comparaison statistique de deux jeux de données). Il compare une référence (un échantillon de
  50 000 produits issus des données d'entraînement) à un échantillon courant (10 000 produits
  issus des données de test, qui servent ici de substitut au flux réel de production). Trois
  caractéristiques sont surveillées : la longueur du titre, la longueur de la description, et la
  répartition des catégories. Si la part des caractéristiques ayant dérivé atteint ou dépasse
  50 %, la dérive est déclarée.
- `trigger_retrain` se déclenche uniquement si une dérive a été détectée : il lance alors
  automatiquement le DAG `rakuten_retrain` décrit plus haut, sans attendre la fin de celui-ci.
  Si aucune dérive n'est détectée, cette étape est court-circuitée et la journée se termine sans
  rien faire.

Ce découpage en deux DAGs séparés est un choix délibéré et conforme aux meilleures pratiques : la
surveillance est légère, fréquente et en lecture seule ; le ré-entraînement est lourd et n'est
déclenché que quand c'est nécessaire.

---

## 4. Résultats mesurés : la boucle a réellement tourné

Ce n'est pas un montage théorique. L'historique des exécutions est conservé dans le dossier
`infra/airflow/logs/dag_id=rakuten_retrain/` et prouve que la boucle a fonctionné pour de vrai :

- **Exécutions programmées automatiquement** : les 10, 17 et 24 mai 2026, puis le 14 juin 2026.
  Le rythme hebdomadaire a bien été respecté.
- **Exécutions lancées à la main** : les 22 mai et 22 juin 2026 (pour vérifier le comportement
  hors planning).
- Ces ré-entraînements ont produit de nouvelles versions du modèle au registre (les versions 3,
  4 et 5), ce qui constitue la trace concrète de la boucle en action.
- La barrière de promotion a fait son travail : elle a correctement conservé le champion (le
  modèle M5) parce que les nouveaux candidats étaient moins bons. La production a donc été
  protégée d'une dégradation.

> Drapeau slide : « boucle fermée en 5 étapes : entraîner, évaluer, promouvoir, redéployer », « 4
> exécutions programmées et des exécutions manuelles », « les ré-entraînements ont créé les
> versions 3 à 5, et la barrière a protégé la production ».
> Capture d'écran : la vue Grid ou Graph du DAG `rakuten_retrain` (les 5 tâches en vert) et
> l'historique des exécutions.

---

## 5. Critique : état de l'art comparé à notre solution

**Points solides :**

- Vraie boucle fermée de bout en bout (entraîner, évaluer, promouvoir, redéployer), et pas un
  simple script lancé à la main.
- Double garde-fou : une barrière de qualité qui fait échouer le DAG si le modèle est mauvais, et
  une promotion seulement conditionnelle au fait d'être réellement meilleur.
- Des exécutions réelles tracées (programmées et manuelles), ce qui rend la démonstration
  vérifiable et non théorique.
- Architecture agnostique : Airflow orchestre MLflow et BentoML sans faire le calcul lui même, et
  utilise le passage de messages XCom pour ne recharger le service que lorsqu'une promotion a eu
  lieu.
- Contrôle des ressources avec la limite d'un seul ré-entraînement simultané.

**Limites assumées :**

- La planification se fait par horaire fixe (hebdomadaire), pas encore « pilotée par la donnée ».
  Une évolution possible serait de partir automatiquement à l'arrivée de nouvelles données plutôt
  qu'à date fixe.
- L'étape `check_new_data` est volontairement simplifiée pour la démonstration : elle vérifie la
  présence des données mais ne détecte pas véritablement l'arrivée de produits neufs. En
  production réelle, il faudrait la brancher sur le flux des nouveaux produits.
- Aucune notification automatique (e-mail ou messagerie d'équipe) n'est envoyée en cas d'échec.
  C'est une bonne pratique encore manquante.

---

## 6. Références

- Astronomer, « Best practices for orchestrating MLOps pipelines with Airflow » :
  https://www.astronomer.io/docs/learn/airflow-mlops
- Apache Airflow, « MLOps use case » : https://airflow.apache.org/use-cases/mlops/
- Apache Airflow, documentation sur les XComs :
  https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html
- ML Journey, « Automate model retraining with Airflow » :
  https://mljourney.com/how-to-automate-model-retraining-pipelines-with-airflow/

---

### En une phrase, pour la défense

« Un DAG Airflow exécute toute la boucle de vie du modèle de façon automatique chaque semaine :
ré-entraîner, vérifier la qualité (une barrière qui fait échouer le processus si le score F1
descend sous 0,85), promouvoir le nouveau modèle seulement s'il est réellement meilleur, puis le
redéployer. Ce n'est pas théorique : l'historique des exécutions, programmées et manuelles, a
créé les versions 3 à 5 du modèle, et le garde-fou a protégé la production en refusant les
modèles moins bons. »
