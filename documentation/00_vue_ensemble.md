# 00 — Vue d'ensemble du système

> Lecture de cadrage avant les rapports thématiques. Objectif : comprendre comment
> les briques s'emboîtent, en partant de zéro.

## 1. Le problème

Un particulier veut vendre un objet d'occasion. Rédiger une bonne annonce (catégorie,
titre, description, prix juste) est long. Le système prend **des photos de l'objet** et
produit l'annonce complète, en s'appuyant sur un **catalogue de référence** pour ne rien
inventer.

## 2. L'idée centrale : « grounded » (ancré)

> On ne demande pas à une IA de **deviner** le produit. On le **retrouve** dans un
> catalogue, puis une IA rédige à partir de faits vérifiés.

Les modèles génératifs *hallucinent* (inventent) par construction. En retrouvant d'abord
le produit réel, on transforme la tâche « inventer » (risquée) en « choisir dans une
liste » (vérifiable). C'est le principe directeur de l'architecture.

## 3. Le pipeline, étape par étape

```
 [1] ENTRÉE du vendeur
     • PHOTO(S)  ............ OBLIGATOIRE (preuve d'achat + entrée du pipeline)
     • précision texte ...... optionnel (ex. "iPhone 13 128 Go")
     • état général ......... optionnel (neuf / très bon / bon / correct)
     • checklist par type ... optionnel (fonctionne ? boîte ? accessoires ? facture ? + questions selon le type d'objet)
      |
 [2] Lecture par un VLM (IA qui "voit") -> titre probable + attributs (marque, couleur...)
     (+ la précision texte vient COMPLÉTER ce titre pour la recherche)
      |
 [3] Transformation en vecteur (embedding) -> 1024 nombres qui capturent le "sens"
      |
 [4] Recherche dans le catalogue (FAISS)   -> les produits les plus proches parmi 3,16 M
      |
 [5] Levée de doute (Akinator)             -> la question qui sépare le mieux les candidats
     (les attributs LUS sur la photo pré-remplissent déjà certaines réponses)
      |
 [6] Vérification visuelle (VLM validateur)-> la photo ressemble-t-elle au catalogue ?
      |
 [7a] PRIX (état -> décote)        [7b] DESCRIPTION (LLM ancré sur la vraie fiche
      |                                  + la checklist d'état intégrée à l'annonce)
      |                                |
 [8] ANNONCE FINALE (catégorie + photos + prix + caractéristiques + description)
```

> **À retenir** : la **photo est la seule entrée obligatoire** (c'est la preuve pour
> l'acheteur et le point de départ). Les **métadonnées sont optionnelles** mais améliorent le
> résultat : la *précision texte* affine la recherche, l'*état* ajuste le prix et le titre, la
> *checklist* enrichit la description. Le système marche avec une photo seule, et devient
> meilleur avec ces compléments.

Chaque étape fait l'objet d'un rapport thématique dédié.

## 4. Les deux moitiés du projet

**A. Data & IA — construire l'intelligence**
- Data engineering : récupérer, nettoyer, valider, éviter la fuite de données.
- Modèles : entraîner et **comparer** plusieurs modèles, mesurer le meilleur.
- Recherche (retrieval) : l'index FAISS qui retrouve le produit.
- IA génératives : VLM (voit) + LLM (rédige), utilisées de façon ancrée.

**B. MLOps — exploiter l'intelligence durablement**
- Suivi d'entraînement (MLflow) : chaque entraînement est enregistré (réglages, scores).
- Registre de modèles : étiqueter le modèle en production, ne le remplacer que s'il est meilleur.
- Orchestration (Airflow) : ré-entraînement automatisé.
- Dérive (Evidently) : surveiller le vieillissement des données.
- Observabilité (Prometheus/Grafana) : tableaux de bord de santé.
- Infra (Docker/Kubernetes) + CI/CD : empaqueter, déployer, tester automatiquement.

> En une phrase : **la partie A construit le modèle, la partie B garantit qu'il reste
> fiable, traçable et reproductible dans le temps.**

## 5. Vocabulaire minimum

| Terme | Définition simple |
|---|---|
| Embedding (vecteur) | liste de nombres qui résume le sens d'un texte/image |
| FAISS | moteur qui trouve très vite les vecteurs les plus ressemblants |
| Retrieval | aller chercher le bon produit dans le catalogue |
| Grounded / ancré | l'IA s'appuie sur des faits réels, elle n'invente pas |
| VLM | IA qui comprend les images (Vision-Language Model) |
| LLM | IA qui comprend/écrit du texte (Large Language Model) |
| MLflow | le carnet de labo qui enregistre chaque entraînement |
| Model Registry | l'étagère des modèles + l'étiquette « en production » |
| Champion / challenger | modèle en place vs candidat ; on ne remplace que si meilleur |
| Drift (dérive) | les données récentes ne ressemblent plus à celles d'entraînement |
| F1-score | note de 0 à 1 de la qualité d'un classifieur (1 = parfait) |
| MAPE | erreur moyenne en % (prix) |
| OOD | cas inconnu (produit hors catalogue) → on le signale, on n'invente pas |

## 6. Périmètre et choix assumés

- Les modèles entraînés sont du **ML classique** (k-NN, SVM, MLP, TF-IDF) ; l'encodeur de
  texte (Arctic) est **pré-entraîné gelé** ; le VLM et le LLM sont **externes (API)**.
  Choix justifié : pour identifier un produit dans un catalogue, le retrieval ancré bat un
  modèle qui devine et coûte moins cher à maintenir.
- La valeur d'ingénierie est dans **la chaîne complète** : données propres → modèles
  comparés et mesurés → mis en production → surveillés → ré-entraînables.
- Données : **Amazon Reviews 2023** comme proxy (pas de dump public Rakuten) ; biais
  documenté, architecture transposable.
