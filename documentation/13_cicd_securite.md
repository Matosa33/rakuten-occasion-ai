# 13 — CI/CD & sécurité

> À chaque modification du code, **re-tester et re-construire automatiquement** ; et protéger
> l'application (secrets, authentification, entrées utilisateur).

---

## 1. La technologie : qu'est-ce que c'est ?

- **CI (Intégration Continue)** : à chaque `push`, un robot (GitHub Actions) **rejoue les
  tests, le lint, l'audit de sécurité, le build** → on sait immédiatement si quelque chose
  casse.
- **CD (Livraison Continue)** : construire et **publier les images** Docker prêtes à déployer
  (ici sur **GHCR**, le registre d'images de GitHub), versionnées.
- **Sécurité applicative** : empêcher les fuites de secrets, authentifier les accès, valider
  les entrées (fichiers uploadés), scanner les dépendances vulnérables.

---

## 2. État de l'art

- **Shift-left** : faire les contrôles de sécurité **tôt** (pendant le dev), pas après la prod.
  Combiner SAST (analyse du code), SCA (audit des dépendances), détection de secrets, scan des
  images.
- **Bonnes pratiques GitHub Actions (2025-2026)** : épingler les actions à un **SHA** (pas un
  tag mutable), **permissions minimales** par job, **OIDC** plutôt que des secrets statiques,
  **secret scanning** + push protection, **signer les images** (Cosign), **auditer les
  dépendances** (dependency-review, Trivy, Snyk).
- **Secrets** : jamais dans le code ; coffres (Vault, Secrets Manager), injection au runtime.

---

## 3. Notre implémentation

**CI** (`.github/workflows/ci.yml`) — 4 jobs :
| Job | Rôle |
|---|---|
| **lint** | `ruff check` + `ruff format --check` (style + règles, dont **règles sécurité `S`**) |
| **test** | `pytest` + couverture (326 tests) |
| **security** | **`pip-audit`** : scan des dépendances pour les CVE connues |
| **docker-build** | construit les 4 images (vérifie qu'elles bâtissent) |

**CD** (`.github/workflows/ghcr.yml`) : build + **push vers GHCR** ; `:latest` sur `main`,
**tags semver** (`:0.1.0`, `:0.1`, `:0`) sur les tags `v*.*.*` ; contrôle de concurrence.

**Sécurité applicative** :
- **Zéro secret dans le code** (R2) : tout en `.env` gitignoré ; `.env.example` = gabarits.
- **Authentification JWT** (HS256) + **bcrypt** pour les mots de passe.
- **Uploads durcis** : whitelist de types, taille max, **garde anti-path-traversal** stricte.
- **URLs capability** (uuid4 non devinable) pour servir les photos sans exposer le stockage.
- **Planchers de version** sur les dépendances (suite à un audit pip-audit).

---

## 4. Résultats (mesurés)

- **CI verte** : les 4 jobs passent sur `main` (lint, 326 tests, pip-audit, build des 4 images).
- **CD opérationnel** : les images sont poussées sur GHCR avec versions semver.
- **Audit de sécurité du dépôt** (fait pendant ce travail) : **0 secret** et **0 fichier
  sensible** (`.env`, clés) dans **tout** l'historique git ; seuls des placeholders dans
  `.env.example`.
- Tests sécurité : `test_auth.py`, `test_photo_upload.py` (anti-traversal), `test_github_workflows.py`.

> 📊 **Chiffres slide** : « CI 4 jobs (lint/tests/pip-audit/build) verte », « images GHCR
> semver », « 0 secret dans tout l'historique », « JWT + anti-path-traversal ». 📸 **Capture** :
> l'onglet **Actions** de GitHub (coches vertes) + la page **Packages** (images GHCR).

---

## 5. Critique (état de l'art vs nous)

**Solide :**
- ✅ **Shift-left réel** : lint sécurité (`ruff S`) + **SCA (`pip-audit`)** + build, à chaque push.
- ✅ **CD versionné** vers GHCR (semver).
- ✅ **Secrets hors du code** (vérifié sur tout l'historique) + **JWT/bcrypt** + **uploads
  durcis** (anti-traversal, capability URLs).
- ✅ Contrôles **testés** (auth, upload, workflows).

**Limites assumées (vs état de l'art le plus strict) :**
- **Actions non épinglées à un SHA** (on utilise des tags majeurs à jour, ex. `@v5`) → le
  durcissement ultime est l'épinglage au SHA (risque chaîne d'approvisionnement, cf. incident
  *tj-actions* 2025) — non fait, c'est un cran de sécurité supplémentaire.
- **Pas de signature d'images** (Cosign) ni de **scan de vulnérabilités d'images** (Trivy/Grype)
  → ajout naturel.
- **Pas d'OIDC** (pas de déploiement cloud ici) ; **JWT = stub démo** (1 utilisateur, pas de
  signup), documenté.
- ~~Avertissement Node 20~~ **résolu** : `actions/checkout` bumpé en `@v5` (Cycle 32.3).

---

## 6. Références
- Wiz — *CI/CD pipeline security best practices* — https://www.wiz.io/academy/application-security/ci-cd-security-best-practices
- OWASP — *CI/CD Security Cheat Sheet* — https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/CI_CD_Security_Cheat_Sheet.md
- GitHub Docs — *Actions secure use reference* — https://docs.github.com/en/actions/reference/security/secure-use
- Arctiq — *Top 10 GitHub Actions security pitfalls* — https://arctiq.com/blog/top-10-github-actions-security-pitfalls-the-ultimate-guide-to-bulletproof-workflows

---

### En une phrase (pour la défense)
*« À chaque push, la CI rejoue lint, 326 tests, audit des dépendances (pip-audit) et build des
images ; la CD publie des images versionnées sur GHCR. Côté sécurité : zéro secret dans tout
l'historique (vérifié), JWT + bcrypt, et des uploads durcis (anti-path-traversal, URLs
capability). »*
