# 06 - Estimation de prix transparente

> Proposer au vendeur un prix conseillé, accompagné d'une fourchette, d'un niveau de confiance et
> d'une explication lisible, plutôt qu'un simple nombre sorti d'une boîte noire que le vendeur ne
> pourrait pas comprendre.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre, en partant de zéro

Estimer le prix d'un objet d'occasion revient à répondre à une question concrète : « combien cela
vaut-il, compte tenu de son état et de son âge ? ». Il existe deux grandes façons de répondre.

La première est l'apprentissage automatique dit « opaque » : on entraîne un programme à prédire un
nombre, mais ce programme ne sait pas dire pourquoi il propose ce prix. C'est une boîte noire.

La seconde, celle que nous avons choisie, est une approche algorithmique transparente : le prix est
le résultat d'un calcul décomposé en étapes que l'on peut lire et vérifier. Le calcul part d'un
prix de référence, lui applique une décote liée à l'âge, puis un ajustement lié à l'état, et il
indique enfin un niveau de confiance dans le résultat.

Une des briques de ce calcul s'appuie sur des « comparables » (souvent abrégés en « comps »). L'idée
est la même qu'un agent immobilier qui estime une maison en regardant le prix de maisons voisines et
similaires : pour fixer un prix, on regarde le prix de produits proches. Cette logique de « regarder
les voisins les plus proches » porte un nom technique, le k plus proches voisins (en anglais k-NN,
pour k-Nearest Neighbors) : on prend les k produits les plus ressemblants et on s'inspire de leurs
prix.

### Pour le lecteur technique

Nous assumons une précision limitée (une erreur moyenne d'environ 62 %, mesurée par la métrique
décrite plus bas) et cette limite est structurelle, par honnêteté de conception. Nos prix de
référence sont des prix NEUFS, issus du catalogue Amazon, alors que nous cherchons à estimer de
l'OCCASION, et nous ne disposons d'aucune donnée de ventes réelles d'occasion. Dans ces conditions,
aucun modèle d'apprentissage automatique ne serait réellement précis. Nous préférons donc un prix
transparent, assorti d'une fourchette et d'un niveau de confiance, à une fausse précision affichée
par un modèle qui n'aurait pas de quoi apprendre.

---

## 2. État de l'art

La méthode des k plus proches voisins est reconnue pour estimer le prix de biens d'occasion : on
prend la médiane ou la moyenne du prix des k produits voisins. Dans le domaine de l'automobile
d'occasion, des études rapportent environ 85 % d'exactitude pour cette méthode, contre environ 71 %
pour une régression linéaire classique.

En pratique, on mesure la ressemblance entre produits par une distance (souvent la distance dite
euclidienne, c'est-à-dire la distance « à vol d'oiseau » entre deux points), et le nombre k de
voisins se règle en testant plusieurs valeurs sur des données de validation.

Pour évaluer la qualité d'un prix prédit, la métrique de référence est le MAPE (Mean Absolute
Percentage Error, soit l'erreur moyenne en pourcentage). Concrètement, pour chaque produit on
calcule l'écart entre le prix prédit et le prix réel, on l'exprime en pourcentage du prix réel, puis
on fait la moyenne de ces pourcentages. Un MAPE de 62 % signifie donc qu'en moyenne le prix prédit
s'écarte de 62 % du prix réel.

Une précision d'honnêteté sur ce 62 % lui-même : il est calculé en comparant notre estimation au
**prix NEUF du catalogue, en dollars**, et uniquement sur les produits qui **ont** un prix au
catalogue (une large part en est dépourvue). Ce chiffre n'est donc **pas** une vraie mesure de
justesse sur de l'occasion en euros : c'est un indicateur grossier, à lire comme une borne, pas comme
une performance. C'est précisément pourquoi nous ne présentons pas le pricing comme un modèle
d'apprentissage performant, mais comme une estimation transparente assortie d'une fourchette.

Enfin, une tendance forte du domaine consiste à afficher une incertitude et une explication plutôt
qu'un seul chiffre sec, car cela renforce la confiance de l'utilisateur dans l'outil.

---

## 3. Notre implémentation : précisément ce que nous avons fait

Le code se trouve dans le fichier `src/pricing/01_algorithmique.py`. La fonction principale
s'appelle `suggest_price(...)`. Elle applique une cascade à quatre niveaux de confiance : elle
essaie d'abord la méthode la plus fiable, et descend d'un cran à chaque fois que les informations
nécessaires manquent. Les quatre niveaux sont nommés L1 (le plus fiable) à L4 (mode de secours).

| Niveau | Nom de méthode | Conditions de déclenchement | Calcul appliqué |
|---|---|---|---|
| L1 | `catalog_meta` | un prix figure dans la fiche du produit identifié | prix catalogue, décote selon l'âge et la catégorie, ajustement selon l'état, puis conversion en euros |
| L2 | `knn_median` | pas de prix direct, mais au moins 3 prix de produits voisins valides (parmi les 10 voisins cherchés) | médiane des prix voisins, décote selon l'âge, ajustement selon l'état, puis conversion en euros |
| L3 | `category_median` | seule la catégorie du produit est connue | médiane de prix de la catégorie, ajustement selon l'état, puis conversion en euros |
| L4 | `fallback` | produit et catégorie tous deux inconnus | renvoie une fourchette vide et invite le vendeur à saisir un prix manuellement |

### Le détail exact des calculs

La décote liée à l'âge est calculée par la fonction `_depreciate(price, age_years, category)`. Elle
est LINÉAIRE et non exponentielle : on retire un certain pourcentage par année d'âge. La formule est
`prix × (1 - taux_de_la_catégorie × âge_en_années)`, et le multiplicateur ne descend jamais en
dessous de 0,10, c'est-à-dire que le prix conserve toujours au minimum 10 % de sa valeur de départ,
quel que soit l'âge. Les taux de décote annuels sont différenciés selon la catégorie :

- `Cell_Phones_and_Accessories` (téléphones et accessoires) : 20 % par an, car ce marché est très
  volatil et perd vite de la valeur ;
- `Electronics` (électronique) : 15 % par an, car ce type de matériel vieillit vite ;
- `Video_Games` (jeux vidéo) : 10 % par an, car la valeur de collection ralentit la perte de valeur ;
- `Tools_and_Home_Improvement` (outillage et bricolage) : 5 % par an, car ces objets vieillissent
  lentement.

Si la catégorie n'est pas reconnue, un taux par défaut de 10 % par an est appliqué.

L'ajustement selon l'état est réalisé par la fonction `_apply_condition`. Elle multiplie le prix par
un coefficient qui dépend de l'état déclaré de l'objet :

- neuf : coefficient 1,00 (le prix est conservé tel quel) ;
- très bon état : coefficient 0,75 ;
- bon état : coefficient 0,55 ;
- état correct, avec défauts : coefficient 0,35.

Lorsque l'état n'est pas précisé, c'est « bon état » (coefficient 0,55) qui s'applique par défaut.

La conversion en euros se fait avec un taux fixe `USD_TO_EUR = 0,92`. Ce choix s'explique ainsi : les
prix du catalogue sont exprimés en dollars américains (source Amazon), alors que l'interface affiche
des euros. Le taux retenu est une moyenne sur la période 2024-2026. Il peut être modifié sans
retoucher le code grâce à une variable d'environnement nommée `PRICE_USD_EUR_RATE`. Brancher un taux
de change en temps réel via une interface externe serait disproportionné pour un prix qui n'est
qu'indicatif et arrondi. Point important : la conversion en euros est appliquée APRÈS la décote et
l'ajustement d'état, jamais avant.

La fourchette de prix autour de la valeur conseillée n'est pas la même selon le niveau de confiance,
ce qui est cohérent : plus on est sûr, plus la fourchette est serrée.

- au niveau L1 : fourchette de plus ou moins 15 % (de 0,85 à 1,15 fois le prix) ;
- au niveau L2 : fourchette de plus ou moins 30 % (de 0,70 à 1,30 fois le prix) ;
- au niveau L3 : fourchette de plus ou moins 50 % (de 0,50 à 1,50 fois le prix).

Le niveau de confiance est aussi chiffré entre 0 et 1 (le `confidence_score`) :

- L1 : score fixé à 0,90 ;
- L2 : score compris entre 0,50 et 0,80, calculé à partir de la dispersion des prix voisins (plus les
  prix voisins se ressemblent, plus le score est élevé) ;
- L3 : score fixé à 0,30 ;
- L4 : score nul (0,0).

Une protection écarte les prix invalides : seuls les prix supérieurs ou égaux à 0,01 dollar sont pris
en compte, ce qui élimine les valeurs « 0,0 » parasites présentes dans certaines fiches Amazon.

Enfin, le système génère une explication écrite en langage courant, mentionnant les deux devises. Par
exemple, pour un produit catalogue : « Basé sur le prix catalogue neuf de 799,99 $ (≈ 736 €) :
dépréciation 15 %/an sur 3.0 an(s), ajustement « Bon état ». » Les codes techniques internes (comme
`bon_etat` écrit en minuscules avec un tiret bas) ne sont jamais montrés au vendeur : ils sont
traduits en libellés lisibles (« Bon état », « Neuf », etc.).

> Choix structurant : nous privilégions la transparence à une fausse précision. Le vendeur doit
> comprendre pourquoi tel prix lui est proposé. Un nombre opaque inspirerait moins confiance et
> serait plus difficile à défendre.

---

## 4. Résultats mesurés

- Démonstration en conditions réelles : pour un iPhone 13 en « bon état », la cascade aboutit à un
  prix conseillé d'environ 232 € au niveau L1, avec une explication mentionnant les deux devises.
- Erreur mesurée (MAPE) : au niveau L2 (médiane des voisins), l'erreur médiane est d'environ 62 % ;
  au niveau L3 (médiane de catégorie), elle est d'environ 56 %. Ces chiffres sont produits par le
  programme et écrits dans des fichiers de rapport, sous le dossier `reports/08_pricing/`.
- L'évaluation est menée sur 1000 produits tirés au hasard parmi les données de validation : pour
  chacun, on cherche ses 10 voisins, on suggère un prix de niveau L2, et on le compare au vrai prix.
- Tests automatisés : le fichier `test_pricing_cascade.py` vérifie le bon fonctionnement des quatre
  niveaux, la conversion de devise et les coefficients d'état.

> Point à expliquer honnêtement : une erreur de 62 % peut sembler élevée, mais elle est structurelle.
> Nos prix de référence sont des prix neufs, alors que nous estimons de l'occasion, et nous n'avons
> aucune donnée de ventes réelles d'occasion. C'est précisément pour cette raison que nous avons
> choisi un prix transparent, organisé par niveaux de confiance, plutôt qu'un modèle d'apprentissage
> opaque qui afficherait une précision trompeuse.

> Chiffres pour la présentation : « cascade à 4 niveaux de confiance », « décote différenciée par
> catégorie et coefficients d'état », « niveau L1 à 232 €, expliqué dans les deux devises », « erreur
> d'environ 62 % assumée (neuf contre occasion) ». Capture d'écran à montrer : la carte de prix de
> l'application (prix conseillé, fourchette, badge d'état et explication).

---

## 5. Critique : état de l'art comparé à notre solution

Les points solides :

- La logique de « comparables » par k plus proches voisins est alignée sur l'état de l'art de
  l'estimation d'occasion.
- La transparence, les niveaux de confiance et la fourchette permettent au vendeur de comprendre le
  prix et de l'ajuster lui-même. C'est bien plus défendable qu'une boîte noire.
- La décote différenciée par catégorie apporte une finesse métier réelle : un jeu vidéo ne perd pas
  sa valeur au même rythme qu'un téléphone.
- L'honnêteté sur l'erreur : nous nommons sa cause (prix neuf contre prix d'occasion) au lieu de la
  masquer.

Les limites assumées :

- L'erreur reste élevée faute de ventes d'occasion réelles : c'est la limite principale. Avec un
  historique de transactions Rakuten, on pourrait construire un véritable modèle calibré.
- Le taux de change est fixe (0,92) : suffisant pour un prix indicatif, mais ce n'est pas du temps
  réel.
- Aucun signal de demande ni de saisonnalité n'est pris en compte ; un modèle plus avancé les
  intégrerait.
- L'âge est supposé (2 ans par défaut dans l'évaluation) lorsqu'il n'est pas fourni, ce qui reste une
  approximation.

---

## 6. Références

- ResearchGate, « Used Car Price Prediction using KNN-based model » :
  https://www.researchgate.net/publication/350094568_Used_Car_Price_Prediction_using_K-Nearest_Neighbor_Based_Model
- Hands-On Machine Learning with R, chapitre 8 « K-Nearest Neighbors » :
  https://bradleyboehmke.github.io/HOML/knn.html
- MDPI, « Spatially explicit KNN for house price predictions » :
  https://www.mdpi.com/2220-9964/15/1/46
- Wikipedia, « Mean absolute percentage error (MAPE) » :
  https://en.wikipedia.org/wiki/Mean_absolute_percentage_error

---

### En une phrase, pour la défense

« Nous proposons un prix au moyen d'une cascade transparente à quatre niveaux de confiance : le prix
du catalogue si on l'a, sinon la médiane des produits voisins, sinon la médiane de la catégorie. Ce
prix est ajusté par une décote propre à chaque catégorie et par un coefficient lié à l'état, converti
en euros, puis expliqué au vendeur. Nous assumons une erreur élevée, car nos prix de référence sont
neufs et nous n'avons pas de ventes d'occasion : d'où le choix de la transparence plutôt que d'une
fausse précision. »
