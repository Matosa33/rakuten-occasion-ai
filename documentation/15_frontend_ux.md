# 15 — Frontend & UX vendeur

> L'interface que le vendeur utilise vraiment : photographier, valider, publier. C'est là que
> tout le pipeline ML devient un **produit utilisable** — et où l'UX décide si le vendeur va
> jusqu'au bout.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre
Un **frontend** est l'application visible dans le navigateur. Le nôtre est une **SPA** (Single
Page Application) en **React** : une seule page qui se met à jour dynamiquement (pas de
rechargement à chaque clic). Le vendeur y suit un parcours en 3 étapes : **Décrire** (photos +
état) → **Identifier** (choisir le bon candidat) → **Vendre** (prix + annonce éditable).

### Pour l'expert
- **React 19 + Vite 6 + Tailwind v4 + Framer Motion**, TypeScript strict.
- État d'authentification via **`useSyncExternalStore`** branché sur le token `localStorage` →
  re-render automatique au login/logout/401 (pas de prop drilling).
- **Human-in-the-loop** : l'IA propose, le vendeur **valide et édite** — jamais de publication
  automatique. C'est un choix produit (confiance) **et** une bonne pratique ML (l'humain
  rattrape les erreurs du modèle).

---

## 2. État de l'art

- **Architecture par composants** réutilisables, état minimal, rendu déclaratif.
- **UX des apps ML** : *progressive disclosure* (montrer l'avancement), **validation humaine**
  des sorties incertaines, et ne jamais présenter une prédiction comme une vérité absolue.
- **Principes de psychologie de la décision** appliqués à la conversion :
  - **Loi de Hick** : moins de choix = décision plus rapide (limiter les options).
  - **Effet d'ancrage** : un prix de référence affiché oriente la perception.
  - **Effet IKEA** : ce qu'on a soi-même édité, on y tient (et on le publie).
  - **Effet Zeigarnik** : une barre de progression « tâche inachevée » pousse à finir.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### Stack & structure (`frontend/src/`, ~1 950 lignes)
- `App.tsx` — l'orchestrateur d'UI : gère les étapes, les 2 modes, l'appel des endpoints.
- `api.ts` — client typé (Bearer JWT, gestion du 401, types partagés avec le backend).
- `auth.ts` — store d'auth externe (localStorage + `useSyncExternalStore`).

### Les 8 composants
| Composant | Rôle |
|---|---|
| `PhotoUploader` | glisser-déposer + **`capture=environment`** (appareil photo mobile), max 5 photos, préviews ; **bloque l'identification sans ≥ 1 photo** (D-035) |
| `ConditionChecklist` | type d'objet + **guidage de prises de vue** + checklist d'état (« bābā ») |
| `CandidatePicker` | les candidats avec **galerie des vues catalogue** + **badge de correspondance visuelle** (VLM) |
| `MarketplaceListing` | l'annonce finale : breadcrumb catégorie + galerie photos + prix + badge état + **caractéristiques structurées** + description **éditable** |
| `PhotoLightbox` | visionneuse plein écran (clavier + flèches) |
| `StepBar` | barre de progression 3 étapes (**Zeigarnik**) |
| `LoginPage` | connexion (JWT) |
| `BatchMode` | le mode **📦 Déménagement** (mitraillage) |

### L'Akinator côté client (`facets.ts`)
Quand plusieurs candidats sont proches, on choisit **côté front** la question la plus utile à
poser, par **entropie de Shannon normalisée × couverture × priorité sémantique** :
- l'**entropie** mesure à quel point une facette (couleur, capacité…) **sépare** les candidats ;
- la **couverture** = combien de candidats portent cette facette ;
- la **priorité** privilégie le **type de produit** (×2,0) puis la capacité (×1,2) — car
  distinguer « téléphone vs coque » est bien plus utile que la marque.
→ On pose **une seule** question, la plus discriminante, comme un arbre de décision. (La logique
existe aussi côté backend `select_next_observation` ; le front la rejoue sur les candidats
affichés.)

### Les 2 modes (`App.tsx` + `batch.ts` + `BatchMode.tsx`)
- **🎯 Un objet** : parcours guidé pas à pas.
- **📦 Déménagement** : « mitrailler » N objets à la chaîne — file en **localStorage**,
  analyses **séquentielles en arrière-plan**, tableau de bord des annonces prêtes (cf. rapport
  *Batch*/D-037). L'humain n'attend jamais l'analyse.

### Neuro-marketing appliqué (choix design assumés)
- **Zeigarnik** → `StepBar` (la tâche inachevée pousse à finir).
- **Loi de Hick** → on limite à 3 candidats mis en avant.
- **Ancrage** → la carte prix affiche un prix de référence + fourchette.
- **Effet IKEA** → l'annonce est **éditable** (le vendeur se l'approprie → la publie).

---

## 4. Résultats (mesurés)

- **Build de production** ~343 kB (gzip ~109 kB) — `npm run build` + `tsc --noEmit` (TS strict, 0 erreur).
- **Parcours complet fonctionnel** : login → upload → candidats (galerie + badge VLM) → annonce
  marketplace-grade éditable (validé visuellement par l'humain sur l'annonce iPad Pro).
- **Servi en conteneur** (build statique → nginx) ; smoke E2E backend 6/6.

> 📊 **Chiffres slide** : « React 19, 8 composants, 2 modes (unitaire + mitraillage) »,
> « Akinator côté client par entropie de Shannon × couverture × priorité », « 4 principes
> neuro-marketing (Zeigarnik/Hick/Ancrage/IKEA) ». 📸 **Capture** : les 3 étapes du flow +
> l'annonce finale éditable + le tableau de bord du mode Déménagement. **C'est le plus
> démonstratif visuellement.**

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **SPA moderne typée** (React 19/Vite/TS strict), composants réutilisés (zéro duplication
  entre les 2 modes : le batch réutilise `CandidatePicker` + `MarketplaceListing`).
- ✅ **Human-in-the-loop** + annonce éditable → confiance + rattrapage des erreurs modèle.
- ✅ **UX réfléchie** : guidage photo, badge de correspondance visuelle, désambiguation à 1 clic
  par entropie, progression visible.
- ✅ **Mode mitraillage** réel (file persistante, traitement async) pour le cas déménagement.

**Limites assumées :**
- **Pas de tests E2E frontend** (Playwright/Cypress) : on teste le backend de bout en bout
  (smoke) mais pas les interactions UI automatiquement — axe d'amélioration.
- **Logique de facette dupliquée** front/back (entropie) : pratique pour réagir sans aller-retour
  serveur, mais c'est une duplication à surveiller (deux sources de vérité possibles).
- **Accessibilité (a11y) non auditée** (contrastes, navigation clavier complète, ARIA) — à faire
  pour un vrai produit.
- **localStorage** pour la file batch : simple, mais limité (quota navigateur, pas de sync
  multi-appareils).

---

## 6. Références
- React — *Thinking in React / components* — https://react.dev/learn/thinking-in-react
- React — *useSyncExternalStore* — https://react.dev/reference/react/useSyncExternalStore
- NN/g (Nielsen Norman Group) — *Progressive disclosure* — https://www.nngroup.com/articles/progressive-disclosure/
- Laws of UX — *Hick's Law, Zeigarnik effect* — https://lawsofux.com/

---

### En une phrase (pour la défense)
*« Le frontend React transforme le pipeline en produit : un parcours guidé en 3 étapes où la
photo est obligatoire, l'IA propose mais l'humain valide et édite (effet IKEA), avec une
désambiguation à un clic choisie par entropie, et un mode "mitraillage" pour le déménagement.
On a appliqué des principes de psychologie de la décision (Hick, Zeigarnik, ancrage) pour
maximiser la conversion. »*
