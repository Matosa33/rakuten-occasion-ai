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

Précision importante : à un seul endroit de la cascade (le niveau L1.5), le
prix de référence DE DÉPART peut être une estimation produite par une IA, lorsqu'aucun prix catalogue
n'est disponible. Cela ne contredit pas le principe de transparence : l'IA ne fournit que le prix
NEUF de référence ; la décote d'âge, l'ajustement d'état et la conversion en euros restent un calcul
déterministe, lisible et identique à celui appliqué à un prix catalogue. Il n'y a donc toujours aucune
« boîte noire » qui sortirait directement un prix d'occasion.

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
s'appelle `suggest_price(...)`. Elle applique une cascade de niveaux de confiance : elle essaie
d'abord la méthode la plus fiable, et descend d'un cran à chaque fois que les informations
nécessaires manquent. À l'origine la cascade comptait quatre niveaux nommés L1 (le plus fiable) à
L4 (mode de secours). Un niveau supplémentaire, L1.5, a ensuite été intercalé entre L1 et L2, ce qui
porte la cascade à cinq niveaux : **L1, L1.5, L2, L3, L4**.

| Niveau | Nom de méthode | Conditions de déclenchement | Calcul appliqué |
|---|---|---|---|
| L1 | `catalog_meta` | un prix figure dans la fiche du produit identifié (et il n'est ni incohérent avec l'ancre IA, ni aberrant par rapport aux voisins) | prix catalogue, décote selon l'âge et la catégorie, ajustement selon l'état, puis conversion en euros |
| L1.5 | `llm_anchor` | pas de prix catalogue exploitable, mais l'IA a estimé un prix NEUF de référence (passe d'identification raisonnée) | ancre IA, décote selon l'âge et la catégorie, ajustement selon l'état, puis conversion en euros |
| L2 | `knn_median` | ni catalogue ni ancre IA, mais au moins 3 prix de produits voisins valides (parmi les 10 voisins cherchés) | médiane des prix voisins, décote selon l'âge, ajustement selon l'état, conversion en euros, puis garde-fou anti sous-évaluation |
| L3 | `category_median` | seule la catégorie du produit est connue | médiane de prix de la catégorie, ajustement selon l'état, conversion en euros, puis garde-fou anti sous-évaluation |
| L4 | `fallback` | produit et catégorie tous deux inconnus | renvoie une fourchette vide et invite le vendeur à saisir un prix manuellement |

### Pourquoi un niveau L1.5 a été ajouté

Le besoin est né d'un constat concret sur de vraies photos. Quand un produit n'a pas de prix direct
dans sa fiche catalogue, l'ancien système descendait directement sur la médiane des produits voisins
(L2). Or cette médiane est souvent POLLUÉE : parmi les voisins remontés par la recherche par
similarité se glissent des accessoires (coques, câbles, chargeurs), des bundles ou des lots, dont le
prix n'a rien à voir avec celui du produit lui-même. Résultat observé : une médiane qui donnait
environ 6 € pour une montre dont le prix neuf tournait autour de 150 €. Le prix conseillé devenait
absurde et décrédibilisait l'outil.

La réponse retenue est l'**ancre IA**. Lors de l'identification raisonnée (décrite plus bas), le
modèle d'IA estime un prix NEUF de référence pour le produit observé, en s'appuyant sur les prix
NEUFS et propres des vrais produits candidats (accessoires exclus). Ce prix neuf estimé sert d'ancre.
Point essentiel et défendable : **seule l'ancre est une estimation par IA ; la décote, elle, reste
100 % déterministe et transparente**, exactement comme aux autres niveaux. On applique à l'ancre la
même dépréciation par âge et le même coefficient d'état que pour un prix catalogue. La phrase « pas
de pricing par boîte noire » reste donc vraie : l'IA ne sort pas un prix d'occasion opaque, elle
fournit un point de départ (le prix neuf de référence) que notre calcul lisible transforme ensuite.

L1.5 est volontairement placé AVANT les médianes de voisins (L2/L3) parce que ces médianes sont
justement la source du problème. Dans le même mouvement, L2 et L3 ont été RÉTROGRADÉES : elles ne
servent plus qu'en l'absence d'ancre IA exploitable.

### L'identification raisonnée qui alimente l'ancre

L'ancre prix neuf ne tombe pas du ciel : elle provient d'un module dédié,
`src/vlm/reasoned_identification.py`, dont la fonction principale est `reason_identify(...)`. Le
principe tient en une phrase : **le moteur de recherche par similarité apporte la connaissance, le
modèle d'IA apporte le jugement**. Concrètement, le moteur de recherche remonte les 15 fiches
catalogue réelles les plus proches ; on envoie à l'IA, en un seul appel, la ou les photos du vendeur
(1 à 2 images) accompagnées des 15 fiches RÉSUMÉES EN TEXTE (pas les 15 images du catalogue, pour
économiser des jetons), des attributs déjà observés et du texte saisi par le vendeur. L'IA doit
alors juger :
quelle est la famille de produit, quel candidat correspond vraiment, et quel est le prix neuf de
référence estimé (le champ `reference_new_price_usd`). Le modèle utilisé est paramétrable par la
variable d'environnement `PHOTO_VLM_IDENTIFY_MODEL` ; à défaut, c'est le modèle d'extraction photo du
projet qui est réutilisé. L'appel est rendu reproductible (température 0, graine fixée, raisonnement
interne désactivé).

Trois garde-fous protègent ce jugement contre l'invention, dans `_parse(...)` :

- si l'IA désigne un candidat qui ne fait PAS partie des 15 fiches réelles (un identifiant
  « halluciné »), on retombe sur le candidat numéro 1 du moteur de recherche ET on remet la confiance
  de famille à zéro, parce que l'IA n'a pas réellement endossé ce candidat ;
- une facette dont la source citée est invalide (ni « observé », ni « par analogie », ni un index de
  fiche réelle) est purement et simplement jetée : on n'affirme jamais une caractéristique non
  sourcée ;
- l'ancre prix, en revanche, est CONSERVÉE même sans preuve formelle (sans index d'évidence), parce
  que c'est une ESTIMATION explicitement étiquetée « prix neuf estimé par IA », pas un fait catalogue.
  Mieux vaut une estimation honnêtement étiquetée que la médiane polluée à 6 €.

Ce module est **best-effort et non bloquant** : absence de clé API, modèle indisponible,
réponse illisible ou exception quelconque renvoient simplement `None`. Le pipeline garde alors le
classement du moteur de recherche et la cascade de pricing telle quelle. Il n'y a jamais de plantage
ni de fiche vide. Enfin, le candidat jugé correct est RÉORDONNÉ en tête des candidats, de sorte que
la fiche, le prix et la validation portent sur le BON produit : auparavant, le candidat numéro 1 du
moteur de recherche pouvait être un accessoire (par exemple une coque d'iPhone affichée à la place de
l'iPhone).

### Le texte vendeur fait foi

Un mécanisme déterministe complète l'IA, dans `src/api/main.py` (fonction
`_seller_text_best_match`). Si le texte saisi par le vendeur (les « précisions ») nomme un produit
qui figure dans les candidats, ce candidat est retenu de façon déterministe, indépendamment du
modèle d'IA rapide qui ignore parfois cette consigne. La correspondance exige au moins deux jetons
discriminants et une couverture d'au moins 50 %, en CONSERVANT les numéros de modèle même à un seul
chiffre (« Momentum 3 » ne doit pas être confondu avec « 2.0 »). En cas d'égalité entre plusieurs
candidats, on retient celui dont le prix est le plus REPRÉSENTATIF, c'est-à-dire le plus proche de la
médiane, ce qui évite de bâtir la fiche sur une donnée corrompue (par exemple un même « Momentum 3 »
listé par erreur à 9755 $). Sur un texte vide, ce mécanisme ne fait rien du tout : aucune régression
possible. Cette métadonnée « sauve » le système quand le produit EST présent au catalogue mais que la
photo seule ne suffit pas à le distinguer d'un sosie.

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
- état correct, avec défauts : coefficient 0,35 ;
- pour pièces / HS : coefficient 0,15.

Lorsque l'état n'est pas précisé, c'est « bon état » (coefficient 0,55) qui s'applique par défaut.
L'état « pour pièces / HS » correspond à un objet hors service ou cédé pour récupération de pièces :
il ne lui reste qu'une valeur résiduelle, d'où le coefficient très bas de 0,15. Cet état est
proposé au vendeur dans l'interface (libellé « Pour pièces / HS »).

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
- au niveau L1.5 : fourchette de plus ou moins 20 % (de 0,80 à 1,20 fois le prix) ;
- au niveau L2 : fourchette de plus ou moins 30 % (de 0,70 à 1,30 fois le prix) ;
- au niveau L3 : fourchette de plus ou moins 50 % (de 0,50 à 1,50 fois le prix).

Le niveau de confiance est aussi chiffré entre 0 et 1 (le `confidence_score`) :

- L1 : score fixé à 0,90 ;
- L1.5 : score compris entre 0,55 et 0,85, calculé à partir de la confiance que l'IA accorde à son
  ancre par la formule `0,60 + 0,25 × confiance_ancre`, puis borné dans cet intervalle. L1.5 se place
  ainsi juste sous L1 mais au-dessus de L2, ce qui reflète bien sa position dans la cascade ;
- L2 : score compris entre 0,50 et 0,80, calculé à partir de la dispersion des prix voisins (plus les
  prix voisins se ressemblent, plus le score est élevé) ;
- L3 : score fixé à 0,30 ;
- L4 : score nul (0,0).

Une protection écarte les prix invalides : seuls les prix supérieurs ou égaux à 0,01 dollar sont pris
en compte, ce qui élimine les valeurs « 0,0 » parasites présentes dans certaines fiches Amazon.

### Les trois garde-fous métier

Au-delà de la cascade, trois protections ont été ajoutées, qui ont toutes une motivation observée
sur de vraies photos. Elles servent à empêcher des prix manifestement faux de remonter à l'utilisateur.

1. **Anti sous-évaluation** (fonction `_floor_against_underpricing`, constante
   `UNDERPRICING_FLOOR_RATIO = 0,25`). Une médiane de voisins polluée par des accessoires ou des
   bundles peut s'effondrer (le fameux 6 € pour une montre à 150 €). Pour s'en prémunir, on calcule un
   PLANCHER : on prend le prix neuf de référence attendu (l'ancre IA, ou le prix catalogue), on lui
   applique exactement la même décote d'âge et d'état, on le convertit en euros, puis on en garde
   25 %. Si la suggestion L2 ou L3 tombe sous ce plancher, on la relève à ce plancher et on l'explique
   au vendeur (« prix relevé : la médiane des voisins était incohérente avec le prix neuf attendu »).
   Ce garde-fou est surtout DÉFENSIF : c'est le niveau L1.5 (l'ancre IA) qui fait le vrai travail de
   fond ; le plancher n'agit qu'en filet de sécurité, et seulement si un ordre de grandeur attendu est
   disponible.

2. **Cohérence du niveau L1** (constante `L1_ANCHOR_MIN_RATIO = 0,2`). Le candidat numéro 1 du
   moteur de recherche peut être un accessoire mal apparié, par exemple une coque à 43 $ pour un
   iPhone dont le prix neuf estimé est de l'ordre de 598 $. Si une ancre IA existe et que le prix catalogue du
   candidat numéro 1 est DRASTIQUEMENT en dessous (inférieur à 0,2 fois l'ancre), on considère ce prix
   catalogue comme pollué : on l'ignore et on bascule sur L1.5. Cela évite d'afficher « iPhone à 15 € »
   parce que le candidat numéro 1 était une coque. Le ratio est volontairement BAS (0,2) car un prix
   catalogue est un FAIT : un reconditionné, une promotion ou une génération antérieure peuvent
   légitimement coûter moins cher que l'estimation de l'IA. On n'écarte donc le prix catalogue que
   s'il est vraiment aberrant.

3. **Prix catalogue aberrant vers le haut** (constante `CATALOG_OUTLIER_FACTOR = 4,0`). À l'inverse, un
   prix catalogue très AU-DESSUS de la médiane des voisins trahit une donnée corrompue (par exemple
   9755 $ pour un casque, à cause d'une faute de saisie ou d'un bundle). Si le prix catalogue dépasse 4
   fois la médiane des voisins, et à condition d'avoir au moins 3 voisins valides pour que cette
   médiane soit fiable, on ignore le prix catalogue au profit des voisins. La condition « au moins 3
   voisins » évite de rejeter un prix sur la foi d'une médiane calculée sur trop peu de données.

Ces deux derniers garde-fous décident, en amont du calcul L1, si le prix catalogue est digne de
confiance : s'il ne l'est pas, la cascade saute L1 et continue vers L1.5 (ou plus bas).

Enfin, le système génère une explication écrite en langage courant, mentionnant les deux devises. Par
exemple, pour un produit catalogue (niveau L1) : « Basé sur le prix catalogue neuf de 799,99 $
(≈ 736 €) : dépréciation 15 %/an sur 3.0 an(s), ajustement « Bon état ». » Pour le niveau L1.5,
l'explication est honnêtement étiquetée comme une estimation : « Prix neuf estimé par IA : <montant> $
(≈ <montant> €), dépréciation … ». Les codes techniques internes (comme `bon_etat` écrit en minuscules
avec un tiret bas) ne sont jamais montrés au vendeur : ils sont traduits en libellés lisibles (« Bon
état », « Neuf », « Pour pièces / HS », etc.).

Côté interface (`frontend/src`), chaque niveau de la cascade reçoit un libellé clair affiché au
vendeur : « Confiance élevée (prix catalogue) » pour L1, « Prix neuf estimé par IA » pour L1.5,
« Confiance moyenne (produits similaires) » pour L2, « Estimation par catégorie » pour L3, et « Saisie
manuelle conseillée » pour L4. Point important sur le niveau L4 : le front n'affiche PLUS « 0,00 € »
comme s'il s'agissait d'une suggestion, mais le message honnête « Prix à fixer (saisie manuelle) »,
pour ne pas laisser croire que l'objet vaut zéro euro.

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
- L'évaluation MAPE est menée sur 1000 produits tirés au hasard parmi les données de validation : pour
  chacun, on cherche ses 10 voisins, on suggère un prix de niveau L2, et on le compare au vrai prix.
- Tests automatisés : le fichier `test_pricing_cascade.py` vérifie le bon fonctionnement des niveaux
  de la cascade, la conversion de devise et les coefficients d'état.

### Mesure de qualité de fiche sur le panel réel

Pour mesurer l'effet réel de ces mécanismes plutôt que de raconter des anecdotes, un
protocole reproductible (`scripts/mesure_qualite_fiche.py`, sorties dans
`reports/09_fiche_quality/mesure_fiche.{json,md}`) a été exécuté sur le panel réel
`data/photos_eval`, qui contient **94 produits** dont les noms de dossiers servent de vérité-terrain.
La mesure se fait sur la PHOTO SEULE, sans les précisions texte du vendeur, donc dans le cas le plus
difficile. Les résultats mesurés :

- **Identification** : **90,3 %** (le critère retenu : au moins 50 % des jetons clés du nom de produit
  retrouvés dans la famille jugée par l'IA et le titre du candidat numéro 1). Le rappel moyen des
  jetons est d'environ **78 %**.
- **Complétude de fiche** : **0,84 en moyenne**, **0,83 en médiane**.
- **Passe raisonnée** déclenchée dans **100 %** des cas ; **catalog-miss** (produit absent du
  catalogue) dans **28 %** des cas ; **question discriminante posée** dans **11 %** des cas.
- **Répartition des niveaux de prix** sur ce panel : **L1 = 42** produits, **L1.5 = 51** produits. La
  forte part de L1.5 confirme que beaucoup de produits réels n'ont pas de prix catalogue direct
  exploitable et que l'ancre IA prend alors utilement le relais.
- **9 produits non identifiés**, TOUS expliqués : perception du modèle exact limitée par l'IA
  (par exemple une RTX 4080 Super perçue comme une 3080, une Xbox Series S, un casque Sennheiser
  Momentum perçu comme du Philips), catalog-miss (un SSD, une station d'accueil), ou un nom de dossier
  ambigu (artefact de mesure plutôt qu'une vraie erreur).

Cette mesure remplace les anecdotes par un chiffre défendable, conformément à notre doctrine de
mesurer sur de VRAIES sorties.

> Point à expliquer honnêtement : une erreur de 62 % peut sembler élevée, mais elle est structurelle.
> Nos prix de référence sont des prix neufs, alors que nous estimons de l'occasion, et nous n'avons
> aucune donnée de ventes réelles d'occasion. C'est précisément pour cette raison que nous avons
> choisi un prix transparent, organisé par niveaux de confiance, plutôt qu'un modèle d'apprentissage
> opaque qui afficherait une précision trompeuse.

> Chiffres pour la présentation : « cascade à 5 niveaux de confiance (L1, L1.5, L2, L3, L4) », « ancre
> prix neuf estimée par IA au niveau L1.5, mais décote 100 % déterministe », « trois garde-fous métier
> (anti sous-évaluation, cohérence L1, prix catalogue aberrant) », « décote différenciée par catégorie
> et coefficients d'état (dont « pour pièces / HS » à 0,15) », « niveau L1 à 232 €, expliqué dans les
> deux devises », « erreur MAPE d'environ 62 % assumée (neuf contre occasion) », « identification
> mesurée à 90,3 % sur 94 produits réels, complétude de fiche 0,84 ». Capture d'écran à montrer : la
> carte de prix de l'application (prix conseillé, fourchette, badge d'état et explication, libellé du
> niveau).

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
- L'ancre IA (L1.5) résout un problème concret et chiffré : les médianes de voisins polluées donnaient
  des prix absurdes (6 € pour une montre à 150 €). En faisant juger l'IA tout en gardant la décote
  déterministe, on combine la connaissance du moteur de recherche par similarité et le bon sens du modèle SANS introduire de
  boîte noire de prix.
- Les trois garde-fous attrapent les cas pathologiques (accessoire mal apparié, donnée corrompue) qui,
  sinon, remonteraient un prix manifestement faux à l'utilisateur.

Les limites assumées :

- L'erreur reste élevée faute de ventes d'occasion réelles : c'est la limite principale. Avec un
  historique de transactions Rakuten, on pourrait construire un véritable modèle calibré.
- Sur photo seule, la perception du MODÈLE exact par l'IA est limitée pour des produits sans marquage
  visible (par exemple un casque Sennheiser Momentum 3 dont le logo est sur l'étui). Le modèle peut
  alors choisir un sosie avec aplomb. On l'atténue par trois leviers : le texte vendeur qui fait foi
  (la métadonnée fixe le produit quand il est au catalogue), le drapeau « Modèle à confirmer » affiché
  au vendeur, et le bouton « Ce n'est pas le bon produit ? Voir les autres résultats ». Le modèle
  d'IA rapide utilisé par défaut a aussi tendance à SOUS-déclencher le signalement d'absence du
  catalogue (il colle à un sosie d'une autre génération, par exemple iPhone 14 vu comme 13, RTX 4080
  vue comme 3080) ; un modèle jugé plus fort, branchable via `PHOTO_VLM_IDENTIFY_MODEL`, ferait mieux
  mais n'est pas câblé par défaut.
- Le garde-fou anti sous-évaluation est avant tout DÉFENSIF : c'est le niveau L1.5 (l'ancre IA) qui
  fait le vrai travail de fond ; le plancher n'est qu'un filet de sécurité.
- Le taux de change est fixe (0,92) : suffisant pour un prix indicatif, mais ce n'est pas du temps
  réel.
- Aucun signal de demande ni de saisonnalité n'est pris en compte ; un modèle plus avancé les
  intégrerait.
- L'âge est supposé (2 ans par défaut) lorsqu'il n'est pas fourni, ce qui reste une approximation
  signalée au vendeur ; l'interface propose un champ « Année d'achat » optionnel pour l'affiner.

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

« Nous proposons un prix au moyen d'une cascade transparente à cinq niveaux de confiance : le prix du
catalogue si on l'a (L1), sinon un prix neuf de référence estimé par IA puis décoté de façon
déterministe (L1.5), sinon la médiane des produits voisins (L2), sinon la médiane de la catégorie
(L3), sinon une saisie manuelle (L4). Ce prix est ajusté par une décote propre à chaque catégorie et
par un coefficient lié à l'état (jusqu'à « pour pièces / HS »), converti en euros, protégé par trois
garde-fous métier, puis expliqué au vendeur. Seule l'ancre IA est une estimation ; tout le reste du
calcul reste lisible et vérifiable. Nous assumons une erreur élevée, car nos prix de référence sont
neufs et nous n'avons pas de ventes d'occasion : d'où le choix de la transparence plutôt que d'une
fausse précision. »
