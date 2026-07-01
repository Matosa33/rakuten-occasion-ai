# 16 - Explicabilité et interprétabilité

> L'objectif de ce composant est de pouvoir **expliquer pourquoi** le système décide ce qu'il
> décide : pourquoi telle catégorie est proposée, pourquoi tels produits sont jugés similaires, et
> de documenter chaque modèle utilisé. Un modèle dont personne ne peut expliquer le comportement
> n'est pas acceptable quand il s'adresse à un particulier qui revend un objet.

> Note d'organisation. Ce document couvre **deux niveaux** d'explicabilité, complémentaires et de
> natures différentes. Le premier, **hors ligne** (sections 1 à 5), produit des rapports une fois
> pour toutes pour la gouvernance : SHAP, t-SNE et fiches modèle. Le second, **en direct dans la
> fiche d'annonce** (section 7), expose au vendeur, requête par requête, la
> **provenance de chaque champ**, l'**étiquette « estimé par IA »** sur le prix concerné et un
> **signal de confiance / drapeau** quand le modèle exact reste à confirmer. Cette seconde partie
> couvre l'explication par prédiction en direct : elle fait partie intégrante de l'interface.

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
| m6_fusion_v1 | Fusion adaptative (moyenne pondérée des probabilités) | Combiner les quatre classifieurs précédents (SVM, forêt aléatoire, réseau de neurones, TF-IDF) | Coût d'inférence multiplié par quatre, à n'adopter que si le gain dépasse +0,02 de score F1 |
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

Pour le modèle TF-IDF + LinearSVC (`m5_tfidf_linsvc_v1`), la fiche indique des performances
mesurées : F1 pondéré sur le test de 0,9503,
F1 macro de 0,9375, et une erreur de calibration attendue (ECE) de 0,0092. L'ECE mesure l'écart
entre la confiance annoncée et la justesse réelle ; plus elle est faible, plus les probabilités
annoncées sont honnêtes.

Les quatre modèles externes réutilisés :

| Fiche | Type | Source | Rôle |
|---|---|---|---|
| siglip_v1 | SigLIP base ViT-B/16, gelé, 768 dimensions | google/siglip-base-patch16-224 | Transformer une image en embedding (liste de 768 nombres) |
| arctic_v1 | Snowflake Arctic Embed L v2, gelé, 1024 dimensions, multilingue | Snowflake/snowflake-arctic-embed-l-v2.0 | Transformer un texte en embedding (liste de 1024 nombres) |
| vlm-validator_v1 | Modèle vision-langage de pointe via OpenRouter | OpenRouter (source fixée dans la fiche générée) | Valider qu'une image vendeur correspond bien à un candidat trouvé |
| llm-writer_v1 | Grand modèle de langage rédacteur via OpenRouter | OpenRouter (source fixée dans la fiche générée) | Rédiger un titre et une description d'annonce |

> Avertissement de cohérence à connaître pour la défense. Le générateur de fiches modèle
> (`src/explain/01_shap_tsne_modelcards.py`) inscrit encore `google/gemini-2.0-flash-exp` comme
> source pour `vlm-validator_v1` et `llm-writer_v1`. Or le **modèle réellement appelé en production**
> par le pipeline photo a changé : le VLM par défaut est désormais `qwen/qwen3.5-flash-02-23`
> (variable d'environnement `PHOTO_VLM_MODEL` dans `src/vlm/photo_extraction.py`, réutilisée par la
> passe d'identification raisonnée via `PHOTO_VLM_IDENTIFY_MODEL`). Les fiches modèle décrivent donc
> la **famille** « VLM/LLM de pointe via OpenRouter » correctement, mais la valeur exacte écrite dans
> la fiche est en retard sur le code d'exécution. Ce point est à corriger dans le générateur de fiches
> pour que la traçabilité reste exacte ; il est signalé ici en toute transparence.

Précisions sur ces modèles externes :

- « Gelé » signifie que le modèle est utilisé tel quel, sans réentraînement sur nos données. La
  fiche de l'encodeur d'image (SigLIP) note que ce gel est une limite à lever si l'écart de
  qualité mesuré dépasse 5 points.
- Arctic Embed traite au maximum 256 mots par texte (un compromis qui le rend environ quatre fois
  plus rapide qu'avec une limite de 512 mots).
- « Zero-shot » veut dire que le validateur vision-langage valide une correspondance sans
  entraînement spécifique, uniquement à partir de sa culture générale. La fiche note un coût
  d'environ 0,0001 dollar par appel et une latence de 1 à 3 secondes.
- Le rédacteur (grand modèle de langage) rédige à partir d'éléments factuels fournis (un
  « ancrage » dans les avis clients), et sa fiche signale un risque d'invention si cet ancrage
  est pauvre.

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

### Livrable 3 : l'attribution SHAP sur la forêt aléatoire

Ce livrable n'est généré que si la forêt aléatoire (fichier `m3_rf_v1.joblib`) existe.
Le script tire au hasard un échantillon de **1000 produits** (paramètre `SHAP_N_SAMPLES = 1000`)
parmi les embeddings texte, puis lance `TreeExplainer`, la variante de SHAP adaptée aux modèles à
base d'arbres. Il produit une image récapitulative, `reports/09_explainability/shap_m3_summary.png`
(un *summary plot*), qui montre les variables les plus influentes sur la décision, jusqu'à 20
affichées.

À noter : l'entrée de cette forêt aléatoire n'est pas un texte lisible mais l'embedding,
c'est-à-dire la liste
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

- **12 fiches modèle générées** : 8 modèles internes (construits dans le projet) et 4 modèles
  externes (réutilisés tels quels). Cette documentation systématique assure la traçabilité de
  chaque brique du système.
- **t-SNE texte** : les catégories forment des groupes visuellement séparés. C'est une confirmation
  visuelle d'un bon score de classification : si les catégories se mélangeaient sur l'image, aucun
  classifieur ne pourrait bien les distinguer. Ici, l'œil confirme la métrique.
- **SHAP sur la forêt aléatoire** : les variables les plus influentes sont représentées dans
  l'image récapitulative `shap_m3_summary.png`.

> Chiffres clés à retenir : « 12 fiches modèle pour la gouvernance », « t-SNE :
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

- SHAP est calculé sur la forêt aléatoire, alors que ce modèle a été écarté du
  service en production car peu efficace en grande dimension. SHAP explique donc un modèle
  *représentatif* à base d'arbres, et non directement le modèle de voisinage finalement servi. Ce
  dernier s'explique d'ailleurs naturellement autrement : en montrant ses voisins, ce que fait déjà
  la recherche de produits similaires. Ce point mérite d'être clarifié à l'oral.
- Pas de décomposition SHAP *en direct*. Le vendeur ne voit pas, au moment de la requête, une
  attribution chiffrée par variable d'embedding. SHAP reste un livrable hors ligne. **En revanche**,
  une explicabilité en direct d'une autre nature est pleinement intégrée à
  l'interface : la provenance de chaque champ, l'étiquette « prix neuf estimé par IA » et
  le drapeau « modèle à confirmer ». Elle est décrite en détail à la section 7. Autrement dit, la
  décomposition SHAP par prédiction n'est pas faite en direct, mais l'explication par prédiction,
  elle, existe bien à l'écran.
- t-SNE sur un échantillon de 5000 points : suffisant pour visualiser, mais pas exhaustif. UMAP,
  qui préserve mieux la structure d'ensemble, serait un bon complément.
- La visualisation t-SNE des images n'est pas encore implémentée : seule celle du texte est
  réellement produite.

---

## 7. Explicabilité en direct dans la fiche d'annonce

Cette section décrit la part de l'explicabilité qui n'est **pas** un rapport hors ligne, mais qui
s'affiche au vendeur, requête par requête, au moment où il prépare son annonce. Elle
repose sur un principe simple : **chaque information montrée doit dire d'où elle
vient, et tout ce qui est deviné par l'IA doit être affiché comme tel, jamais comme un fait**. C'est
la traduction concrète, côté produit, de la règle « ancré avant génératif » du projet : on s'appuie
en priorité sur la connaissance réelle (le catalogue, la photo, le texte du vendeur) et on étiquette
honnêtement ce qui relève d'une estimation.

### 7.1 La provenance par champ : chaque ligne de la fiche dit d'où elle vient

Le cœur de cette explicabilité est la **provenance**, c'est-à-dire l'origine de chaque champ de la
fiche structurée (« Marque », « Capacité », « Type de produit »…). Le module pur
`src/serving/listing_fill.py` (fonction `assemble_listing`) attache à chaque champ une étiquette de
source, et l'interface (`frontend/src/components/MarketplaceListing.tsx`) l'affiche sous forme d'un
petit badge coloré à côté du nom du champ. Le but est qu'un vendeur particulier comprenne d'un coup
d'œil ce qui a été **lu sur sa photo**, ce qui vient du **catalogue**, et ce qui n'est qu'une
valeur **typique à vérifier**.

Il existe exactement **cinq provenances**, définies dans le code comme des constantes lisibles :

| Provenance (libellé affiché) | Constante (code) | Signification | Fiabilité |
|---|---|---|---|
| observé | `SRC_OBSERVED` | Lu directement sur la photo du vendeur par le modèle vision-langage | La plus fiable pour *cet* objet précis |
| catalogue | `SRC_CATALOG` | Spécification du produit catalogue correctement apparié | Fiable **si** le match est correct |
| typique-à-vérifier | `SRC_TYPICAL` | Valeur imputée à partir des produits voisins, **non affirmée comme certaine** | À confirmer par le vendeur |
| catégorie | `SRC_CATEGORY` | Déduit de la catégorie votée (par ex. le « Type de produit ») | Indicatif |
| vendeur | `SRC_SELLER` | Saisi ou choisi par le vendeur lui-même (état, année d'achat) | Donnée fournie par l'humain |

L'ordre de priorité quand plusieurs sources pourraient renseigner un même champ est volontaire et
documenté dans `value_with_source` : **observé (photo) d'abord, puis catalogue (si le match est
fiable), puis typique à vérifier**. La logique sous-jacente est qu'une information vue sur l'objet
réel l'emporte toujours sur une information déduite d'un produit ressemblant. Point crucial pour
l'anti-invention : si le match catalogue **n'est pas** jugé fiable (score sous le seuil de 0,60),
une spécification issue du candidat n'est jamais présentée comme « catalogue » mais comme
« typique-à-vérifier ». On ne fait jamais passer une supposition pour un fait.

Cette discipline est renforcée par le cas du **catalog-miss** (le produit n'est pas, ou mal, présent
au catalogue). Dans ce cas, le pipeline (`src/api/main.py`, endpoint `/identify`) ne traite **pas**
les spécifications du candidat le plus proche comme des faits : la fiche est alors bâtie sur
l'observé (photo) plus la catégorie, et le vendeur voit un bandeau d'avertissement (détaillé plus
bas). On évite ainsi l'erreur grossière qui consiste à habiller un objet avec les caractéristiques
d'un sosie d'une autre génération.

Le champ `visible_text` (texte brut lu par OCR, souvent un titre recopié ou un filigrane de type
« leboncoin ») est **délibérément exclu** de l'affichage : c'est du bruit, pas une caractéristique
produit.

### 7.2 Les facettes sourcées de la passe d'identification raisonnée

Au-delà des champs venant directement de la photo ou du catalogue, une **passe
d'identification raisonnée** (`src/vlm/reasoned_identification.py`) intervient. Le principe de répartition des
rôles est important pour l'explicabilité : **le retriever apporte la connaissance** (les 15
candidats catalogue réels les plus proches) et **le modèle vision-langage apporte le jugement** (il
choisit, à partir des photos du vendeur et des 15 fiches résumées en texte, quel candidat correspond
le mieux et quelles caractéristiques retenir). Un seul appel à l'API OpenRouter est effectué, en mode
déterministe (température 0, graine fixe, raisonnement désactivé) pour que le même cas redonne le
même résultat.

Chaque caractéristique (« facette ») que ce modèle produit **doit obligatoirement citer sa source**,
sous l'une de trois formes contrôlées par le code (`SourcedFacet`) :

- un **entier** qui est l'index d'une fiche candidate réelle → la facette est rattachée au
  **catalogue** réel et reste vérifiable (on sait quelle fiche l'a fournie) ;
- la chaîne **`observed`** → la caractéristique a été **vue sur la photo** du vendeur ;
- la chaîne **`analogy`** → la caractéristique est **estimée par analogie** avec des produits
  comparables lorsque le produit exact manque ; elle est traitée comme une **estimation, jamais comme
  un fait**.

Le garde-fou correspondant est strict et codé dans `_parse` : une facette dont la source est
invalide (ni `observed`, ni `analogy`, ni un index de candidat valide) est **purement et simplement
jetée**. Le système refuse donc d'afficher une caractéristique qu'il ne peut pas raccrocher à une
origine. Quand la fiche finale est assemblée (dans `/identify`), seules les facettes de source
`observed` (rattachées à l'objet réel) et celles dont l'index pointe une fiche réelle **du produit
effectivement retenu** sont injectées comme données ; les facettes `analogy` ne sont pas injectées
comme faits, conformément à l'anti-invention.

### 7.3 L'étiquette « estimé par IA » sur le prix concerné

Le prix suggéré suit une cascade à cinq niveaux (`src/pricing/01_algorithmique.py`,
détaillée dans la documentation pricing) dont chaque niveau est **transparent** : la décote selon
l'état et la dépréciation selon l'âge sont **100 % déterministes** (de simples multiplications
documentées), il n'y a aucun modèle de prix opaque. Le seul élément qui peut être une **estimation
de l'IA** est, le cas échéant, l'**ancre de prix neuf** du niveau **L1.5**.

C'est précisément ce niveau, et lui seul, qui porte une étiquette honnête. Dans l'interface
(`MarketplaceListing.tsx`), le libellé de confiance du prix vaut :

- `L1` → « Confiance élevée (prix catalogue) » : le prix part d'un **prix catalogue réel** ;
- `L1.5` → « **Prix neuf estimé par IA** » : le prix part d'une **ancre estimée par l'IA**, puis
  décotée de façon déterministe ;
- `L2` → « Confiance moyenne (produits similaires) » ;
- `L3` → « Estimation par catégorie » ;
- `L4` → fiche sans prix calculable, l'interface affiche « **Prix à fixer (saisie manuelle)** » au
  lieu d'un trompeur « 0,00 € ».

L'idée directrice est qu'on ne masque jamais le fait qu'un prix repose sur une estimation : si l'IA
a fourni l'ancre, le vendeur le lit en toutes lettres. Et même au niveau L1.5, la part « estimée »
se limite à l'ancre du prix neuf ; toute la mécanique de décote reste vérifiable à la main, ce qui
préserve la promesse « pas de pricing ML opaque ». Le texte d'explication renvoyé avec le prix
indique d'ailleurs explicitement « Prix neuf estimé par IA : … $, dépréciation …/an sur … an(s),
ajustement … ». Quand le vendeur n'a pas saisi d'année d'achat, l'interface signale aussi en clair
que l'âge est **supposé à 2 ans** et invite à le préciser pour affiner ; l'hypothèse n'est jamais
silencieuse.

### 7.4 Le signal de confiance et le drapeau « modèle à confirmer »

Le dernier pilier de l'explicabilité en direct est un **signal de confiance** assorti, si besoin,
d'un **drapeau actionnable**. Deux mécanismes coexistent et il faut bien les distinguer car ils ne
mesurent pas la même chose.

**Le pourcentage de confiance affiché** correspond à la part du **vote des k plus proches voisins
sur la catégorie fine** (le classifieur champion du projet). L'interface ne l'affiche **que s'il est
net**, c'est-à-dire supérieur ou égal à **60 %** (`idConfident` dans `MarketplaceListing.tsx`). Le
raisonnement est subtil mais honnête : un pourcentage bas ne veut pas dire « ce n'est sans doute pas
un casque » ; il reflète le plus souvent une **fragmentation du vote** entre plusieurs modèles très
proches (la catégorie est sûre, mais le **produit exact** est ambigu, par exemple un casque dont le
vote se disperse à 34 %). Afficher « 34 % de confiance » serait alors trompeur. On préfère donc, dans
ce cas, **ne pas montrer un chiffre trompeur** et porter l'incertitude par un bandeau explicite.

**Le drapeau « Modèle à confirmer »** s'affiche quand l'identification du produit exact est jugée
incertaine, soit parce que le vote est fragmenté (pourcentage sous 60 %), soit parce que la passe
raisonnée a estimé qu'une **question discriminante** était nécessaire (`ask_question`). Le bandeau
est **actionnable** : il reprend, si elle existe, la question précise formulée par l'IA
(`facet_question`, par exemple sur la capacité ou la variante exacte) ; sinon, il invite le vendeur à
préciser le nom du modèle ou à ajouter une photo de l'étiquette ou de la boîte. C'est de
l'explicabilité utile : on dit au vendeur **pourquoi** on doute et **comment** lever le doute.

À côté de ce drapeau, le **bandeau catalog-miss** (« Produit *estimé* … - absent du catalogue. Prix
et caractéristiques à vérifier. ») prévient quand le produit n'a pas été retrouvé au catalogue et que
la fiche est donc une estimation d'ensemble, pas une recopie de fiche existante.

Enfin, le parcours vendeur tire parti de ces signaux pour décider quoi montrer : si l'IA est sûre
(statut `identified`), on enchaîne directement vers la fiche ; sinon on présente les candidats. Dans
tous les cas, un bouton « **Ce n'est pas le bon produit ? Voir les autres résultats** » reste
disponible sur la fiche : le dernier mot revient toujours à l'humain.

### 7.5 Observabilité métier : on peut relire ce que le pipeline a vraiment fait

L'explicabilité ne s'arrête pas à l'écran du vendeur : côté exploitation, le pipeline émet des
**logs structurés** (via `structlog`, dans `src/api/main.py`) qui rendent chaque décision
inspectable a posteriori, en complément des métriques HTTP Prometheus déjà en place. Deux événements
métier sont journalisés :

- `identify_done` : statut, nombre de candidats, score du top-1, catégorie fine et sa confiance,
  présence et résultat de la passe raisonnée (`reasoned`, `reordered`, `catalog_miss`,
  `anchor_usd`, `ask_question`, `family_conf`), complétude de la fiche, et les temps des appels
  (`extraction_ms`, `reason_ms`) ;
- `price_done` : niveau de cascade réellement utilisé, méthode, prix suggéré, présence d'une ancre
  IA (`has_anchor`), catégorie et état.

L'intérêt est concret et non décoratif : on peut **lire** le taux de catalog-miss, la fréquence
d'usage du niveau L1.5, ou repérer où part la latence, plutôt que de raisonner sur des impressions.

### 7.6 Ce que mesure l'évaluation de qualité de fiche

Pour ne pas se contenter d'anecdotes (doctrine « mesurer sur de vraies sorties »), un protocole
reproductible (`scripts/mesure_qualite_fiche.py`, sortie dans
`reports/09_fiche_quality/mesure_fiche.{json,md}`) fait passer le **panel réel** de photos
(`data/photos_eval/`, où le nom de chaque dossier sert de vérité-terrain) par l'API, **photo seule**,
sans précisions de texte. Les résultats mesurés confirment que cette explicabilité en direct repose
sur un socle d'identification solide :

- **Taux d'identification : 90,3 %** (au moins 50 % des tokens clés du nom de produit retrouvés dans
  la famille jugée par l'IA et le titre du top-1), avec un **rappel moyen de 78 %** ;
- **Complétude de la fiche : 0,84 en moyenne** et **0,83 en médiane** ;
- **Passe raisonnée présente : 100 %** ; **catalog-miss : 28 %** ; **question discriminante posée :
  11 %** ;
- **Niveaux de prix** sur le panel : **L1 = 42** (prix catalogue réel) et **L1.5 = 51** (ancre
  estimée par IA).

Les **9 produits non identifiés** sont tous expliqués (limite de perception du modèle sur des
produits sans marquage visible, catalog-miss légitime, ou nom de dossier ambigu, qui est un artefact
de mesure). Cette transparence sur les échecs fait partie de l'explicabilité : on documente non
seulement quand le système réussit, mais aussi **pourquoi** il échoue quand il échoue.

### 7.7 Limites honnêtes de cette explicabilité en direct

Pour ne rien survendre :

- **La photo seule limite la perception du modèle exact** quand l'objet ne porte pas de marquage
  visible sur les clichés envoyés (par exemple un casque dont le logo est sur l'étui). Le modèle peut
  alors choisir un sosie avec aplomb. C'est précisément pour cela que le drapeau « modèle à
  confirmer » et le bouton « ce n'est pas le bon ? » existent : ils transforment une incertitude
  silencieuse en une action explicite pour le vendeur. Le **texte vendeur** (quand il nomme le
  produit) fait alors office de garde-fou déterminant : il est traité comme **autoritaire**
  (`_seller_text_best_match`) et fixe le produit indépendamment du modèle rapide.
- Le modèle rapide par défaut (`qwen/qwen3.5-flash-02-23`) **sous-déclenche** parfois le catalog-miss
  (il s'accroche à un sosie d'une autre génération) ; un modèle jugé plus fort ferait mieux et reste
  configurable par variable d'environnement, mais n'est pas câblé par défaut.
- Toute cette passe raisonnée est **best-effort et non bloquante** : en cas d'absence de clé API, de
  modèle indisponible ou de réponse inexploitable, le pipeline retombe simplement sur le classement
  du retriever et la cascade de prix habituelle, sans jamais planter ni afficher une fiche vide. La
  robustesse fait elle aussi partie de la confiance que l'on peut accorder au système.

---

## 8. Références

- Lundberg et Lee, *A Unified Approach to Interpreting Model Predictions (SHAP)* :
  https://arxiv.org/abs/1705.07874
- SHAP, documentation de `TreeExplainer` : https://shap.readthedocs.io/en/latest/
- van der Maaten et Hinton, *Visualizing Data using t-SNE* :
  https://www.jmlr.org/papers/v9/vandermaaten08a.html
- Mitchell et al., *Model Cards for Model Reporting* : https://arxiv.org/abs/1810.03993

---

### En une phrase, pour la défense

« Nous expliquons nos modèles sur deux niveaux. Hors ligne, pour la gouvernance : SHAP indique
quelles informations poussent vers une catégorie, t-SNE permet de voir que les catégories forment des
groupes bien séparés (ce qui confirme visuellement notre score F1), et 12 fiches modèle documentent
chaque brique et ses limites. En direct, dans la fiche d'annonce : chaque champ porte sa provenance
parmi cinq sources, le prix qui repose sur une estimation est étiqueté « prix neuf estimé par IA »,
et un drapeau « modèle à confirmer » dit au vendeur pourquoi on doute et comment lever le doute. Le
principe est simple : un modèle inexplicable n'est pas acceptable face à un particulier, et tout ce
qui est deviné doit être affiché comme tel, jamais comme un fait. »
