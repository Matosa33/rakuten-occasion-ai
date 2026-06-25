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

## 6. Regard critique : ce qui est solide, ce qui est limité

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

**Les limites, assumées.**

- L'échantillon de 93 produits est réel mais modeste. Les écarts faibles (par exemple entre modèles
  sur l'identification) tombent logiquement dans le bruit statistique, et on l'a dit clairement
  plutôt que de survendre une avance.
- **Tous** les modèles échouent à distinguer les générations d'un même appareil quand elles sont
  visuellement identiques (le cas typique est l'iPhone, où une génération ressemble à la précédente).
  C'est une limite de fond de l'approche par image, pas un défaut d'un modèle particulier, et il faut
  l'annoncer honnêtement.
- L'étude de la chaîne de valeur a été menée avec le modèle Gemma comme lecteur de photos (le modèle
  par défaut à ce moment), avant que la comparaison de modèles ne désigne Qwen comme meilleur choix.
  Cela ne change pas les conclusions relatives (photo contre texte, une photo contre plusieurs,
  effet de la métadonnée), car toutes les situations ont été lues par le **même** modèle : on compare
  donc bien ce qui est comparable.
- La qualité **rédactionnelle** du texte final (est-il agréable à lire, bien tourné) n'est pas
  évaluée ici : ce document mesure la complétude et l'exactitude par des critères objectifs, pas le
  style. C'est un prolongement possible.

---

## 7. En une phrase, pour la soutenance

*On a démontré, sur 93 annonces réelles et avec des tests appariés, que la photo est le maillon
décisif pour produire une fiche complète et bien identifiée (la photo bat le texte du vendeur quand
celui-ci décrit mal son objet, gain de 0,145 de complétude, et plusieurs photos valent mieux
qu'une), que la métadonnée saisie par le vendeur n'apporte rien une fois les photos là (équivalence
prouvée par un test TOST, après avoir écarté un faux gain dû à une fuite d'annotation), et que parmi
quatre modèles de lecture d'image, Qwen 3.5 Flash offre le meilleur compromis qualité-coût, retenu
comme modèle par défaut.*
