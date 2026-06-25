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

Le code source du frontend represente environ 2 000 lignes (1 998 exactement). Il s'articule autour de trois fichiers centraux et de huit composants d'interface.

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
| Liste de controle d'etat | Demande le type d'objet, affiche des conseils de prises de vue adaptes a ce type, puis propose une courte liste de questions sur l'etat de l'objet (les details qui font une bonne annonce). |
| Selection du candidat | Affiche les produits proposes par l'intelligence artificielle, avec une galerie des photos du catalogue et un indicateur de correspondance visuelle. |
| Annonce finale | Presente l'annonce telle qu'elle sera publiee : fil d'ariane de la categorie, galerie des photos du vendeur, prix, etiquette d'etat, tableau de caracteristiques structurees et description modifiable. |
| Visionneuse plein ecran | Affiche les photos en grand, avec navigation au clavier et fleches. |
| Barre de progression | Indique l'avancement dans les trois etapes (ressort Zeigarnik). |
| Page de connexion | Permet de s'identifier avec le jeton d'authentification. |
| Mode demenagement | Le mode de mise en vente en rafale, decrit plus bas. |

### Le tri intelligent des questions (logique de type Akinator)

Quand plusieurs produits candidats se ressemblent beaucoup, comment aider le vendeur a trancher en un minimum de clics ? L'application choisit elle-meme, cote navigateur, la question la plus utile a poser. C'est le meme principe que le jeu Akinator, qui devine un personnage en posant le moins de questions possible, ou qu'un arbre de decision.

Pour chaque caracteristique disponible (couleur, capacite, type de produit, marque, taille, etc.), un score est calcule en multipliant trois facteurs :

- L'entropie de Shannon normalisee. L'entropie mesure a quel point une caracteristique separe bien les candidats. Une caracteristique que tous partagent (par exemple, ils sont tous noirs) ne sert a rien : son entropie est nulle. Une caracteristique qui partage les candidats en deux groupes egaux est la plus discriminante : son entropie est maximale. La valeur est ramenee sur une echelle de 0 a 1 pour pouvoir comparer des caracteristiques qui n'ont pas le meme nombre de valeurs possibles.
- La couverture, c'est-a-dire la proportion de candidats qui possedent reellement cette caracteristique renseignee. Une caracteristique connue pour un seul candidat n'aide pas a departager les autres.
- La priorite semantique, qui favorise les caracteristiques les plus parlantes pour le vendeur. Le type de produit est multiplie par 2,0, la capacite par 1,2 et la taille par 1,1. Toutes les autres caracteristiques gardent un coefficient de 1,0. Ce reglage garantit que la question la plus eclairante (par exemple distinguer un telephone d'une coque de telephone) passe avant une question moins utile comme la marque.

L'application pose alors une seule question : celle qui obtient le meilleur score. Le vendeur clique sur une reponse, la liste de candidats se reduit, et le calcul recommence sur les candidats restants en excluant les caracteristiques deja choisies. Le serveur dispose d'une logique equivalente de selection de la prochaine observation utile ; le frontend rejoue ce raisonnement directement sur les candidats affiches, pour repondre instantanement sans rallonger la conversation avec le serveur.

### Les deux modes d'utilisation

Mode un objet (parcours guide). C'est le parcours pas a pas classique : on decrit, on identifie, on vend. A l'etape de description, deux regles importantes sont appliquees. D'abord, au moins une photo est obligatoire avant de pouvoir lancer l'identification : la photo est la preuve pour l'acheteur et le point d'entree de toute la chaine d'analyse. Ensuite, une fois le bon candidat choisi, l'application enchaine automatiquement le calcul du prix et la redaction de l'annonce, sans demander de clic intermediaire superflu (application de la loi de Hick).

Une subtilite importante concerne le calcul du prix. Pour estimer un prix juste, l'application s'appuie sur le prix du produit choisi et sur les prix des produits voisins. Mais elle ne retient que les voisins du meme type de produit que celui choisi. Sans ce filtre, des accessoires bon marche (coques, cables) feraient chuter la mediane des prix et produiraient une estimation absurde.

Mode demenagement (mise en vente en rafale). Concu pour le cas ou l'on a beaucoup d'objets a vendre d'un coup. Le vendeur photographie un objet, l'ajoute a la file, et passe immediatement au suivant, sans jamais attendre l'analyse. Les identifications tournent en arriere-plan, une a la fois pour ne pas surcharger le modele de vision. Un tableau de bord liste tous les objets avec leur statut : en file, en cours d'analyse, a valider, generation de l'annonce en cours, prete, ou en erreur. La file est sauvegardee dans le navigateur (dans ce qu'on appelle le localStorage, une petite memoire locale persistante). Ainsi, si la page est rechargee en plein milieu, rien n'est perdu : les photos sont deja sur le serveur, et un objet interrompu en pleine analyse redevient simplement actionnable. Ce mode reutilise exactement les memes composants que le parcours guide (la selection de candidat et l'annonce finale), sans duplication de code.

### Psychologie de la decision concretement appliquee

- Effet Zeigarnik : la barre de progression a trois etapes maintient une tension positive qui pousse a finir la mise en vente commencee.
- Loi de Hick : on met en avant seulement les trois meilleurs candidats, la liste complete restant accessible mais repliee. On enchaine aussi le prix et l'annonce sans clic supplementaire.
- Effet d'ancrage : la carte de prix affiche un prix conseille accompagne d'une fourchette de reference, ce qui oriente la perception de la valeur.
- Effet IKEA : l'annonce (titre et description) est entierement modifiable. En la personnalisant, le vendeur se l'approprie, et donc la publie plus volontiers.

---

## 4. Resultats (mesures)

- Taille du paquet de production. Une fois le code compile et optimise, le fichier JavaScript principal pese 343 kilo-octets (environ 109 kilo-octets une fois compresse pour le transfert reseau). La feuille de style pese 21 kilo-octets (environ 5 kilo-octets compresses). C'est tres leger : la page se charge vite, meme sur une connexion mobile.
- Qualite du code. La compilation verifie l'integralite des types de donnees en mode strict, sans aucune erreur signalee, avant chaque assemblage de production.
- Parcours complet fonctionnel. L'enchainement entier a ete valide : connexion, ajout de photos, affichage des candidats (avec galerie et indicateur de correspondance visuelle), puis annonce de qualite marketplace, modifiable, verifiee visuellement par un humain.
- Mise en production. Le code est servi dans un conteneur (un environnement logiciel isole et reproductible). Le code est d'abord compile par Node, puis les fichiers obtenus sont servis par nginx, un serveur web leger et rapide. La verification de bout en bout cote serveur passe les six controles prevus.

> Chiffres pour la presentation : React version 19, huit composants d'interface, deux modes d'utilisation (un objet et mise en vente en rafale), tri des questions par entropie de Shannon multipliee par la couverture et la priorite semantique, quatre principes de psychologie de la decision (Zeigarnik, Hick, ancrage, IKEA). Capture d'ecran a montrer : les trois etapes du parcours, l'annonce finale modifiable, et le tableau de bord du mode demenagement. C'est la partie la plus demonstrative visuellement.

---

## 5. Regard critique : etat de l'art comparé a notre realisation

### Ce qui est solide

- Une application a page unique moderne et typee (React 19, Vite, TypeScript strict), avec des composants reutilises sans aucune duplication entre les deux modes : le mode en rafale s'appuie sur les memes briques que le parcours guide.
- La boucle avec humain dans le circuit et l'annonce modifiable apportent a la fois confiance et rattrapage des erreurs du modele.
- Une experience reflechie : guidage des prises de vue selon le type d'objet, indicateur de correspondance visuelle, desambiguisation en un clic guidee par l'entropie, et progression toujours visible.
- Un veritable mode rafale, avec file persistante et traitement en arriere-plan, pour le cas concret du demenagement.

### Limites assumees

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

Le frontend React transforme la chaine de traitement en un vrai produit : un parcours guide en trois etapes ou la photo est obligatoire, ou l'intelligence artificielle propose mais ou l'humain valide et modifie (effet IKEA), avec une desambiguisation en un clic choisie par entropie, et un mode rafale pour le demenagement. Des principes de psychologie de la decision (Hick, Zeigarnik, ancrage) y sont appliques pour maximiser le passage a l'acte de mise en vente.
