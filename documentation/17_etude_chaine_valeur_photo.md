# 17. Étude scientifique : que vaut vraiment une photo pour rédiger une annonce ?

> L'idée tient en une phrase : on a voulu prouver, chiffres à l'appui et sans tricher, que partir
> d'une photo produit une meilleure fiche d'annonce que partir du texte du vendeur, que plusieurs
> photos valent mieux qu'une, et que les informations saisies à la main par le vendeur n'ajoutent
> presque rien une fois les photos disponibles. C'est le cœur de la promesse du produit, donc cela
> méritait une vraie démonstration, pas une intuition.

---

## 1. La question, posée simplement

Le produit aide un particulier à vendre un objet d'occasion à partir de ses photos. La promesse
implicite est forte : « donnez-moi une photo, je m'occupe du reste » (trouver la catégorie, le bon
modèle, remplir les caractéristiques, écrire le titre). Avant de présenter cela comme un acquis, il
fallait répondre honnêtement à trois questions.

1. **Une photo vaut-elle mieux que le texte que le vendeur tape lui-même ?** Si un simple titre
   saisi suffit, la photo n'apporte rien et la promesse s'effondre.
2. **Plusieurs photos valent-elles mieux qu'une seule ?** Montrer le dos, l'étiquette, l'écran,
   cela aide-t-il vraiment, ou est-ce du confort inutile ?
3. **Les informations saisies par le vendeur (la « métadonnée vendeur ») améliorent-elles encore
   le résultat une fois les photos là ?** Autrement dit, faut-il continuer à demander au vendeur
   de remplir des champs, ou les photos rendent-elles cette saisie superflue ?

Répondre à ces questions, c'est mesurer la **valeur de chaque maillon** de la chaîne qui va de
l'entrée du vendeur jusqu'à la fiche finale. D'où le titre de ce document.

---

## 2. Comment on lit une photo, et ce que veut dire « fiche »

Pour transformer une photo en texte exploitable, on utilise un **modèle vision-langage**, c'est à
dire un programme d'intelligence artificielle capable de regarder une image et d'en écrire une
description. On lui demande de produire deux choses à partir des photos : un **titre probable** du
produit (par exemple « EVGA 1000 GQ 1000W 80+ Gold Power Supply ») et une liste d'**attributs
observés** (marque, couleur, capacité, modèle, texte visible sur l'objet). Cette étape s'appelle
l'**extraction**.

Ce titre extrait sert ensuite à retrouver le vrai produit dans un catalogue de référence (une grande
base de produits réels), puis à assembler la **fiche** : la catégorie, l'état, la marque, et les
caractéristiques attendues pour ce type d'objet. La « fiche » est donc le résultat final présenté au
vendeur, prêt à publier.

---

## 3. Le protocole, conçu pour ne pas se mentir

### 3.1 Les six situations comparées

Pour isoler l'effet de chaque maillon, on a évalué le même ensemble de produits dans six situations
d'entrée différentes, en ne changeant qu'une chose à la fois.

| Code | Ce que reçoit le système en entrée |
|---|---|
| text-only | Le **texte du vendeur seul** (un court intitulé), aucune photo |
| text-fr-en | Le même texte vendeur, mais **traduit** du français vers l'anglais |
| one-photo | **Une seule photo** (aucun texte vendeur) |
| multi-photo | **Plusieurs photos** du même objet (différentes vues) |
| multi-photo-meta | Plusieurs photos **plus la métadonnée saisie par le vendeur** |
| multi-photo-meta-fr-en | Comme multi-photo-meta, mais avec la métadonnée **traduite** en anglais |

La progression text-only, one-photo, multi-photo, multi-photo-meta va du plus pauvre (du texte seul) au plus riche (photos plus
métadonnée). Comparer deux situations voisines mesure l'apport du maillon qu'on vient d'ajouter. La
traduction est testée à part (text-only contre text-fr-en, multi-photo-meta contre multi-photo-meta-fr-en) parce que le catalogue de référence est
en anglais : on voulait savoir si traduire l'entrée française aide ou non.

### 3.2 Les mesures de qualité de la fiche

Une fiche peut être bonne sur un axe et mauvaise sur un autre. On a donc mesuré plusieurs choses
complémentaires, toutes sur une échelle de 0 à 1.

- **La complétude (en anglais « completeness »)** : la part des caractéristiques attendues pour ce
  type de produit qui sont effectivement remplies dans la fiche. Une fiche très complète renseigne
  la marque, le modèle, la capacité, la couleur, etc. C'est notre **mesure principale**, car une
  annonce vide se vend mal.
- **L'identification (en anglais « entity_match »)** : a-t-on retrouvé le **bon produit** dans le
  catalogue ? Concrètement, le produit retrouvé partage-t-il l'essentiel de son nom avec le vrai
  produit.
- **L'exactitude de catégorie** : a-t-on rangé l'objet dans la bonne grande famille (électronique,
  téléphonie, jeux vidéo, outillage) et dans la bonne sous-catégorie fine.

### 3.3 Les deux garde-fous contre l'auto-illusion

Mesurer mal donne des conclusions fausses qui ont l'air vraies. Deux précautions ont été prises.

**Premier garde-fou : la stratification anti-fuite.** En préparant les données, on a remarqué que
sur une partie des produits, le texte saisi par le vendeur contenait déjà le nom exact du vrai
produit. Si on mesurait l'apport de la métadonnée sur ces produits là, on mesurerait en réalité un
**raccourci circulaire** : la métadonnée « aiderait » seulement parce qu'elle contient déjà la
réponse. Ce phénomène s'appelle une **fuite d'annotation**. Sur les 93 produits, 44 étaient dans ce
cas et 49 en étaient exempts. On a donc systématiquement refait les mesures sensibles sur le
sous-ensemble **propre** des 49 produits sans recouvrement, en plus de l'ensemble complet. Ce
découpage en sous-groupes s'appelle une **stratification**.

**Second garde-fou : des tests statistiques appariés.** On n'a jamais conclu « A est meilleur que B »
sur la seule comparaison de deux moyennes. On a comparé A et B **produit par produit** (chaque
produit est son propre point de comparaison, ce qu'on appelle un test apparié), ce qui élimine
l'effet « certains produits sont juste plus faciles que d'autres ». Trois outils ont servi.
- Le **test de Wilcoxon apparié** : dit si une différence de score entre deux situations est réelle
  ou due au hasard. On le résume par une **valeur p** : en dessous de 0,05, la différence est jugée
  réelle (statistiquement significative).
- Le **test de tendance de Page** : dit si une mesure **augmente régulièrement** le long d'une
  progression ordonnée (ici de text-only vers multi-photo-meta).
- Le **test d'équivalence TOST** (de l'anglais « Two One-Sided Tests ») : c'est l'inverse d'un test
  classique. Au lieu de chercher une différence, il cherche à **prouver une absence d'effet**, en
  démontrant que l'écart reste sous un seuil jugé négligeable d'avance (ici 0,05, appelé le SESOI,
  pour « plus petit effet d'intérêt »). C'est important : ne pas trouver de différence n'est pas la
  même chose que prouver qu'il n'y en a pas, et seul le TOST permet la seconde affirmation.

Enfin, comme l'API du modèle vision-langage n'est pas parfaitement reproductible (elle peut répondre
légèrement différemment au même appel), chaque extraction de photo a été **mise en cache** : toutes
les situations qui partagent les mêmes photos partagent la même extraction, et on peut rejouer les
calculs sans rappeler l'API. Cela garantit qu'une différence observée vient bien du maillon testé,
pas d'un tirage différent du modèle.

L'étude a porté sur **93 produits réels** annotés à la main (photos authentiques, vrai nom, vraie
catégorie, vrai prix, état, et une note de qualité de la métadonnée vendeur de 0 à 5).

---

## 4. Les résultats mesurés

### 4.1 Vue d'ensemble (93 produits)

| Situation | Exactitude catégorie | Identification | Complétude |
|---|---|---|---|
| text-only (texte seul) | 0,871 | 0,720 | 0,505 |
| text-fr-en (texte traduit) | 0,850 | 0,742 | 0,509 |
| one-photo (1 photo) | 0,817 | 0,656 | 0,641 |
| multi-photo (N photos) | 0,903 | 0,785 | 0,699 |
| multi-photo-meta (N photos + métadonnée) | 0,893 | 0,850 | 0,694 |
| multi-photo-meta-fr-en (+ traduction) | 0,850 | 0,774 | 0,692 |

### 4.2 La photo est le maillon décisif (prouvé de trois façons)

- **La complétude augmente régulièrement avec la richesse photo.** De text-only à one-photo à multi-photo, elle passe de
  0,505 à 0,641 à 0,699. Le test de tendance de Page confirme cette montée avec une valeur p de
  l'ordre de 0,000000000000000000001 (très loin sous 0,05) : la progression n'est pas un hasard.
- **La photo bat le texte seul là où ça compte le plus.** Sur les produits dont la métadonnée
  vendeur est pauvre (note de qualité inférieure ou égale à 2, soit 41 produits), passer du texte
  seul (text-only) à une photo (one-photo) fait gagner **0,145 de complétude** (intervalle de confiance à 95 % :
  de 0,107 à 0,183), avec une valeur p inférieure à 0,0001. Autrement dit, quand le vendeur décrit
  mal son objet, la photo prend le relais et remplit la fiche à sa place. C'est exactement la
  justification de l'approche « la photo d'abord ».
- **Plusieurs photos valent mieux qu'une.** De one-photo à multi-photo, la complétude gagne en moyenne 0,058
  (intervalle de 0,036 à 0,081, valeur p inférieure à 0,0001), et l'identification du bon produit
  gagne 0,129 (intervalle de 0,054 à 0,208, valeur p de 0,003). Montrer plusieurs vues aide
  réellement à reconnaître le produit et à le décrire.

### 4.3 La métadonnée vendeur n'apporte rien (démontré, pas supposé)

C'est le résultat le plus contre-intuitif, et celui où les garde-fous ont été décisifs.

- **Sur la complétude**, ajouter la métadonnée vendeur aux photos (multi-photo vers multi-photo-meta) ne change rien : la
  valeur p est de 0,20 sur l'ensemble, et de 0,074 sur le sous-ensemble propre. Surtout, le test
  d'équivalence TOST conclut formellement à l'**équivalence** (valeur p de l'ordre de 0,0000000026) :
  on a donc **prouvé l'absence d'effet**, on ne s'est pas contenté de ne pas en trouver.
- **Sur l'identification**, un piège a failli nous tromper. Sur l'ensemble complet, la métadonnée
  semblait aider (gain de 0,065, valeur p de 0,034, ce qui passerait pour significatif). Mais sur le
  sous-ensemble **propre** des 49 produits sans fuite d'annotation, ce gain **disparaît
  complètement** (valeur p de 0,56). La conclusion honnête est donc : le gain apparent était un
  **artefact de circularité** (la métadonnée contenait déjà la réponse sur certains produits), et
  non un vrai apport. Sans la stratification, on aurait affirmé à tort « la métadonnée aide à
  identifier ». C'est précisément le genre d'erreur que le protocole était conçu pour éviter.

Conséquence produit : on peut **alléger la saisie demandée au vendeur** sans dégrader la fiche, ce
qui réduit la friction et le taux d'abandon.

### 4.4 Traduire l'entrée n'aide pas

Traduire le texte ou la métadonnée du français vers l'anglais (text-only contre text-fr-en, multi-photo-meta contre multi-photo-meta-fr-en) n'a
**aucun effet mesurable** sur la complétude (valeur p de 0,57 pour multi-photo-meta contre multi-photo-meta-fr-en). Le moteur de
recherche du catalogue tolère donc le français en entrée, et on s'épargne une étape de traduction.

---

## 5. Quel modèle lit le mieux les photos ?

La qualité de l'extraction dépend du modèle vision-langage utilisé. On a donc comparé quatre modèles
disponibles via une passerelle d'API (tous bon marché et capables de « voir » des images) sur la
situation à plusieurs photos, avec les mêmes mesures dures que ci-dessus.

| Modèle | Identification | Complétude | Latence moyenne | Prix (par million de mots en entrée) |
|---|---|---|---|---|
| Gemma 4 31B | 0,806 | 0,701 | 6,7 s | 0,12 $ |
| MiMo V2.5 | 0,806 | 0,724 | 2,3 s | 0,105 $ |
| Gemini 2.5 Flash Lite | 0,839 | 0,673 | 2,1 s | 0,10 $ |
| **Qwen 3.5 Flash** | 0,817 | **0,745** | 4,1 s | **0,065 $** |

Lecture honnête, appuyée sur des tests appariés.
- **Pour l'identification, aucun modèle n'est réellement meilleur** : l'avance apparente de Gemini
  (0,839) n'est pas significative (test de McNemar, qui compare deux classements binaires produit
  par produit, valeurs p de 0,58 à 1,00). Les quatre identifient aussi bien le produit.
- **Pour la complétude, Qwen gagne pour de vrai** : il remplit plus complètement la fiche que Gemini
  (valeur p inférieure à 0,0001) et que Gemma (valeur p de 0,0002), et il est en prime le **moins
  cher** des quatre.

On a donc retenu **Qwen 3.5 Flash** comme modèle d'extraction par défaut. Sa latence (4,1 secondes)
est un peu plus élevée que celle de Gemini, ce qui reste acceptable pour un assistant qui prépare une
annonce. Un détail technique a son importance : ces modèles dits « à raisonnement » peuvent passer
tout leur budget de réponse à réfléchir et ne jamais produire le résultat demandé ; on a donc
**désactivé le raisonnement** pour cette tâche de simple lecture d'image, ce qui a rendu la
comparaison équitable et fiable.

---

## 6. La fiche en production : mesure de bout en bout sur le panel réel

Les sections précédentes répondent à la question scientifique « la photo vaut-elle mieux que le
texte ? » dans un cadre de comparaison contrôlé. Une fois cette démonstration faite, il restait une
question complémentaire, plus terre à terre : **le pipeline complet, tel qu'il tourne réellement en
production, produit-il une fiche utilisable à partir d'une seule photo ?** On a donc ajouté une
mesure de bout en bout, qui ne compare plus six situations entre elles mais évalue la sortie finale
du système réel, dans le scénario le plus exigeant : **la photo seule, sans aucune précision saisie
par le vendeur**.

### 6.1 Le protocole de mesure de qualité de fiche

Le script `scripts/mesure_qualite_fiche.py` fait passer un panel de produits réels (le répertoire
`data/photos_eval/`, où **le nom de chaque dossier sert de vérité-terrain**, par exemple
`07_coros_pace_2`) à travers l'API exactement comme le ferait un vendeur : envoi des photos
(`/upload`), identification (`/identify`), puis tarification (`/price`). Pour chaque produit on
mesure des grandeurs objectives et reproductibles.

- **L'identification** : on extrait les **tokens clés** du nom de dossier (en retirant le préfixe
  numérique et quelques mots vides), et on regarde quelle part de ces tokens se retrouve dans
  (la famille de produit jugée par l'IA + le titre du candidat de tête). Le **rappel** de tokens est
  cette part ; un produit est compté « identifié » dès que **la moitié au moins** des tokens clés
  sont retrouvés (seuil `_IDENTIFY_OK_THRESHOLD = 0.5`).
- **La complétude de la fiche** : la part des caractéristiques attendues effectivement remplies
  (le champ `completeness` de la fiche assemblée), exactement la mesure principale des sections
  précédentes, mais relevée ici sur la **sortie de production**.
- **Le niveau de prix** : quel maillon de la cascade de tarification a réellement servi (L1, L1.5,
  L2, L3 ou L4), ce qui dit sur quoi le prix s'appuie.
- **Des signaux métier** : la passe d'identification raisonnée a-t-elle bien été exécutée, le système
  a-t-il signalé que le produit était **absent du catalogue** (« catalog-miss »), a-t-il **posé une
  question** discriminante au vendeur.

Ce protocole remplace les anecdotes par un **chiffre défendable** : on n'affirme plus « ça marche
bien sur les exemples qu'on a regardés », on mesure sur l'ensemble du panel et on publie le résultat,
y compris les échecs. C'est la même discipline que dans le reste du projet : mesurer sur de vraies
sorties plutôt que sur des impressions.

### 6.2 Les résultats mesurés (panel de 94 dossiers, 93 produits évalués)

Le panel compte 94 dossiers, dont un (`_cache`) ne contient pas de photo et n'est donc pas évalué :
la mesure porte sur **93 produits réels**, sans aucune erreur d'exécution.

| Mesure | Résultat |
|---|---|
| Identification (au moins 50 % des tokens clés retrouvés) | **90,3 %** |
| Rappel moyen de tokens | 78 % |
| Complétude de fiche (moyenne) | **0,84** |
| Complétude de fiche (médiane) | 0,83 |
| Passe d'identification raisonnée exécutée | 100 % |
| Produit absent du catalogue (« catalog-miss ») | 28 % |
| Question discriminante posée au vendeur | 11 % |
| Niveau de prix L1 (prix catalogue réel) | 42 produits |
| Niveau de prix L1.5 (ancre prix neuf estimée par IA) | 51 produits |

Lecture de ces chiffres.

- **Plus de neuf produits sur dix sont correctement identifiés** à partir de la photo seule, sans le
  moindre mot du vendeur. C'est la mesure qui valide la promesse « donnez une photo, je m'occupe du
  reste » dans son scénario le plus dur.
- **La fiche est remplie à 84 % en moyenne** sur ce même scénario photo seule. Une fiche n'est donc
  pas un squelette à compléter, mais une annonce déjà largement renseignée que le vendeur n'a plus
  qu'à relire.
- **La passe d'identification raisonnée tourne sur 100 % des cas** : elle ne tombe jamais en panne
  silencieuse. Quand elle ne peut pas conclure, c'est un choix explicite (catalog-miss à 28 %,
  question posée à 11 %), pas un plantage.
- **Le prix s'appuie majoritairement sur des ancres solides.** Sur les 93 produits, 42 obtiennent un
  prix à partir du **prix catalogue réel** du produit identifié (niveau L1) et 51 à partir d'une
  **ancre de prix neuf estimée par l'IA** (niveau L1.5). Aucun produit ne retombe sur les médianes de
  voisins (L2/L3) ni sur la saisie manuelle (L4) : c'est le résultat direct du fait d'avoir
  **rétrogradé les médianes** (polluées par les accessoires et les bundles, elles donnaient par
  exemple 6 € pour une montre à 150 €) **derrière l'ancre IA** dans la cascade.

### 6.3 Les neuf produits non identifiés, expliqués un par un

L'honnêteté impose de ne pas masquer les échecs : 9 produits sur 93 (les 10 % manquants) n'atteignent
pas le seuil d'identification. Aucun n'est un mystère ; on les classe en trois familles d'explication.

1. **Limite de perception du modèle** (le cas le plus fréquent). Le modèle vision-langage choisit un
   appareil voisin mais d'une génération ou d'un modèle différent, parce que rien ne distingue
   visuellement les deux sur les photos envoyées : une carte graphique RTX 4080 Super lue comme une
   3080, une Xbox Series S confondue avec une autre console, un casque Sennheiser Momentum pris pour
   un Philips. C'est la limite de fond de l'approche par image, déjà annoncée plus haut.
2. **Produit réellement absent du catalogue** (« catalog-miss » légitime). Certains objets, comme un
   SSD précis ou une station d'accueil, n'ont pas de fiche correspondante dans le catalogue de
   référence : le système le **signale** correctement plutôt que de coller à un sosie, ce qui est le
   comportement souhaité.
3. **Nom de dossier ambigu** (artefact de mesure, pas une vraie erreur). Quand la vérité-terrain
   elle-même est imprécise (un dossier nommé de façon trop générique), le calcul de rappel de tokens
   sous-estime mécaniquement la réussite : le produit est correctement reconnu, mais la mesure ne
   peut pas le constater faute de tokens clairs à comparer.

Cette ventilation est importante : elle montre que le taux de 90,3 % n'est pas un plafond accidentel
mais un résultat compréhensible, dont chaque exception a une cause identifiée et, dans deux cas sur
trois, un comportement système correct (signalement du catalog-miss, robustesse face à un sosie).

### 6.4 Comment la production sécurise une identification incertaine

Mesurer un taux d'erreur ne suffit pas : il faut dire ce que le produit **fait** des cas incertains.
Trois mécanismes, tous vérifiés en fonctionnement réel, transforment une perception fragile en une
expérience honnête pour le vendeur.

- **L'identification raisonnée** (`src/vlm/reasoned_identification.py`). Le moteur de recherche
  apporte la **connaissance** (les quinze fiches candidates les plus proches), et le modèle apporte
  le **jugement** : en un seul appel, à partir des photos du vendeur et de ces quinze fiches
  **résumées en texte** (et non des quinze images du catalogue, pour économiser des jetons), il
  désigne la bonne fiche, estime un **prix neuf de référence**, et signale s'il faut poser une
  question. Le candidat retenu **remonte en tête**, si bien que la fiche, le prix et la validation
  portent enfin sur le bon objet. Avant ce mécanisme, le premier résultat de la recherche pouvait
  être un accessoire (par exemple une coque d'iPhone affichée comme « le produit »).
- **Des garde-fous anti-invention stricts.** Le modèle ne peut jamais introduire un produit hors des
  quinze candidats : s'il cite une fiche inexistante, on retombe sur le premier résultat de la
  recherche **et** on remet sa confiance à zéro (il n'a pas endossé ce choix). Une caractéristique
  dont la source est invalide est jetée. Et surtout, tout cela est **non bloquant** : pas de clé
  d'API, modèle indisponible, réponse illisible - la fonction renvoie « rien » et le pipeline garde
  le classement de la recherche et la cascade de prix. Le système ne plante jamais et ne montre
  jamais de fiche vide.
- **Le texte vendeur fait foi quand il est présent.** Si le vendeur nomme un produit qui figure parmi
  les candidats (avec un recouvrement suffisant de mots, en conservant les numéros de modèle même à
  un seul chiffre, pour distinguer un « Momentum 3 » d'un « 2.0 »), ce candidat est retenu de façon
  **déterministe**, indépendamment du modèle rapide qui ignore parfois la consigne. En cas d'égalité,
  on prend le candidat au prix **représentatif** (le plus proche de la médiane), pour éviter de bâtir
  la fiche sur une donnée corrompue (par exemple un même produit listé à 9755 $ par erreur de saisie).
  C'est ce mécanisme qui « sauve » l'identification quand la photo seule échoue : la métadonnée, même
  inutile en moyenne (section 4.3), redevient précieuse précisément sur les cas où la perception
  visuelle bute, dès lors que le produit est bien au catalogue.

À l'écran, l'incertitude restante est rendue **lisible et actionnable** plutôt que masquée. Le
pourcentage de confiance n'est affiché que s'il est net (au moins 60 %), car un pourcentage bas
reflète souvent une simple **fragmentation du vote** sur la variante exacte (un casque qui pourrait
être plusieurs modèles voisins), pas un doute sur la catégorie. Dans ce cas, un bandeau « Modèle à
confirmer » invite le vendeur à préciser le modèle ou à photographier l'étiquette, en reprenant la
question discriminante de l'IA si elle en a posé une. Un produit absent du catalogue est signalé par
un bandeau « Produit estimé, absent du catalogue », et l'ancre de prix neuf estimée porte l'étiquette
explicite « Prix neuf estimé par IA » (niveau L1.5), pour ne jamais faire passer une estimation pour
un fait.

---

## 7. Regard critique : ce qui est solide, ce qui est limité

**Ce qui est solide.**

- Les conclusions reposent sur des **produits réels** et sur des **tests appariés** (chaque produit
  est son propre témoin), pas sur des moyennes brutes.
- L'absence d'effet de la métadonnée est **démontrée** par un test d'équivalence, pas seulement
  constatée.
- La stratification anti-fuite a réellement servi : elle a démasqué un faux gain qui aurait conduit
  à une conclusion erronée.
- Chaque extraction de photo est mise en cache, donc les résultats sont reproductibles et les
  différences observées sont bien attribuables au maillon testé.
- Le choix du modèle d'extraction est tranché par la mesure (qualité et coût réels), pas par
  préférence.
- La qualité de la **fiche de production** est elle aussi mesurée de bout en bout (section 6), pas
  seulement la comparaison des maillons : 90,3 % d'identification et 0,84 de complétude sur la photo
  seule, avec chaque échec expliqué. On ne se contente pas de prouver que la photo est utile, on
  montre ce que le système réel en fait.

**Les limites, assumées.**

- L'échantillon de 93 produits est réel mais modeste. Les écarts faibles (par exemple entre modèles
  sur l'identification) tombent logiquement dans le bruit statistique, et on l'a dit clairement
  plutôt que de survendre une avance.
- **Tous** les modèles échouent à distinguer les générations d'un même appareil quand elles sont
  visuellement identiques (le cas typique est l'iPhone, où une génération ressemble à la précédente).
  C'est une limite de fond de l'approche par image, pas un défaut d'un modèle particulier, et il faut
  l'annoncer honnêtement.
- **La perception du modèle exact est limitée sur la photo seule** quand l'objet ne porte aucun
  marquage visible sur les photos envoyées (le cas typique est le casque Sennheiser Momentum 3, dont
  le logo est sur l'étui). Le modèle peut alors choisir un sosie avec aplomb. Cette limite est
  **atténuée**, pas niée : par le texte vendeur qui fait foi (la métadonnée fixe le produit dès qu'il
  est au catalogue), par le bandeau « Modèle à confirmer », et par le bouton « Ce n'est pas le bon
  produit ? ». La métadonnée, inutile en moyenne, redevient donc précieuse exactement sur ces cas
  difficiles.
- **Le modèle rapide sous-déclenche le signalement « absent du catalogue ».** Qwen 3.5 Flash a
  tendance à coller à un sosie d'une autre génération (un iPhone 14 lu comme un 13, une RTX 4080 comme
  une 3080) plutôt qu'à déclarer le produit absent du catalogue. Un modèle jugé plus fort ferait
  mieux : c'est une option prévue (variable d'environnement dédiée au modèle d'identification), non
  activée par défaut pour ne pas alourdir le coût.
- **Le garde-fou anti sous-évaluation du prix est surtout défensif.** Ce n'est pas lui qui fait le
  vrai travail de tarification : c'est le niveau L1.5 (l'ancre de prix neuf estimée par l'IA, placée
  avant les médianes polluées) qui assure des prix cohérents. Le garde-fou ne sert qu'à rattraper les
  cas résiduels où une médiane s'effondrerait malgré tout.
- L'étude de la chaîne de valeur a été menée avec le modèle Gemma comme lecteur de photos (le modèle
  par défaut à ce moment), avant que la comparaison de modèles ne désigne Qwen comme meilleur choix.
  Cela ne change pas les conclusions relatives (photo contre texte, une photo contre plusieurs,
  effet de la métadonnée), car toutes les situations ont été lues par le **même** modèle : on compare
  donc bien ce qui est comparable.
- La qualité **rédactionnelle** du texte final (est-il agréable à lire, bien tourné) n'est pas
  évaluée ici : ce document mesure la complétude et l'exactitude par des critères objectifs, pas le
  style. C'est un prolongement possible.

---

## 8. En une phrase, pour la soutenance

*On a démontré, sur 93 annonces réelles et avec des tests appariés, que la photo est le maillon
décisif pour produire une fiche complète et bien identifiée (la photo bat le texte du vendeur quand
celui-ci décrit mal son objet, gain de 0,145 de complétude, et plusieurs photos valent mieux
qu'une), que la métadonnée saisie par le vendeur n'apporte rien une fois les photos là (équivalence
prouvée par un test TOST, après avoir écarté un faux gain dû à une fuite d'annotation), et que parmi
quatre modèles de lecture d'image, Qwen 3.5 Flash offre le meilleur compromis qualité-coût, retenu
comme modèle par défaut. En production, le pipeline complet identifie correctement 90,3 % des
produits à partir de la photo seule et remplit la fiche à 0,84 en moyenne, chaque échec étant
expliqué et l'incertitude rendue actionnable pour le vendeur.*
