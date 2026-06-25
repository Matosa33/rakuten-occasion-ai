# 16 - Explicabilité et interprétabilité

> L'objectif de ce composant est de pouvoir **expliquer pourquoi** le système décide ce qu'il
> décide : pourquoi telle catégorie est proposée, pourquoi tels produits sont jugés similaires, et
> de documenter chaque modèle utilisé. Un modèle dont personne ne peut expliquer le comportement
> n'est pas acceptable quand il s'adresse à un particulier qui revend un objet.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre, sans aucun bagage technique

Un modèle d'apprentissage automatique (un programme qui apprend à partir d'exemples au lieu d'être
programmé règle par règle) se comporte souvent comme une « boîte noire » : il donne une réponse,
mais sans dire pourquoi. L'explicabilité consiste à rendre cette décision **lisible** par un humain.
Nous utilisons trois outils complémentaires.

- **SHAP** répond à la question : « quelles informations ont poussé le modèle vers cette catégorie,
  et de combien chacune ? ». C'est une façon de mesurer la part de responsabilité de chaque donnée
  d'entrée dans la décision finale.
- **t-SNE** répond à la question : « les produits que le modèle juge proches sont-ils vraiment
  regroupés ? ». Pour cela, on prend les représentations numériques des produits (chaque produit est
  transformé en une liste de 1024 nombres, voir plus bas) et on les projette sur un plan en deux
  dimensions que l'on peut afficher comme une simple image. Chaque produit devient un point coloré
  selon sa catégorie, et l'on regarde si les couleurs forment des groupes nets.
- **Model Cards** (fiches modèle) : une fiche d'identité par modèle, qui dit à quoi il sert, avec
  quelles données il a été construit, et quelles sont ses limites.

Un mot sur « l'embedding » qui revient partout dans ce projet. Un embedding est la traduction d'un
produit (son texte ou son image) en une liste de nombres. Deux produits qui se ressemblent
obtiennent des listes de nombres proches. Ici, chaque produit est représenté par une liste de 1024
nombres pour le texte et 768 nombres pour l'image.

### Pour le lecteur expert

- **SHAP** (*SHapley Additive exPlanations*) attribue à chaque variable d'entrée une contribution
  fondée sur les **valeurs de Shapley**, un concept issu de la théorie des jeux. C'est la seule
  méthode d'attribution qui satisfait simultanément trois propriétés mathématiques : l'efficacité
  (la somme des contributions reconstitue la prédiction), la symétrie (deux variables au rôle
  identique reçoivent la même contribution) et l'additivité. La variante `TreeExplainer` calcule ces
  valeurs de façon exacte et rapide pour les modèles à base d'arbres de décision, comme une forêt
  aléatoire.
- **t-SNE** (*t-distributed Stochastic Neighbor Embedding*) préserve les **voisinages locaux** mais
  pas les distances globales. C'est l'outil idéal pour *voir* l'existence de groupes (clusters),
  mais il faut l'interpréter avec prudence : la distance entre deux groupes sur l'image n'a pas de
  signification absolue.
- **Model Cards** (Mitchell et al., 2019, Google) : standard de gouvernance des modèles. Une fiche
  documente l'usage prévu, les données, les métriques, les limites et les considérations éthiques.

---

## 2. État de l'art

- **SHAP** et **LIME** sont les deux standards de l'attribution de variables, à la fois au niveau
  global (quelles variables comptent en général) et local (pourquoi cette prédiction précise).
- **t-SNE** et **UMAP** sont les deux méthodes de référence pour visualiser des espaces de grande
  dimension. UMAP préserve mieux la structure globale et passe mieux à l'échelle sur de grands jeux
  de données.
- **Model Cards** et **Datasheets** sont attendus pour tout modèle dit « responsable », pour assurer
  transparence, traçabilité et limites explicites. Ils sont de plus en plus exigés dans les
  contextes réglementaires, notamment par le règlement européen sur l'intelligence artificielle
  (l'AI Act).
- Le principe directeur du domaine est d'**expliquer au bon niveau** : à la fois globalement
  (quelles informations comptent en moyenne) et localement (pourquoi cette décision-ci).

---

## 3. Notre implémentation, précisément ce que fait le code

Un seul script, `src/explain/01_shap_tsne_modelcards.py` (310 lignes), produit les livrables
d'explicabilité. Il est conçu pour fonctionner même si certains fichiers d'entrée manquent : chaque
livrable est généré seulement si l'artefact dont il dépend existe, et le script ne plante jamais si
un fichier est absent (il enregistre simplement un message et passe au suivant). Cette robustesse
s'appelle ici une génération « tolérante aux manques ».

### Livrable 1 : les 12 fiches modèle (Model Cards)

Ces fiches sont **toujours générées**, car elles ne dépendent d'aucun autre fichier. Le script écrit
12 fichiers Markdown dans le dossier `reports/09_explainability/model_cards/`, un par modèle. Huit
fiches décrivent des modèles construits dans le projet et quatre décrivent des modèles externes que
le projet réutilise tels quels.

Chaque fiche suit un format inspiré de la plateforme HuggingFace : le type du modèle, sa tâche, ce
qu'il reçoit en entrée, ce qu'il produit en sortie, les données d'entraînement ou la source, et les
limitations. Si un fichier de résultats chiffrés existe pour le modèle (au format JSON dans
`reports/04_classifiers_bench/`), la fiche y ajoute automatiquement les métriques mesurées sur le
jeu de test.

Voici le contenu réel des 12 fiches générées.

Les huit modèles internes :

| Fiche | Type | Rôle | Limites notées |
|---|---|---|---|
| m1_knn_v1 | k-NN cosinus pondéré | Classer un produit dans une des 4 catégories | Lent à l'inférence (il faut chercher les voisins), pas de calibration native des probabilités |
| m2_svm_v1 | LinearSVC avec calibration de Platt | Classer un produit, avec des probabilités calibrées | Le réglage C n'est pas optimisé (valeur par défaut), modèle linéaire donc sans interactions |
| m3_rf_v1 | Forêt aléatoire (300 arbres, profondeur max 20) | Classer un produit | Gourmand en mémoire (environ 2 Go), pas le meilleur score mais explicable via SHAP |
| m4_mlp_v1 | Réseau de neurones (couches cachées 512 puis 256, arrêt anticipé) | Classer un produit | Boîte noire (peu explicable nativement), sensible à la mise à l'échelle des données |
| m5_tfidf_linsvc_v1 | TF-IDF (mots 1-2 grammes et caractères 3-5 grammes) + LinearSVC + Platt | Classer un produit à partir du texte brut | Pas de sémantique (mots isolés), mais excellente base de référence |
| m6_fusion_v1 | Fusion adaptative (moyenne pondérée des probabilités) | Combiner les modèles m2, m3, m4 et m5 | Coût d'inférence multiplié par quatre, à n'adopter que si le gain dépasse +0,02 de score F1 |
| m7_faiss_hnsw_v1 | Index FAISS HNSW (M=32, efConstruction=200, efSearch=64) | Retrouver les produits les plus proches d'un produit donné | Recherche approximative (taux de rappel de 95 à 98 %), à comparer à une recherche exacte de référence |
| m8_pricing_v1 | Cascade de règles transparentes, sans apprentissage | Suggérer un prix indicatif avec un niveau de confiance | Dépréciation supposée linéaire (la vraie courbe ne l'est pas), pas d'effet de saisonnalité |

Quelques termes employés ci-dessus, expliqués simplement :

- **k-NN cosinus pondéré** : pour classer un produit, on regarde ses voisins les plus ressemblants
  et on vote, en donnant plus de poids aux plus proches.
- **LinearSVC** : un séparateur linéaire qui trace une frontière entre catégories.
- **Calibration de Platt** : une correction qui transforme les scores bruts en vraies probabilités
  (par exemple « 80 % de chances que ce soit cette catégorie »).
- **TF-IDF** : une façon de transformer un texte en nombres en mesurant l'importance de chaque mot.
- **FAISS** : une bibliothèque qui retrouve très vite les éléments les plus proches parmi des
  millions. **HNSW** est sa méthode de recherche approximative par graphe de voisinage.
- **Score F1** : une note de qualité de classification entre 0 et 1, qui combine la précision et le
  rappel ; plus c'est proche de 1, mieux c'est.

Pour le modèle m5, la fiche indique des performances mesurées : F1 pondéré sur le test de 0,9503,
F1 macro de 0,9375, et une erreur de calibration attendue (ECE) de 0,0092. L'ECE mesure l'écart
entre la confiance annoncée et la justesse réelle ; plus elle est faible, plus les probabilités
annoncées sont honnêtes.

Les quatre modèles externes réutilisés :

| Fiche | Type | Source | Rôle |
|---|---|---|---|
| siglip_v1 | SigLIP base ViT-B/16, gelé, 768 dimensions | google/siglip-base-patch16-224 | Transformer une image en embedding (liste de 768 nombres) |
| arctic_v1 | Snowflake Arctic Embed L v2, gelé, 1024 dimensions, multilingue | Snowflake/snowflake-arctic-embed-l-v2.0 | Transformer un texte en embedding (liste de 1024 nombres) |
| vlm-validator_v1 | Modèle vision-langage de pointe (Gemini 2.0 Flash via OpenRouter) | google/gemini-2.0-flash-exp | Valider qu'une image vendeur correspond bien à un candidat trouvé |
| llm-writer_v1 | Grand modèle de langage rédacteur (Gemini Flash via OpenRouter) | google/gemini-2.0-flash-exp | Rédiger un titre et une description d'annonce |

Précisions sur ces modèles externes :

- « Gelé » signifie que le modèle est utilisé tel quel, sans réentraînement sur nos données. La
  fiche e1 note que ce gel est une limite à lever si l'écart de qualité mesuré dépasse 5 points.
- Arctic Embed traite au maximum 256 mots par texte (un compromis qui le rend environ quatre fois
  plus rapide qu'avec une limite de 512 mots).
- « Zero-shot » veut dire que le modèle e3 valide une correspondance sans entraînement spécifique,
  uniquement à partir de sa culture générale. La fiche note un coût d'environ 0,0001 dollar par
  appel et une latence de 1 à 3 secondes.
- Le modèle e4 rédige à partir d'éléments factuels fournis (un « ancrage » dans les avis clients),
  et sa fiche signale un risque d'invention si cet ancrage est pauvre.

### Livrable 2 : la visualisation t-SNE des embeddings texte

Ce livrable n'est généré que si les embeddings texte du jeu de validation existent (fichier
`text_arctic_val.npy`). Le script tire au hasard un échantillon de **5000 produits** (paramètre
`TSNE_N_SAMPLES = 5000`), récupère leur catégorie réelle, puis applique t-SNE avec une
**perplexité de 30** (paramètre `TSNE_PERPLEXITY = 30`). La perplexité règle la taille du voisinage
pris en compte lors de la projection. Le tirage au hasard est rendu reproductible par une graine
fixe, c'est-à-dire un point de départ figé pour le générateur de nombres aléatoires.

Le résultat est une image, `reports/09_explainability/tsne_text.png` : un nuage de points où chaque
catégorie a sa couleur. Si les couleurs forment des groupes nets et bien séparés, cela confirme à
l'œil que le modèle distingue correctement les catégories.

Une partie « t-SNE vision » est prévue dans le code mais n'est pas encore implémentée : si les
embeddings d'images du jeu de validation existent, le script signale simplement qu'il faudrait la
coder, sans produire d'image. La visualisation t-SNE livrée concerne donc uniquement le texte.

### Livrable 3 : l'attribution SHAP sur la forêt aléatoire (m3)

Ce livrable n'est généré que si le modèle m3 (la forêt aléatoire, fichier `m3_rf_v1.joblib`) existe.
Le script tire au hasard un échantillon de **1000 produits** (paramètre `SHAP_N_SAMPLES = 1000`)
parmi les embeddings texte, puis lance `TreeExplainer`, la variante de SHAP adaptée aux modèles à
base d'arbres. Il produit une image récapitulative, `reports/09_explainability/shap_m3_summary.png`
(un *summary plot*), qui montre les variables les plus influentes sur la décision, jusqu'à 20
affichées.

À noter : l'entrée du modèle m3 n'est pas un texte lisible mais l'embedding, c'est-à-dire la liste
des 1024 nombres. SHAP attribue donc une contribution à chacune de ces 1024 dimensions numériques.
Ces dimensions n'ont pas de nom parlant, mais le graphique montre lesquelles pèsent le plus dans la
décision et permet de vérifier que le modèle s'appuie sur un ensemble structuré de signaux, pas sur
un comportement erratique.

### Idée fondatrice

L'ensemble repose sur un principe cohérent avec tout le projet : un modèle non explicable n'est pas
acceptable en production face à un particulier. Le vendeur doit pouvoir comprendre pourquoi on lui
suggère une catégorie et pourquoi le système juge certains produits similaires. Le t-SNE qui montre
des groupes de catégories bien séparés est cohérent avec un bon score de classification.

---

## 4. Résultats mesurés

- **12 fiches modèle générées** : 8 modèles internes (m1 à m8) et 4 modèles externes (e1 à e4).
  Cette documentation systématique assure la traçabilité de chaque brique du système.
- **t-SNE texte** : les catégories forment des groupes visuellement séparés. C'est une confirmation
  visuelle d'un bon score de classification : si les catégories se mélangeaient sur l'image, aucun
  classifieur ne pourrait bien les distinguer. Ici, l'œil confirme la métrique.
- **SHAP sur m3** : les variables les plus influentes sont représentées dans l'image récapitulative
  `shap_m3_summary.png`.

> Drapeau slide. Chiffres à afficher : « 12 fiches modèle pour la gouvernance », « t-SNE :
> catégories visuellement séparées, ce qui confirme le score F1 », « SHAP : variables les plus
> influentes par décision ». Capture à montrer : le nuage t-SNE coloré par catégorie (très parlant,
> on voit que le modèle sépare bien), accompagné de l'image récapitulative SHAP et d'une fiche
> modèle.

---

## 5. Analyse critique : état de l'art comparé à notre travail

**Points solides :**

- Explicabilité sur trois plans complémentaires : global avec SHAP (quelles informations comptent),
  géométrique avec t-SNE (les groupes de catégories sont-ils nets), et gouvernance avec les fiches
  modèle. Les trois angles attendus sont couverts.
- Cohérence entre la métrique chiffrée et le visuel : le t-SNE confirme à l'œil le score de
  classification mesuré, ce qui est à la fois rare et convaincant.
- 12 fiches modèle, soit une traçabilité complète, utile pour justifier les choix techniques.
- Génération tolérante aux manques : aucun livrable ne dépend d'un autre de façon bloquante.

**Limites assumées :**

- SHAP est calculé sur le modèle m3 (la forêt aléatoire), alors que ce modèle a été écarté du
  service en production car peu efficace en grande dimension. SHAP explique donc un modèle
  *représentatif* à base d'arbres, et non directement le modèle de voisinage finalement servi. Ce
  dernier s'explique d'ailleurs naturellement autrement : en montrant ses voisins, ce que fait déjà
  la recherche de produits similaires. Ce point mérite d'être clarifié à l'oral.
- Pas d'explication par prédiction *en direct*. Le vendeur voit les candidats, leurs scores et le
  verdict du modèle vision-langage, mais pas une décomposition SHAP au moment de la requête.
  L'explicabilité est donc produite hors ligne, sous forme de rapports, et n'est pas intégrée à
  l'interface utilisateur.
- t-SNE sur un échantillon de 5000 points : suffisant pour visualiser, mais pas exhaustif. UMAP,
  qui préserve mieux la structure d'ensemble, serait un bon complément.
- La visualisation t-SNE des images n'est pas encore implémentée : seule celle du texte est
  réellement produite.

---

## 6. Références

- Lundberg et Lee, *A Unified Approach to Interpreting Model Predictions (SHAP)* :
  https://arxiv.org/abs/1705.07874
- SHAP, documentation de `TreeExplainer` : https://shap.readthedocs.io/en/latest/
- van der Maaten et Hinton, *Visualizing Data using t-SNE* :
  https://www.jmlr.org/papers/v9/vandermaaten08a.html
- Mitchell et al., *Model Cards for Model Reporting* : https://arxiv.org/abs/1810.03993

---

### En une phrase, pour la défense

« Nous expliquons nos modèles sur trois plans : SHAP indique quelles informations poussent vers une
catégorie, t-SNE permet de voir que les catégories forment des groupes bien séparés (ce qui confirme
visuellement notre score F1), et 12 fiches modèle documentent chaque brique et ses limites. Le
principe est simple : un modèle inexplicable n'est pas acceptable face à un particulier. »
