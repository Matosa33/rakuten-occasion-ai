# 15. Frontend et experience vendeur

> L'interface que le vendeur utilise vraiment : photographier, valider, publier. C'est ici que toute la chaine de traitement par intelligence artificielle devient un produit reellement utilisable, et c'est ici que la qualite de l'experience decide si le vendeur va jusqu'au bout de sa mise en vente.

---

## 1. La technologie : de quoi parle-t-on ?

### Pour comprendre

Un frontend, c'est tout simplement l'application que l'on voit dans le navigateur web. La notre est ce qu'on appelle une application a page unique (en anglais Single Page Application) : une seule page web qui se met a jour toute seule au fur et a mesure des actions, sans jamais recharger entierement l'ecran a chaque clic. Le resultat est fluide, comme une vraie application installee sur un telephone.

Le vendeur y suit un parcours simple en trois etapes :
1. Decrire : il prend des photos de son objet et indique son etat.
2. Identifier : l'intelligence artificielle propose des produits qui ressemblent au sien, et le vendeur choisit le bon.
3. Vendre : l'application propose un prix et redige une annonce que le vendeur peut modifier avant de la publier.

Le principe de fond, ici, est que l'intelligence artificielle propose mais ne decide jamais seule. Le vendeur valide et corrige a chaque etape. On appelle cela une boucle avec humain dans le circuit (en anglais human-in-the-loop). Ce choix sert deux objectifs a la fois : il rassure le vendeur (il garde le controle de son annonce), et il rattrape les erreurs eventuelles du modele (un humain repere immediatement une proposition absurde).

Une refonte recente du parcours vendeur a deplace le curseur dans le bon sens : quand l'intelligence artificielle est vraiment sure de son identification, elle saute l'etape de selection et emmene directement le vendeur a l'annonce finale (moins de clics, parcours plus fluide). Quand elle hesite, elle montre les candidats. Et dans tous les cas, le vendeur garde une porte de sortie sur la fiche finale : un bouton explicite "Ce n'est pas le bon produit ? Voir les autres resultats". Le but est de fluidifier le cas facile sans jamais enfermer le vendeur sur une mauvaise proposition. Cette refonte est detaillee en section 3 (parcours vendeur refondu).

### Pour l'expert

L'application est construite avec les outils suivants :
- React (version 19) pour construire l'interface a partir de petits blocs reutilisables appeles composants.
- Vite (version 6) comme outil qui assemble et optimise le code pour le navigateur.
- Tailwind (version 4) pour la mise en forme visuelle.
- Framer Motion pour les animations (transitions entre etapes, apparition des elements).
- TypeScript en mode strict : une variante de JavaScript qui verifie les types de donnees avant meme d'executer le code, ce qui evite une large categorie de bugs.

La gestion de la connexion (le fait de savoir si l'utilisateur est connecte ou non) repose sur un mecanisme standard de React nomme `useSyncExternalStore`. Concretement, l'application surveille un jeton d'authentification stocke dans le navigateur. Des qu'il change (connexion, deconnexion, ou expiration de session), toute l'interface se remet a jour automatiquement, sans qu'on ait besoin de transmettre cette information manuellement de composant en composant.

---

## 2. Etat de l'art : les bonnes pratiques du domaine

### Construction d'interfaces modernes

Les interfaces web actuelles sont batuies a partir de composants : des morceaux d'interface autonomes et reutilisables (un bouton, une carte produit, une galerie de photos). On garde le moins d'informations en memoire possible, et l'affichage decoule automatiquement de ces informations. Cette approche est dite declarative : on decrit ce que l'on veut voir, et le systeme s'occupe de mettre l'ecran a jour.

### Experience des applications a base d'intelligence artificielle

Trois principes font consensus pour les applications qui exposent des resultats d'intelligence artificielle :
- Le devoilement progressif (en anglais progressive disclosure) : on montre l'avancement etape par etape plutot que de tout afficher d'un coup.
- La validation humaine systematique des resultats incertains : l'application ne publie jamais quelque chose automatiquement.
- L'honnetete des predictions : on ne presente jamais une prediction comme une verite absolue. On affiche toujours un niveau de confiance.

### Psychologie de la decision appliquee a la conversion

Pour qu'un vendeur aille jusqu'au bout de la mise en vente, on s'appuie sur quelques effets bien documentes en psychologie de la decision :
- La loi de Hick : plus on propose de choix, plus la decision est lente. Limiter le nombre d'options accelere donc l'action.
- L'effet d'ancrage : afficher un prix de reference oriente la perception de ce qui est cher ou bon marche.
- L'effet IKEA : on attache plus de valeur a ce que l'on a soi-meme construit ou modifie. Un vendeur qui a personnalise son annonce a davantage envie de la publier.
- L'effet Zeigarnik : une tache commencee mais inachevee cree une tension qui pousse a la terminer. Une barre de progression exploite ce ressort.

---

## 3. Notre realisation (precisement ce qui a ete fait)

### Organisation du code

Le code source du frontend represente environ 2 300 lignes (2 291 exactement, en comptant tous les fichiers TypeScript et TSX du dossier `frontend/src`). Il s'articule autour de trois fichiers centraux, d'un module de logique d'etat (la pre-qualification de l'objet) et de huit composants d'interface.

Les trois fichiers centraux :
- Le chef d'orchestre de l'interface gere les trois etapes, bascule entre les deux modes d'utilisation, et appelle les services du serveur au bon moment.
- Le client de communication avec le serveur centralise tous les appels reseau. Il ajoute automatiquement le jeton d'authentification a chaque requete, gere le cas ou la session a expire, et partage avec le serveur les definitions de donnees pour eviter les incoherences.
- Le gestionnaire de connexion stocke le jeton d'authentification dans le navigateur et previent l'interface des qu'il change.

### A quoi sert chaque jeton d'authentification

Quand le vendeur se connecte, le serveur lui remet un jeton (en anglais un JWT, JSON Web Token : une sorte de badge electronique signe qui prouve qui vous etes). Ce badge est joint a chaque demande ulterieure sous une forme standard appelee Bearer. S'il est absent, expire ou invalide, le serveur repond par un code d'erreur 401 (non autorise), l'application efface le badge et ramene aussitot le vendeur a l'ecran de connexion.

### Les huit composants d'interface

| Composant | Role |
|---|---|
| Televersement des photos | Permet de glisser-deposer des images depuis un ordinateur, ou de declencher directement l'appareil photo arriere sur mobile grace a l'attribut `capture=environment`. Limite a 5 photos maximum, affiche des apercus, et bloque l'identification tant qu'au moins 1 photo n'a pas ete fournie. |
| Liste de controle d'etat | Propose une courte liste de questions sur l'etat de l'objet (les details qui font une bonne annonce). Depuis la refonte, elle ne demande plus au vendeur de choisir un type d'objet : seules les questions universelles sont posees a l'etape de description, et les questions specifiques au type (sante batterie d'un telephone, clavier d'un ordinateur, manettes d'une console, etc.) s'affichent plus tard, sur la fiche finale, une fois le type deduit automatiquement de la categorie identifiee. |
| Selection du candidat | Affiche les produits proposes par l'intelligence artificielle, avec une galerie des photos du catalogue et un indicateur de correspondance visuelle. |
| Annonce finale | Presente l'annonce telle qu'elle sera publiee : fil d'ariane de la categorie, galerie des photos du vendeur, prix avec son niveau de confiance, etiquette d'etat, indicateur de confiance d'identification (affiche seulement s'il est net), bandeaux d'alerte ("produit estime, absent du catalogue" et "modele a confirmer"), tableau de caracteristiques structurees a provenance, questions d'etat specifiques au type, et description modifiable. |
| Visionneuse plein ecran | Affiche les photos en grand, avec navigation au clavier et fleches. |
| Barre de progression | Indique l'avancement dans les trois etapes (ressort Zeigarnik). |
| Page de connexion | Permet de s'identifier avec le jeton d'authentification. |
| Mode demenagement | Le mode de mise en vente en rafale, decrit plus bas. |

A l'etape de description, le vendeur renseigne aussi l'etat general parmi cinq choix (Neuf, Tres bon etat, Bon etat, Correct, Pour pieces / HS) et, en option, l'annee d'achat. Ces deux informations alimentent directement le calcul du prix : l'etat applique un multiplicateur sur le prix neuf, et l'annee permet de calculer l'age donc la depreciation. Si le vendeur ne renseigne pas l'annee, l'application suppose un age de deux ans et le signale honnetement sur la fiche ("Age suppose : 2 ans").

### Le tri intelligent des questions (logique de type Akinator)

Quand plusieurs produits candidats se ressemblent beaucoup, comment aider le vendeur a trancher en un minimum de clics ? L'application choisit elle-meme, cote navigateur, la question la plus utile a poser. C'est le meme principe que le jeu Akinator, qui devine un personnage en posant le moins de questions possible, ou qu'un arbre de decision.

Pour chaque caracteristique disponible (couleur, capacite, type de produit, marque, taille, etc.), un score est calcule en multipliant trois facteurs :

- L'entropie de Shannon normalisee. L'entropie mesure a quel point une caracteristique separe bien les candidats. Une caracteristique que tous partagent (par exemple, ils sont tous noirs) ne sert a rien : son entropie est nulle. Une caracteristique qui partage les candidats en deux groupes egaux est la plus discriminante : son entropie est maximale. La valeur est ramenee sur une echelle de 0 a 1 pour pouvoir comparer des caracteristiques qui n'ont pas le meme nombre de valeurs possibles.
- La couverture, c'est-a-dire la proportion de candidats qui possedent reellement cette caracteristique renseignee. Une caracteristique connue pour un seul candidat n'aide pas a departager les autres.
- La priorite semantique, qui favorise les caracteristiques les plus parlantes pour le vendeur. Le type de produit est multiplie par 2,0, la capacite par 1,2 et la taille par 1,1. Toutes les autres caracteristiques gardent un coefficient de 1,0. Ce reglage garantit que la question la plus eclairante (par exemple distinguer un telephone d'une coque de telephone) passe avant une question moins utile comme la marque.

L'application pose alors une seule question : celle qui obtient le meilleur score. Le vendeur clique sur une reponse, la liste de candidats se reduit, et le calcul recommence sur les candidats restants en excluant les caracteristiques deja choisies. Le serveur dispose d'une logique equivalente de selection de la prochaine observation utile ; le frontend rejoue ce raisonnement directement sur les candidats affiches, pour repondre instantanement sans rallonger la conversation avec le serveur.

### Les deux modes d'utilisation

Mode un objet (parcours guide). C'est le parcours pas a pas classique : on decrit, on identifie, on vend. A l'etape de description, deux regles importantes sont appliquees. D'abord, au moins une photo est obligatoire avant de pouvoir lancer l'identification : la photo est la preuve pour l'acheteur et le point d'entree de toute la chaine d'analyse. Ensuite, une fois le bon candidat choisi, l'application enchaine automatiquement le calcul du prix et la redaction de l'annonce, sans demander de clic intermediaire superflu (application de la loi de Hick).

Une subtilite importante concerne le calcul du prix. Pour estimer un prix juste, l'application s'appuie sur le prix du produit choisi et sur les prix des produits voisins. Mais elle ne retient que les voisins du meme type de produit que celui choisi. Sans ce filtre, des accessoires bon marche (coques, cables) feraient chuter la mediane des prix et produiraient une estimation absurde. Le front transmet aussi au calcul du prix une ancre supplementaire : le prix neuf de reference estime par l'intelligence artificielle pendant la phase d'identification raisonnee (voir section dediee plus bas). Cette ancre nourrit le niveau de cascade L1.5, qui evite des prix grotesques (par exemple six euros suggeres pour une montre a cent cinquante euros, quand les voisins etaient pollues par des accessoires). Detail important pour l'honnetete : le front n'applique cette ancre que pour le produit que l'intelligence artificielle a effectivement designe (ou un produit absent du catalogue) ; si le vendeur choisit explicitement un autre candidat, l'ancre hors-sujet n'est pas appliquee.

Mode demenagement (mise en vente en rafale). Concu pour le cas ou l'on a beaucoup d'objets a vendre d'un coup. Le vendeur photographie un objet, l'ajoute a la file, et passe immediatement au suivant, sans jamais attendre l'analyse. Les identifications tournent en arriere-plan, une a la fois pour ne pas surcharger le modele de vision. Un tableau de bord liste tous les objets avec leur statut : en file, en cours d'analyse, a valider, generation de l'annonce en cours, prete, ou en erreur. La file est sauvegardee dans le navigateur (dans ce qu'on appelle le localStorage, une petite memoire locale persistante). Ainsi, si la page est rechargee en plein milieu, rien n'est perdu : les photos sont deja sur le serveur, et un objet interrompu en pleine analyse redevient simplement actionnable. Ce mode reutilise exactement les memes composants que le parcours guide (la selection de candidat et l'annonce finale), sans duplication de code.

### La refonte du parcours vendeur

Cette refonte part d'un constat tres concret, observe sur de vraies photos : demander au vendeur de classer son objet ou de valider chaque proposition creait des frictions inutiles, et le pipeline pouvait construire une fiche sur le mauvais produit. Cette section explique les decisions de conception qui ont corrige cela.

Le type d'objet n'est plus choisi par le vendeur. Auparavant, le vendeur devait selectionner manuellement le type de son objet (telephone, ordinateur, console, outil, photo / audio / video, autre) pour declencher les bonnes questions d'etat. Le probleme : un vendeur ne sait pas toujours dans quelle case ranger une carte graphique ou un dock. Desormais, le type est deduit automatiquement de la categorie identifiee par l'intelligence artificielle, cote navigateur. La fonction de derivation reconnait les categories par mot entier (et non par simple inclusion de texte) et exclut explicitement les accessoires. Ce detail est important : sans cette precaution, un casque (en anglais "headphones", qui contient les lettres de "phone") ou un chargeur seraient ranges a tort dans la categorie telephone. Quand la categorie ne correspond a aucun type ayant des questions dediees (par exemple une carte graphique ou un produit audio), seules les questions universelles s'appliquent, ce qui est le comportement honnete (poser une question sur la "sante de la batterie" d'une carte graphique n'aurait aucun sens). Concretement, les questions d'etat specifiques au type s'affichent au bon moment : sur la fiche finale, apres l'identification, quand le type est connu de facon fiable.

L'etat "Pour pieces / HS" et l'annee d'achat. La liste des etats accueille un cinquieme choix, "Pour pieces / HS", qui correspond a un cas tres courant de l'occasion (un objet en panne mais vendable pour ses pieces). Cote prix, cet etat applique un multiplicateur de 0,15 sur le prix neuf, soit une valeur residuelle. Le champ "Annee d'achat" (facultatif) permet de calculer l'age de l'objet, donc une depreciation plus juste ; sans lui, l'application suppose deux ans et le signale.

L'auto-confirmation. Quand l'intelligence artificielle se declare sure de son identification (statut "identified"), l'application enchaine directement vers la fiche finale, sans passer par l'ecran de selection des candidats. Quand elle hesite (statut "a confirmer" ou "incertain"), elle affiche les candidats pour que le vendeur tranche. Dans les deux cas le vendeur reste maitre : sur la fiche finale, des qu'il existe plus d'un candidat, un bouton "Ce n'est pas le bon produit ? Voir les autres resultats" ramene a la liste. C'est une application directe de la loi de Hick (on epargne un clic quand le cas est facile) sans sacrifier la boucle avec humain dans le circuit.

L'affichage de la confiance d'identification, seulement quand il est net. La fiche affiche un pourcentage de confiance, mais ce pourcentage demande une explication soignee car il est facile a mal interpreter. Ce chiffre est la part du vote des plus proches voisins (le vote k plus proches voisins, en anglais k-NN) en faveur de la categorie fine. Un pourcentage bas ne veut donc pas dire "je ne sais pas si c'est un casque" : il veut dire que le vote est fragmente entre plusieurs modeles ou marques proches (le produit exact est ambigu, par exemple un casque dont le vote se disperse a trente-quatre pour cent). Afficher brutalement ce chiffre serait trompeur. L'application a donc fait un choix : elle n'affiche le pourcentage que lorsqu'il est net, c'est-a-dire superieur ou egal a soixante pour cent. En dessous de ce seuil, le doute n'est pas affiche sous forme de chiffre froid, mais traduit en action concrete par le bandeau "Modele a confirmer" decrit ci-dessous.

Les deux bandeaux d'alerte de la fiche. Deux messages peuvent apparaitre en haut de la fiche finale pour rester honnete sur le niveau de certitude :
- Le bandeau "produit estime, absent du catalogue" (catalog-miss). Il s'affiche quand l'intelligence artificielle juge qu'aucun des produits du catalogue ne correspond reellement a ce que montrent les photos. La fiche est alors presentee comme une estimation, et le vendeur est invite a verifier prix et caracteristiques.
- Le bandeau "Modele a confirmer". Il s'affiche quand l'identification du modele exact est incertaine (parce que l'intelligence artificielle a une question discriminante a poser, ou parce que le vote de categorie n'est pas net). Plutot qu'un pourcentage decourageant, ce bandeau propose une action utile : il reprend la question discriminante de l'intelligence artificielle si elle existe (par exemple sur la capacite ou la couleur exacte), ou invite a preciser le modele dans le champ "Precisions" ou a ajouter une photo de l'etiquette ou de la boite. C'est une facon de transformer le doute du modele en une demande claire et resolvable par le vendeur.

L'etiquette honnete sur le prix neuf estime par IA. Quand le prix repose sur le niveau L1.5 (l'ancre estimee par l'intelligence artificielle plutot que sur un prix catalogue reel), la carte de prix l'indique explicitement par l'etiquette "Prix neuf estime par IA". L'idee directrice de toute cette refonte est la meme : ne jamais presenter une estimation comme un fait, et toujours donner au vendeur le moyen de corriger.

### La fiche exhaustive et la provenance des champs

La fiche finale ne se contente pas d'un titre et d'un prix : elle presente un tableau de caracteristiques structurees, le bloc "Informations cles". L'objectif est une fiche aussi complete que possible, mais sans jamais affirmer une information non verifiee.

Chaque caracteristique porte une etiquette de provenance, qui dit au vendeur d'ou vient l'information. Il y a cinq provenances possibles, chacune avec sa couleur :
- "observe" : l'information a ete lue sur les photos du vendeur (la source la plus fiable pour cet objet precis).
- "catalogue" : l'information vient de la fiche catalogue d'un produit correctement identifie.
- "typique-a-verifier" : l'information est une valeur typique imputee a partir de produits comparables ; elle est marquee comme a verifier, jamais affirmee comme certaine.
- "categorie" : l'information est deduite de la categorie (par exemple le type de produit).
- "vendeur" : l'information vient du vendeur lui-meme (par exemple l'annee d'achat qu'il a saisie).

Cette transparence est le pendant visible d'un principe defendu dans tout le projet : aucune valeur sans pedigree. Un point de design concret : quand le produit est juge absent du catalogue (catalog-miss), les specifications du mauvais candidat ne sont pas presentees comme des faits. Le pied de page de l'application le resume : "Identification ancree sur catalogue, chaque champ porte sa source, aucune valeur inventee."

La fiche affiche aussi un indicateur de completude ("Fiche remplie a X pour cent"), c'est-a-dire la part des caracteristiques attendues pour cette categorie qui sont effectivement renseignees. Ce taux est calcule cote serveur sur un schema de facettes adapte a la categorie fine : on ne garde du schema general que les facettes reellement pertinentes pour la categorie fine du produit (presentes chez au moins un candidat de meme categorie fine). Cela evite de penaliser injustement une enceinte pour l'absence d'une "capacite" de stockage, qui n'a pas de sens pour elle. L'etat (un choix du vendeur, toujours disponible) est exclu de ce calcul pour ne pas fausser le score.

Le "type de produit" affiche correspond a la categorie du produit reellement identifie (celui que l'intelligence artificielle a fait remonter en tete), et non a un vote brut qui pouvait etre pollue. C'est ce qui evite, par exemple, qu'une coque fasse afficher la categorie "Basic Cases" pour un iPhone.

### Psychologie de la decision concretement appliquee

- Effet Zeigarnik : la barre de progression a trois etapes maintient une tension positive qui pousse a finir la mise en vente commencee.
- Loi de Hick : on met en avant seulement les trois meilleurs candidats, la liste complete restant accessible mais repliee. On enchaine aussi le prix et l'annonce sans clic supplementaire.
- Effet d'ancrage : la carte de prix affiche un prix conseille accompagne d'une fourchette de reference, ce qui oriente la perception de la valeur.
- Effet IKEA : l'annonce (titre et description) est entierement modifiable. En la personnalisant, le vendeur se l'approprie, et donc la publie plus volontiers.

---

## 4. Resultats (mesures)

- Taille du paquet de production. Une fois le code compile et optimise, le fichier JavaScript principal pesait, lors de la derniere mesure de paquet, 343 kilo-octets (environ 109 kilo-octets une fois compresse pour le transfert reseau) et la feuille de style 21 kilo-octets (environ 5 kilo-octets compresses). C'est tres leger : la page se charge vite, meme sur une connexion mobile. La derniere refonte a ajoute du code (le frontend est passe d'environ 2 000 a environ 2 300 lignes), donc ces chiffres precis sont a remesurer apres un nouveau build pour la presentation finale.
- Qualite du code. La compilation verifie l'integralite des types de donnees en mode strict, sans aucune erreur signalee, avant chaque assemblage de production.
- Qualite de la fiche mesuree sur de vraies photos. Un protocole de mesure reproductible (un script dedie) fait passer un panel reel de 94 produits (les noms de dossiers servent de verite-terrain), a partir de la photo seule, sans precisions texte. Sur ce panel, 93 produits sur 94 ont ete mesures sans erreur. Les resultats : un taux d'identification correcte de 90,3 pour cent (au sens : au moins la moitie des mots-cles du nom retrouves dans la famille proposee par l'intelligence artificielle et dans le titre du meilleur candidat), avec un rappel moyen des mots-cles de 78 pour cent ; une completude de fiche moyenne de 0,84 et mediane de 0,83 ; une passe d'identification raisonnee presente dans 100 pour cent des cas ; un taux de "produit absent du catalogue" de 28 pour cent ; une question discriminante posee dans 11 pour cent des cas ; et une repartition des niveaux de prix de 42 fiches au niveau L1 (prix catalogue reel) contre 51 au niveau L1.5 (prix neuf estime par IA). Les neuf produits non identifies sont tous expliques (un defaut de perception du modele exact sur la photo, un produit reellement absent du catalogue, ou un nom de dossier ambigu qui est un artefact de la mesure). Cette approche remplace les anecdotes par un chiffre defendable.
- Parcours complet fonctionnel. L'enchainement entier a ete valide : connexion, ajout de photos, affichage des candidats (avec galerie et indicateur de correspondance visuelle), puis annonce de qualite marketplace, modifiable, verifiee visuellement par un humain.
- Mise en production. Le code est servi dans un conteneur (un environnement logiciel isole et reproductible). Le code est d'abord compile par Node, puis les fichiers obtenus sont servis par nginx, un serveur web leger et rapide. La verification de bout en bout cote serveur passe les six controles prevus.

> Chiffres pour la presentation : React version 19, huit composants d'interface, deux modes d'utilisation (un objet et mise en vente en rafale), tri des questions par entropie de Shannon multipliee par la couverture et la priorite semantique, quatre principes de psychologie de la decision (Zeigarnik, Hick, ancrage, IKEA), cinq niveaux de cascade de prix (L1, L1.5, L2, L3, L4), cinq provenances de champ sur la fiche (observe, catalogue, typique-a-verifier, categorie, vendeur). Qualite mesuree sur un panel reel de 94 produits a partir de la photo seule : identification correcte 90,3 pour cent, completude de fiche 0,84 en moyenne. Capture d'ecran a montrer : les trois etapes du parcours, l'auto-confirmation vers la fiche, les bandeaux "produit estime" et "modele a confirmer", l'annonce finale modifiable avec ses caracteristiques sourcees, et le tableau de bord du mode demenagement. C'est la partie la plus demonstrative visuellement.

---

## 5. Regard critique : etat de l'art comparé a notre realisation

### Ce qui est solide

- Une application a page unique moderne et typee (React 19, Vite, TypeScript strict), avec des composants reutilises sans aucune duplication entre les deux modes : le mode en rafale s'appuie sur les memes briques que le parcours guide.
- La boucle avec humain dans le circuit et l'annonce modifiable apportent a la fois confiance et rattrapage des erreurs du modele.
- Une experience reflechie : guidage des prises de vue selon le type d'objet, indicateur de correspondance visuelle, desambiguisation en un clic guidee par l'entropie, et progression toujours visible.
- Un parcours honnete sur l'incertitude : auto-confirmation quand l'intelligence artificielle est sure, candidats sinon, et toujours un bouton "ce n'est pas le bon" ; confiance affichee seulement quand elle est nette ; bandeaux d'alerte "produit estime" et "modele a confirmer" qui transforment le doute en action ; et caracteristiques de la fiche etiquetees par leur provenance (aucune valeur inventee).
- Un veritable mode rafale, avec file persistante et traitement en arriere-plan, pour le cas concret du demenagement.

### Limites assumees

- Identification du modele exact a partir de la photo seule. Quand un produit ne porte aucun marquage visible sur les photos envoyees (par exemple un casque dont le logo est sur l'etui), le modele de vision peut choisir un sosie avec aplomb (une autre generation, un produit ressemblant). Trois garde-fous limitent les degats : le texte du vendeur fait foi s'il nomme le produit (et que ce produit est au catalogue), le bandeau "modele a confirmer", et le bouton "ce n'est pas le bon". Cette limite est documentee honnetement plutot que masquee.
- Pas de tests automatises de l'interface. La chaine cote serveur est testee de bout en bout, mais les interactions d'interface ne sont pas verifiees automatiquement par un robot de test. C'est un axe d'amelioration identifie.
- Logique de selection de question presente a deux endroits. Le calcul de la caracteristique la plus discriminante existe a la fois dans le navigateur et sur le serveur. C'est pratique (le navigateur reagit sans aller-retour reseau), mais cela cree deux sources de verite potentielles a maintenir cohrentes.
- Accessibilite non auditee. Les contrastes de couleur, la navigation complete au clavier et les indications pour les lecteurs d'ecran n'ont pas fait l'objet d'un audit formel. C'est indispensable pour un vrai produit grand public.
- Stockage local de la file en rafale. Le recours a la memoire locale du navigateur est simple, mais limite : quota de stockage restreint, et absence de synchronisation entre plusieurs appareils.

---

## 6. References

- React : penser une interface en composants. https://react.dev/learn/thinking-in-react
- React : le mecanisme `useSyncExternalStore` pour brancher un etat externe. https://react.dev/reference/react/useSyncExternalStore
- Nielsen Norman Group : le devoilement progressif (progressive disclosure). https://www.nngroup.com/articles/progressive-disclosure/
- Laws of UX : la loi de Hick et l'effet Zeigarnik. https://lawsofux.com/

---

### En une phrase (pour la defense)

Le frontend React transforme la chaine de traitement en un vrai produit : un parcours guide en trois etapes ou la photo est obligatoire, ou l'intelligence artificielle propose mais ou l'humain valide et modifie (effet IKEA), avec une desambiguisation en un clic choisie par entropie, et un mode rafale pour le demenagement. La derniere refonte le rend a la fois plus fluide (auto-confirmation quand l'identification est sure, type d'objet et questions d'etat derives automatiquement, etat "pour pieces" et annee d'achat) et plus honnete (confiance affichee seulement quand elle est nette, bandeaux "produit estime" et "modele a confirmer", prix neuf estime etiquete comme tel, et chaque caracteristique de la fiche portant sa provenance), le tout valide par une mesure chiffree sur un panel reel (90,3 pour cent d'identification correcte). Des principes de psychologie de la decision (Hick, Zeigarnik, ancrage) y sont appliques pour maximiser le passage a l'acte de mise en vente.
