# 04 - Recherche par similarité (retrieval)

> Le moteur du produit : retrouver, parmi 3,16 millions de produits du catalogue, ceux qui
> ressemblent le plus à la photo et à la description fournies par le vendeur, vite et juste, puis
> lever le doute sans jamais inventer.

> La recherche ne s'arrête plus au classement brut. Le top-15 des candidats réels devient la
> matière d'une **passe d'identification raisonnée** : le moteur de recherche par similarité apporte
> la CONNAISSANCE (15 fiches réelles), un modèle multimodal apporte le JUGEMENT (lequel de ces 15 est
> le produit ?). À cela s'ajoute une règle d'autorité du **texte vendeur** et un **réordonnancement**
> du candidat choisi en tête de liste, pour que la fiche, le prix et la validation portent sur le
> bon produit. Ces trois mécanismes sont décrits en section 4. Ils ne remplacent pas le retrieval :
> ils le couronnent, et ils retombent proprement sur le classement retrieval brut en cas de
> défaillance (en mode best-effort, jamais bloquant).

---

## 1. La technologie : qu'est-ce que c'est et à quoi ça sert ?

### Le problème, expliqué à partir de zéro

Dans ce projet, chaque produit est d'abord transformé en une suite de nombres appelée vecteur
(un embedding). Un vecteur est une sorte de signature numérique : deux produits qui se ressemblent
ont des vecteurs proches, deux produits différents ont des vecteurs éloignés. Quand un vendeur
arrive avec une photo et un texte, on calcule le vecteur de son annonce, et il faut le comparer
aux vecteurs de tout le catalogue pour trouver les plus ressemblants.

Le souci est la taille du catalogue : 3,16 millions de produits. Comparer la signature du vendeur
à chacune des 3,16 millions de signatures, une par une, serait beaucoup trop lent pour répondre en
temps réel. La solution est un index : une structure de données qui range les vecteurs de façon
maligne, exactement comme l'index alphabétique à la fin d'un livre permet de trouver un mot sans
lire toutes les pages. Grâce à cet index, la recherche répond en une fraction de milliseconde au
lieu de parcourir tout le catalogue.

Ce composant repose sur quatre briques qui se complètent :

1. **L'index FAISS** : la structure rapide qui retrouve les voisins les plus proches d'un vecteur.
   FAISS (Facebook AI Similarity Search) est une bibliothèque spécialisée qui retrouve très vite
   les éléments les plus proches parmi des millions de vecteurs.
2. **La fusion RRF** : une méthode pour combiner plusieurs « points de vue » d'un produit (par
   exemple son texte et son image) en un seul classement unique et fiable.
3. **Les garde-fous OOD** : un système de détection qui repère un produit inconnu, c'est-à-dire
   absent du catalogue, pour avouer le doute au lieu de proposer une mauvaise correspondance.
   OOD veut dire « hors distribution » (Out Of Distribution), autrement dit un produit qui ne
   ressemble à rien de connu.
4. **Le mode Akinator** : quand plusieurs produits candidats sont presque aussi probables les uns
   que les autres, on pose la question, ou plutôt on demande l'observation, qui les départage.

### Pour aller plus loin (lecteur technique)

- **HNSW** (Hierarchical Navigable Small World) est le type d'index choisi. C'est un graphe à
  plusieurs couches : chaque vecteur est relié à un petit nombre de voisins. La recherche entre par
  une couche grossière où les sauts sont longs, puis descend vers des couches fines où les sauts
  sont courts. L'image juste est celle d'un itinéraire : on prend d'abord l'autoroute, puis la
  nationale, puis la petite rue. Résultat : un taux de bonnes réponses quasi parfait (recall
  supérieur ou égal à 0,95) en un temps qui croît de façon logarithmique avec la taille du
  catalogue, sur processeur classique, sans carte graphique.

- **RRF** (Reciprocal Rank Fusion, formalisé par Cormack en 2009) fusionne plusieurs classements
  avec la formule : score d'un document d égale la somme, sur chaque point de vue i, de
  1 divisé par (k plus le rang de d dans le point de vue i), avec k fixé à 60. Son intérêt majeur :
  il ne regarde que le rang d'un produit dans chaque classement, jamais son score brut. Il n'a donc
  pas besoin que les scores des différents points de vue soient sur la même échelle, ce qui le rend
  robuste quand un point de vue note de 0 à 1 et un autre de 0 à 100.

- **OOD** : on règle un seuil de confiance à partir de la courbe précision/rappel, en penchant
  volontairement vers la précision. Une fausse identification (affirmer le mauvais produit) coûte
  plus cher qu'un doute exprimé à tort, donc on préfère un système prudent.

---

## 2. État de l'art : ce que fait le reste du monde

- **HNSW** domine le besoin « taux de bonnes réponses supérieur à 0,95 en quelques millisecondes »
  quand la qualité prime sur la mémoire consommée. À l'inverse, un index appelé IVF_PQ compresse
  fortement les vecteurs (utile au-delà d'environ 20 millions de vecteurs) mais au prix d'un taux de
  bonnes réponses plus faible.
- **La recherche approchée** (dite ANN, Approximate Nearest Neighbors) est plusieurs ordres de
  grandeur plus rapide que la recherche exacte qui compare tout (dite recherche « Flat », à plat).
  On accepte de rater très rarement un voisin pour gagner énormément en vitesse.
- **RRF** est une technique standard pour fusionner une recherche dense (par signatures numériques)
  avec une recherche par mots-clés, ou pour combiner plusieurs points de vue d'un même objet.
- **La détection OOD** s'appuie sur des seuils appliqués aux scores de similarité, et sur des
  signaux contradictoires (par exemple un premier candidat très bien noté mais entouré de candidats
  de catégories incohérentes entre elles).

---

## 3. Notre implémentation : exactement ce que nous avons fait

### a) Les index FAISS (fichier `src/retrieval/01_faiss_indices.py`)

Nous construisons et comparons trois index sur les mêmes vecteurs. La mesure de proximité utilisée
est le produit scalaire (inner product). Comme nos vecteurs ont été normalisés au préalable (mis à
une longueur de 1), ce produit scalaire est mathématiquement égal au cosinus, c'est-à-dire à
l'angle entre deux signatures : plus l'angle est petit, plus les produits se ressemblent.

| Index | Paramètres exacts | Usage retenu |
|---|---|---|
| **Flat (exact)** | comparaison exhaustive, force brute | référence d'évaluation (taux de bonnes réponses de 100 %) |
| **HNSW** | `M=32`, `efConstruction=200`, `efSearch=64` | servi en production |
| **IVF_PQ** | `nlist=1024` (environ la racine carrée du nombre de vecteurs), `m=32` sous-quantizers, `nprobe=16` | écarté (taux de bonnes réponses trop bas à notre échelle) |

**Ce que veulent dire les paramètres de HNSW, le détail qui compte :**

- **`M=32`** est le nombre de voisins (de connexions) que chaque vecteur conserve dans le graphe.
  Plus M est grand, plus le graphe est richement connecté, donc plus le taux de bonnes réponses est
  élevé, mais plus la mémoire vive consommée augmente (chaque connexion se stocke). La valeur 32 est
  le palier où le taux de bonnes réponses plafonne pour nos données : passer à 64 doublerait presque
  la mémoire pour un gain négligeable.

- **`efConstruction=200`** est le nombre de candidats explorés au moment de construire le graphe.
  Plus cette valeur est haute, meilleurs sont les voisins retenus, mais plus la construction est
  lente. C'est un coût payé une seule fois, on peut donc se permettre d'être généreux avec 200.

- **`efSearch=64`** est le nombre de candidats explorés à chaque requête. C'est le bouton de réglage
  en direct du compromis vitesse contre précision : on peut le baisser pour répondre plus vite, ou
  le monter pour mieux trouver, sans jamais reconstruire l'index. La valeur 64 donne un taux de
  bonnes réponses de 0,948 pour une latence moyenne de 0,29 milliseconde par requête, notre point
  d'équilibre mesuré.

- **`nlist` et `nprobe` (paramètres de l'index IVF_PQ écarté)** : `nlist=1024` découpe l'espace des
  vecteurs en environ 1024 cellules ; `nprobe=16` n'en visite que 16 à chaque requête, ce qui est
  rapide mais fait rater tous les voisins tombés dans les cellules non visitées. C'est précisément
  ce qui explique son taux de bonnes réponses faible (0,415) à notre échelle.

### b) Fusion de plusieurs points de vue avec RRF (fichier `src/retrieval/02_multiview_rrf.py`)

La fonction interne `_rrf_fusion` applique la formule RRF (somme de 1 divisé par 60 plus le rang)
sur plusieurs classements, un par point de vue, pour produire un classement fusionné unique. La
constante k vaut 60, comme le préconise Cormack, et elle rend la fusion insensible aux scores bruts
en ne regardant que les rangs. Concrètement, on demande à l'index 50 voisins par point de vue
(paramètre `TOP_K_RETRIEVAL = 50`) pour avoir assez de matière à fusionner.

À ce jour, le point de vue actif est le texte. Le point de vue image (le catalogue encodé par un
modèle d'image) est prévu dans le code et s'activera quand les signatures d'image du catalogue
seront disponibles : le mécanisme RRF est déjà en place et accueillera ce second point de vue sans
modification.

> Précision sur les profondeurs de recherche, car deux valeurs cohabitent et désignent des choses
> différentes. Le banc d'essai de fusion (`02_multiview_rrf.py`) demande `TOP_K_RETRIEVAL = 50`
> voisins par point de vue, afin d'avoir assez de matière à fusionner. Le pipeline servi en
> production (`src/api/pipeline.py`) retourne lui `TOP_K_RETRIEVAL = 30` candidats triés par
> similarité (de quoi alimenter le défilement de l'interface vendeur). Parmi ces candidats, seuls
> les **15 premiers** sont transmis à la passe d'identification raisonnée décrite en section 5
> (constante `MAX_CANDIDATES = 15`), pour limiter la taille du contexte envoyé au modèle.

### c) Les garde-fous OOD à trois niveaux (fichier `src/retrieval/03_ood_guardrails.py`)

Deux fonctions de base sont fournies et réutilisables ailleurs dans l'application :

- `is_ood_top1(score, seuil)` applique un seuil absolu sur le score du meilleur candidat : si ce
  score est trop bas, le produit est probablement hors catalogue.
- `is_ambiguous_top12(s1, s2, gap=0.05)` détecte l'ambiguïté : si le meilleur et le deuxième
  candidat ont des scores trop proches (écart inférieur à 0,05), on ne peut pas trancher avec
  certitude.

En usage réel, la requête d'un vendeur est courte (une photo et quelques mots), donc son score de
similarité avec un produit du catalogue est systématiquement plus bas que la similarité mesurée
entre deux fiches catalogue complètes. Pour cette raison, nous présentons toujours les candidats au
vendeur (c'est l'humain qui valide), et nous affichons en plus un niveau de confiance à trois
paliers :

- score **supérieur ou égal à 0,60** : produit *identifié* ;
- score **entre 0,45 inclus et 0,60 exclu** : produit *à confirmer* ;
- score **inférieur à 0,45** : produit *incertain*.

### d) Le mode Akinator (fichier `src/retrieval/04_akinator_backend.py`)

Quand l'écart entre le premier et le deuxième candidat est inférieur à 0,05 (paramètre
`AMBIGUITY_GAP_THRESHOLD = 0.05`), souvent parce qu'il s'agit de variantes très proches d'un même
produit, on lève l'ambiguïté par observation dirigée, en quatre temps :

1. **Calculer les attributs qui distinguent les candidats.** On compare les métadonnées des
   meilleurs candidats (au plus 5, paramètre `TOP_K_AMBIG = 5`) : capacité de stockage, couleur,
   numéro de modèle, version, année, dimensions, et ainsi de suite. Pour chaque attribut, on mesure
   son pouvoir de séparation avec l'entropie de Shannon, une mesure de diversité : si tous les
   candidats ont la même valeur pour un attribut, cet attribut ne sert à rien (entropie nulle) ; si
   chaque candidat a une valeur différente, l'attribut sépare parfaitement (entropie maximale).
2. **Traduire l'attribut le plus séparateur en observation concrète à demander.** Le code associe
   chaque attribut à une instruction visuelle précise : « photographiez l'étiquette au dos »,
   « scannez le code-barres », « photographiez les connecteurs », etc. Si l'attribut n'a pas de
   correspondance prévue, on demande par défaut une vue arrière du produit.
3. **Re-noter les candidats** avec cette nouvelle information (cette étape est pilotée par l'API).
4. **Recommencer** jusqu'à ce que l'écart entre les deux meilleurs candidats dépasse 0,10
   (paramètre `CLARITY_GAP_THRESHOLD = 0.10`, le seuil au-delà duquel on considère la situation
   éclaircie), ou jusqu'à épuisement des observations possibles. Dans ce dernier cas, on bascule
   honnêtement en mode « produit non identifié, saisie assistée ».

> « On demande à VOIR, pas à savoir » : plutôt que de poser une question abstraite au vendeur, on
> lui demande une observation visuelle simple (une vue, une étiquette, un code-barres). C'est plus
> fiable, car on ne suppose pas que le vendeur connaisse les caractéristiques techniques du produit.

---

## 4. L'identification raisonnée : le top-15 devient la matière du jugement

Cette section décrit un mécanisme clé. Initialement, le retrieval produisait un classement et on
présentait le premier candidat. Le problème pratique : le tout premier voisin retrouvé n'est pas
toujours le bon produit. Sur une photo d'iPhone, par exemple, le candidat le mieux noté pouvait
être une coque d'iPhone (un accessoire dont le titre ressemble énormément), pas le téléphone. La
fiche, le prix et la validation se construisaient alors sur le mauvais objet.

L'idée répartit clairement les rôles : **le moteur de recherche par similarité apporte la
connaissance, le modèle apporte le jugement**. Le moteur de recherche sait quels 15 produits réels
du catalogue ressemblent le plus à l'annonce. Un modèle multimodal (vision + langage), lui, sait
regarder la photo du vendeur et décider lequel de ces 15 produits est réellement présent sur
l'image. On ne lui demande jamais d'inventer un produit : il choisit parmi les 15 candidats réels,
ou il avoue qu'aucun ne convient. C'est la doctrine « grounded avant génératif » poussée jusqu'au
bout.

### a) La passe d'identification raisonnée (fichier `src/vlm/reasoned_identification.py`)

La fonction `reason_identify(user_photo_paths, candidates, observed, seller_text)` réalise **un seul
appel** à l'API OpenRouter. Elle reçoit :

- **1 à 2 photos du vendeur** (constante `MAX_USER_PHOTOS = 2`), encodées en data-url base64 ;
- **les 15 fiches candidates RÉSUMÉES EN TEXTE** (titre tronqué à 140 caractères, marque, catégorie
  fine, attributs, prix, identifiant), pas les 15 images du catalogue. C'est un choix d'économie :
  envoyer 15 images coûterait beaucoup de jetons (tokens) pour un gain de jugement faible, alors que
  le résumé texte suffit à identifier le bon candidat ;
- **les attributs déjà observés** par le modèle d'extraction photo et **le texte vendeur**.

Le modèle par défaut est lu dans la variable d'environnement `PHOTO_VLM_IDENTIFY_MODEL` (repli sur
le modèle d'extraction, `qwen/qwen3.5-flash-02-23`). L'appel est rendu **reproductible** (température
fixée à 0, graine fixe, mode raisonnement désactivé), conformément au protocole de déterminisme du
projet. Il réutilise les fonctions `post_with_retry` et `_to_data_url` du module d'extraction photo :
pas de nouveau client HTTP, donc le retry exponentiel sur les erreurs 429/5xx est partagé.

Le modèle répond en **JSON strict** (le format est imposé par le texte du prompt, pas par un champ
natif de l'API), et le parsing est **tolérant** (JSON pur, JSON entre balises markdown, ou premier
objet `{...}` trouvé). Les champs produits sont notamment :

- `product_family` : la famille / le modèle du produit (texte court) ;
- `family_confidence` : la confiance du modèle dans cette famille (entre 0 et 1) ;
- `chosen_parent_asin` : l'identifiant du candidat retenu parmi les 15 ;
- `catalog_miss` : vrai si AUCUN des 15 candidats n'est le produit (y compris quand ce sont tous une
  autre génération / variante que ce qui est vu) ;
- `reference_new_price_usd` : une **ancre de prix NEUF estimée**, exprimée en dollars, ancrée sur les
  prix neufs PROPRES des candidats réels (accessoires et lots exclus), voir la sous-section sur le
  pricing plus bas ;
- `reference_new_confidence` et `price_anchor_evidence` : la confiance de cette ancre et la liste des
  index de fiches qui l'ont étayée (pour l'auditabilité) ;
- `ask_question` + `facet_question` : si une seule observation discriminante changerait la famille ou
  le prix, le modèle pose UNE question courte au vendeur ;
- `facets` : des facettes de produit, chacune **sourcée** (un index de fiche réelle, ou `observed`
  pour ce qui est lu sur la photo, ou `analogy` pour une valeur inférée d'un comparable).

### b) Les garde-fous anti-hallucination de la passe raisonnée

Le code valide (`_parse`) systématiquement la sortie du modèle, car un modèle, même contraint, peut
déraper. Les garde-fous, expliqués pour le POURQUOI :

- **Identifiant halluciné** : si `chosen_parent_asin` ne fait pas partie des 15 candidats ET que le
  modèle n'a pas déclaré de `catalog_miss`, on retombe sur le **premier candidat du retrieval**, MAIS
  on remet `family_confidence` à 0. Raison : le modèle n'a pas réellement endossé ce candidat, donc
  l'aval ne doit pas le traiter comme un fait certain. On garde le résultat retrieval, sans lui prêter
  une confiance qu'il n'a pas.
- **Facette à source invalide** : toute facette dont la provenance n'est ni `observed`, ni `analogy`,
  ni un index de fiche valide est **jetée**. On n'affiche jamais une caractéristique non sourçable.
- **Ancre de prix sans preuve** : l'ancre prix neuf est **conservée même sans evidence**. Ce n'est
  pas un fait catalogue mais une **estimation explicitement étiquetée** « prix neuf estimé par IA ».
  La garder vaut mieux que retomber sur une médiane de catégorie polluée (par exemple 11 € suggérés
  pour une montre qui en vaut 150).

### c) Le repli propre : best-effort, jamais bloquant

Si la clé API est absente, si le modèle est indisponible, si le JSON est inexploitable, ou si une
exception survient, `reason_identify` retourne `None`. Le pipeline garde alors le **classement
retrieval brut** et la **cascade de pricing habituelle**. Il n'y a jamais de plantage, jamais de
fiche vide. Cette discipline du best-effort garantit qu'ajouter de l'intelligence ne fragilise pas
le chemin nominal.

### d) Le texte vendeur fait autorité (fonction `_seller_text_best_match`, fichier `src/api/main.py`)

Le modèle rapide ignore parfois la consigne du texte vendeur. Or, quand le vendeur écrit lui-même
le nom de son produit, cette métadonnée est souvent plus fiable que la perception de la photo. On
ajoute donc une règle **déterministe**, indépendante du modèle : si le texte vendeur nomme un produit
présent dans les candidats, ce candidat est retenu d'office. Les conditions d'un match fort :

- au moins **2 tokens discriminants** du texte présents dans le titre du candidat, et
- au moins **50 % des tokens** du texte couverts.

Détail qui compte : on **garde les numéros de modèle même à un seul chiffre** (« Momentum 3 » contre
« 2.0 »), parce que c'est précisément le chiffre qui sépare deux variantes proches. Les mots non
discriminants (état, couleur, génériques) sont exclus par une liste de mots vides.

En cas d'égalité entre plusieurs candidats, on choisit celui au **prix représentatif** (le plus
proche de la médiane des candidats à égalité). Cela évite de bâtir la fiche sur une donnée corrompue,
par exemple un même « Momentum 3 » listé par erreur à 9755 $. Sur un texte vendeur vide, la fonction
ne fait rien (no-op total), donc zéro régression pour le flux photo seule.

Quand cette règle déclenche, l'endpoint `/identify` bascule en **branche « override vendeur »** : la
fiche est bâtie sur la fiche catalogue du produit nommé, et l'« observé » du VLM, qui portait peut-être
sur un autre produit, est écarté.

### e) Le réordonnancement du candidat choisi

Une fois le candidat retenu, soit par le texte vendeur (prioritaire), soit par la passe raisonnée,
on le **remonte en tête** de la liste des candidats. Concrètement (dans `/identify`), on cherche son
rang, et s'il n'est pas déjà premier, on le place en position 0 en décalant les autres. Tout l'aval
(fiche structurée, suggestion de prix, validation visuelle, « type de produit » affiché) porte alors
sur le **bon produit**, pas sur le premier voisin du retrieval qui pouvait être un accessoire.

Ce réordonnancement explique un comportement subtil du système : le score affiché et le classement
restent ceux du retrieval (transparence), mais le produit MIS EN AVANT est celui que le jugement a
choisi.

### f) Économie de latence

Le pipeline enchaînait potentiellement trois appels à des modèles : extraction photo, validation
visuelle du top-1, et la passe raisonnée. Pour ne pas allonger inutilement la réponse, on **saute le
3ᵉ appel** (le validateur visuel) lorsque la passe raisonnée a déjà tranché avec confiance (famille
confiante, sans catalog-miss). Le jugement de correspondance est alors déjà couvert.

### g) Observabilité métier

Au-delà des métriques HTTP Prometheus existantes, chaque requête produit un journal structuré
inspectable : l'événement `identify_done` consigne le statut, le nombre de candidats, le score du
top-1, la catégorie fine et sa confiance, si la passe raisonnée a tourné, si le candidat a été
réordonné, le catalog-miss, l'ancre prix, la question posée, la confiance famille, la complétude, et
les durées d'extraction et de raisonnement. L'événement `price_done` consigne le niveau de cascade,
la méthode, le prix suggéré et la présence d'une ancre. On peut ainsi LIRE ce que fait le pipeline
(taux de catalog-miss, usage du niveau L1.5, où part la latence), au lieu de deviner.

### h) Ce que cela change pour le prix et la fiche (renvoi)

La passe raisonnée alimente directement deux briques voisines, documentées en détail ailleurs mais
résumées ici car elles dépendent du retrieval :

- **Pricing** (`src/pricing/01_algorithmique.py`) : un niveau **L1.5** a été inséré dans la cascade,
  ENTRE le prix catalogue réel (L1) et les médianes de voisins (L2/L3). L1.5 applique au **prix neuf
  estimé par l'IA** la MÊME décote déterministe (multiplicateur d'état × dépréciation par âge). Seule
  l'ancre est une estimation ; la décote reste 100 % transparente. Les médianes de voisins ont été
  rétrogradées car, polluées par des accessoires et des lots, elles sous-évaluaient gravement (le
  fameux 6 € pour une montre à 150 €). Les multiplicateurs d'état sont : neuf 1,00 ; très bon 0,75 ;
  bon 0,55 ; correct 0,35 ; pour pièces 0,15. Des garde-fous ont été ajoutés : on relève une médiane
  absurdement basse vers un plancher (anti sous-évaluation), on ignore un prix catalogue
  drastiquement sous l'ancre IA (top-1 = accessoire mal apparié, ratio 0,2), et on écarte un prix
  catalogue aberrant (plus de 4 fois la médiane des voisins, avec au moins 3 voisins, signe d'une
  donnée corrompue type 9755 $).
- **Fiche exhaustive** (`src/serving/listing_fill.py`) : les facettes jugées par l'IA sont fusionnées
  aux facettes catalogue, chacune avec sa provenance (observé, catalogue, typique-à-vérifier,
  catégorie, vendeur), et la complétude se mesure désormais PAR CATÉGORIE FINE (une enceinte n'est
  plus pénalisée pour l'absence d'une « capacité » qui ne la concerne pas).

---

## 5. Résultats mesurés (1 000 requêtes de test, sauf indication contraire)

Le catalogue indexé compte exactement 3 156 705 produits, chacun représenté par un vecteur de
1024 dimensions. La latence indiquée est la latence moyenne par requête.

| Index | Taux de bonnes réponses (recall@1) | Latence par requête | Taille sur disque | Verdict |
|---|---|---|---|---|
| Flat (exact) | **1,000** | 23,03 ms | 12,3 Go | référence |
| **HNSW** | **0,948** | **0,29 ms** | 13,2 Go | servi en production |
| IVF_PQ | 0,415 | 0,19 ms | 0,12 Go | écarté (taux trop bas) |

Le recall@1 désigne la proportion de requêtes pour lesquelles le tout premier voisin proposé est
bien le bon. Pour HNSW, le taux monte encore quand on regarde plus de voisins : 0,972 sur les 5
premiers, 0,976 sur les 10 premiers.

Autres mesures :

- **Catégorie correcte parmi les premiers résultats** : sur 1 000 requêtes, la bonne catégorie
  figure dans le premier résultat dans 94,2 % des cas, et dans les 5 premiers dans 98,2 % des cas.
- **Seuil OOD calibré à 0,600** : mesuré sur 5 000 requêtes, ce seuil donne une précision de 0,953
  et un rappel de 0,988. Autrement dit, quand le système affirme avoir identifié un produit, il a
  raison dans 95,3 % des cas, et il accepte d'identifier 98,8 % des produits réellement présents au
  catalogue. Le réglage a été choisi pour maximiser une mesure (le F0.5) qui privilégie la précision
  sur le rappel, conformément à notre prudence assumée.
- **Mode Akinator** : sur 2 000 requêtes, l'écart entre les deux meilleurs candidats est jugé
  ambigu (inférieur à 0,05) dans 75 % des cas, soit 1 500 requêtes. Parmi ces cas ambigus, le
  système trouve au moins une observation à proposer pour 1 492 d'entre eux.

### Qualité de fiche bout-en-bout sur photos réelles

Les chiffres ci-dessus mesurent le moteur de recherche isolé sur des vecteurs catalogue. Une mesure
complémentaire évalue la qualité **bout-en-bout sur de vraies photos**, qui inclut donc l'extraction
par le modèle de vision, le retrieval, la passe raisonnée et l'assemblage de fiche. Le protocole est
reproductible
(`scripts/mesure_qualite_fiche.py`, sorties dans `reports/09_fiche_quality/mesure_fiche.{json,md}`) :
il s'applique au panel réel `data/photos_eval`, où chaque dossier est nommé d'après la vérité-terrain
(le vrai produit), et il n'utilise que la **photo seule** (sans le texte de précisions). Sur les 94
produits du panel, 93 ont été mesurés (1 écarté car sans photo) :

- **Identification** : **90,3 %** (la famille produite par l'IA et le titre du top-1 contiennent au
  moins 50 % des tokens-clés du vrai nom), pour un **rappel moyen de jetons de 78 %**.
- **Complétude de fiche** : **0,84** en moyenne, **0,83** en médiane.
- **Passe raisonnée** : déclenchée à **100 %** ; **catalog-miss** dans **28 %** des cas ; **question
  posée** dans **11 %** des cas. Répartition des niveaux de prix : **L1 = 42**, **L1.5 = 51**.
- **9 produits non identifiés**, TOUS expliqués honnêtement : une perception du modèle exact limitée
  (par exemple une RTX 4080 Super perçue comme 3080, une Xbox Series S, un casque Sennheiser Momentum
  perçu comme un Philips), un catalog-miss légitime (SSD, station d'accueil), ou un nom de dossier
  ambigu (artefact de mesure, pas une vraie erreur produit).

Cette mesure remplace les anecdotes par un chiffre défendable, conformément à la doctrine du projet
(mesurer sur de vraies sorties, jamais sur des comptes de lignes ou des pourcentages abstraits).

> Chiffres clés à retenir : « HNSW retrouve le bon produit avec un taux de 0,948 en
> 0,29 ms sur 3,16 millions de produits » (le chiffre qui impressionne), « bonne catégorie en
> premier résultat dans 94,2 % des cas », « seuil OOD à 0,600 donnant une précision de 0,95 et un
> rappel de 0,99 », et « identification bout-en-bout sur photos réelles à 90,3 % avec une complétude
> de fiche de 0,84 ». Captures suggérées : le tableau de comparaison des index, un écran montrant les
> candidats avec la question Akinator, et la fiche réordonnée avec le bandeau « Modèle à confirmer ».

---

## 6. Regard critique : forces et limites

**Points solides :**

- Le choix de l'index repose sur un banc d'essai mesuré (taux de bonnes réponses croisé avec la
  latence et la taille), pas sur une intuition. HNSW ressort comme le meilleur compromis, ce qui est
  conforme à l'état de l'art.
- La fusion RRF (constante k de 60) combine plusieurs points de vue de façon robuste, sans avoir à
  régler des poids fragiles ni à aligner des échelles de score.
- La détection OOD est calibrée du côté de la précision, ce qui permet de gérer honnêtement les
  produits inconnus et constitue notre principale défense contre les fausses identifications.
- Le mode Akinator par observation dirigée, guidé par l'entropie, désambigue intelligemment et de
  façon accessible au vendeur.
- La passe d'identification raisonnée sépare proprement la connaissance (le retrieval) du jugement
  (le modèle) : elle corrige le défaut où le premier voisin retrouvé était un accessoire, sans jamais
  permettre au modèle d'introduire un produit hors des 15 candidats réels. Le tout est best-effort :
  si elle échoue, on revient sans bruit au classement retrieval.
- Le texte vendeur, traité comme une autorité déterministe (et non comme une instruction au modèle),
  « sauve » l'identification quand le produit EST au catalogue, indépendamment des aléas du modèle.

**Limites assumées :**

- HNSW occupe 13,2 Go en mémoire vive. Au-delà d'environ 20 millions de produits, il faudrait passer
  à l'index compressé IVF_PQ en acceptant un taux de bonnes réponses moindre. Ce n'est pas nécessaire
  à notre échelle actuelle, mais il faut le savoir pour anticiper une montée en charge.
- Le seuil OOD a été calibré en comparant des fiches catalogue complètes entre elles, alors que la
  vraie requête d'un vendeur est plus courte et obtient des scores plus bas. Nous avons compensé par
  les trois niveaux de confiance, mais une recalibration sur de vraies requêtes vendeur serait plus
  juste.
- La recherche est aujourd'hui surtout textuelle : l'index servi en production porte sur le texte.
  La recherche image vers image directe, qui comparerait la photo du vendeur aux photos du catalogue,
  attend que les signatures d'image du catalogue soient produites.
- La fusion multi point de vue donne aujourd'hui son plein potentiel uniquement avec le texte. Elle
  gagnera nettement en qualité quand le point de vue image sera activé.
- Sur photo seule, la perception du MODÈLE exact reste limitée pour des produits sans marquage visible
  sur les images envoyées (par exemple un casque Sennheiser Momentum 3 dont le logo est sur l'étui) :
  le modèle peut alors choisir un sosie avec aplomb. On atténue par trois leviers : le texte vendeur
  autoritaire (la métadonnée fixe le produit), le flag « Modèle à confirmer », et le bouton « Ce n'est
  pas le bon produit ? Voir les autres résultats ». La métadonnée sauve quand le produit est au
  catalogue.
- Le modèle rapide par défaut (`qwen3.5-flash`) sous-déclenche le catalog-miss : il colle parfois à un
  sosie d'une autre génération (iPhone 14 perçu comme 13, RTX 4080 comme 3080). Un modèle jugé plus
  fort, branchable via `PHOTO_VLM_IDENTIFY_MODEL`, ferait mieux ; ce n'est pas câblé par défaut.
- Le garde-fou anti sous-évaluation du pricing est surtout défensif : le vrai travail de
  rehaussement est fait par le niveau L1.5 (l'ancre prix neuf estimée par l'IA).

---

## 7. Références

- Malkov & Yashunin, *Efficient and robust approximate nearest neighbor search using HNSW graphs* :
  https://arxiv.org/abs/1603.09320
- Pinecone, *Hierarchical Navigable Small Worlds (HNSW)* :
  https://www.pinecone.io/learn/series/faiss/hnsw/
- Cormack et al., *Reciprocal Rank Fusion* :
  https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
- FAISS, wiki officiel (types d'index, IVF_PQ) : https://github.com/facebookresearch/faiss/wiki

---

### En une phrase (pour la défense)

*Notre moteur retrouve le bon produit parmi 3,16 millions en 0,29 milliseconde avec un taux de
bonnes réponses de 0,948 (index HNSW, paramètre M de 32, choisi après comparaison mesurée contre la
recherche exacte et contre l'index compressé IVF_PQ), fusionne les points de vue par RRF (constante
de Cormack de 60), refuse d'inventer grâce à des garde-fous OOD calibrés du côté de la précision
(seuil de 0,600, précision de 0,95 et rappel de 0,99), et lève l'ambiguïté en demandant au vendeur
l'observation visuelle la plus discriminante (mode Akinator guidé par l'entropie). Le top-15 de cette
recherche alimente une passe d'identification raisonnée, où le moteur de recherche par similarité
apporte la connaissance et le modèle apporte le jugement, qui choisit le bon candidat parmi les 15,
le réordonne en tête (avec le texte vendeur faisant autorité), et atteint 90,3 % d'identification
bout-en-bout sur photos réelles.*
