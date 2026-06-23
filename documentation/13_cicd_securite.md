# 13 — CI/CD & sécurité

> À chaque modification du code : **re-tester et re-construire automatiquement**. Et protéger
> l'application : secrets, authentification, validation des entrées utilisateur.

---

## 1. La technologie : qu'est-ce que c'est ?

### Pour comprendre (à partir de zéro)
- **CI (Intégration Continue)** : à chaque `push`, un robot (**GitHub Actions**) rejoue **lint,
  tests, audit de sécurité, build** → on sait *immédiatement* si quelque chose casse.
- **CD (Livraison Continue)** : construire et **publier les images** Docker prêtes à déployer
  (ici sur **GHCR**, le registre d'images de GitHub), **versionnées**.
- **Sécurité applicative** : empêcher les fuites de secrets, authentifier les accès, valider les
  entrées (fichiers uploadés), scanner les dépendances vulnérables.

### Pour l'expert
- **Shift-left** : faire les contrôles de sécurité **tôt** (au commit), pas après la prod.
  Combiner **SAST** (analyse du code), **SCA** (audit des dépendances), détection de secrets,
  scan d'images.
- **Versionnage semver** des images : `:latest` sur `main`, `:0.1.0` / `:0.1` / `:0` sur un tag
  `v*` → `docker pull` reproductible.

---

## 2. État de l'art

- **Bonnes pratiques GitHub Actions** : **permissions minimales** par job, **concurrence** (annuler
  les runs obsolètes), épingler les actions à un **SHA** (anti chaîne d'approvisionnement, cf.
  incident *tj-actions* 2025), **OIDC** plutôt que secrets statiques, **signer les images**
  (Cosign), **auditer les dépendances** (Trivy/Snyk).
- **Secrets** : jamais dans le code ; coffres, injection au runtime.

---

## 3. Notre implémentation (précisément ce qu'on a fait)

### CI (`.github/workflows/ci.yml`) — 4 jobs, déclenchés sur push + PR `main`
| Job | Rôle exact |
|---|---|
| **lint** | `ruff check` + `ruff format --check` (dont les **règles sécurité `S`** = bandit) |
| **test** | `pytest` + couverture (326 tests) — **`needs: lint`** (ne gaspille pas de minutes si le lint échoue) |
| **security** | **`pip-audit`** : scan CVE des dépendances ; CVE ignorées **explicitement justifiées** (diskcache, sans fix publié) |
| **docker-build** | construit les **4 images** (matrix) **sans push** (`push: false`) → vérifie qu'elles bâtissent sur PR |

Détails : **permissions `contents: read`** (moindre privilège), **`concurrency` cancel-in-progress**
(économie de minutes), **cache GHA** pour ne pas re-télécharger torch CPU à chaque build, `actions/
checkout` **bumpé en `@v5`** (C32.3, supprime le warning Node 20).

### CD (`.github/workflows/ghcr.yml`)
Build + **push vers GHCR** ; `:latest` sur `main`, **tags semver** sur `v*.*.*` ; permission
`packages: write` ; contrôle de concurrence. Une matrix garantit que les **4 images** sont
poussées (régression attrapée par `test_github_workflows.py`).

### Sécurité applicative
- **Zéro secret dans le code** (R2) : tout en `.env` gitignoré ; `.env.example` = gabarits ;
  `secrets.yaml` k8s gitignoré (gabarit committé).
- **Authentification JWT HS256** (`src/auth/`) + **bcrypt** (pas de passlib, incompatible
  bcrypt 5.0) ; endpoints métier protégés par `Depends(get_current_user)`.
- **Uploads durcis** (`src/api/uploads.py`) : whitelist de types (jpeg/png/webp/heic), taille max
  10 Mo, **garde anti-path-traversal** stricte (image_id = hex32 + extension whitelistée).
- **URLs capability** (uuid4 non devinable) pour servir les photos sans exposer le stockage.
- **Planchers de version** sur les dépendances (suite à l'audit pip-audit).

---

## 4. Résultats (mesurés)

- **CI verte 7/7** sur `main` (lint, 326 tests, pip-audit, 4 builds Docker — avec `checkout@v5`).
- **CD opérationnel** : images poussées sur GHCR avec versions semver.
- **Audit sécurité du dépôt** (réalisé) : **0 secret** et **0 fichier sensible** dans **tout**
  l'historique git ; seuls des placeholders dans `.env.example`.
- Tests sécurité : `test_auth.py`, `test_photo_upload.py` (anti-traversal), `test_github_workflows.py`.

> 📊 **Chiffres slide** : « CI 4 jobs (lint/tests/pip-audit/build) verte », « images GHCR semver »,
> « **0 secret dans tout l'historique** », « JWT + anti-path-traversal + capability-URL ». 📸
> **Capture** : l'onglet **Actions** (coches vertes) + la page **Packages** (images GHCR).

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Shift-left réel** : lint sécurité (`ruff S`) + **SCA (`pip-audit`)** + build, à chaque push.
- ✅ **CD versionné** vers GHCR (semver) + permissions minimales + concurrence + cache.
- ✅ **Secrets hors du code** (vérifié sur tout l'historique) + **JWT/bcrypt** + **uploads durcis**.
- ✅ Contrôles **testés** (auth, upload, contrats workflows).

**Limites assumées (vs état de l'art le plus strict) :**
- **Actions épinglées à des tags majeurs** (`@v5`), pas à un **SHA** → durcissement supply-chain
  restant (backlog).
- **Pas de signature d'images** (Cosign) ni de **scan de vulnérabilités d'images** (Trivy/Grype).
- **Pas d'OIDC** (pas de déploiement cloud ici) ; **JWT = stub démo** (1 utilisateur, pas de
  signup), documenté.

---

## 6. Références
- Wiz — *CI/CD pipeline security best practices* — https://www.wiz.io/academy/application-security/ci-cd-security-best-practices
- OWASP — *CI/CD Security Cheat Sheet* — https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/CI_CD_Security_Cheat_Sheet.md
- GitHub Docs — *Actions secure use reference* — https://docs.github.com/en/actions/reference/security/secure-use
- OWASP — *Path Traversal* — https://owasp.org/www-community/attacks/Path_Traversal

---

### En une phrase (pour la défense)
*« À chaque push, la CI rejoue lint, 326 tests, audit des dépendances (pip-audit) et build des 4
images ; la CD publie des images versionnées (semver) sur GHCR. Côté sécurité : zéro secret dans
tout l'historique (vérifié), JWT + bcrypt, et des uploads durcis (anti-path-traversal, URLs
capability). »*
