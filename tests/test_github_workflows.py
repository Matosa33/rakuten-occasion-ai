"""Tests contrat des workflows GitHub Actions (Cycle 15.2, D-033).

Sans padding : chaque test attrape une régression réelle.
- YAML well-formed (parsing yaml)
- Triggers attendus (push/pull_request main, push tag v*.*.*)
- Jobs structurellement présents
- Cohérence : permissions, concurrence, matrix
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
GHCR = ROOT / ".github" / "workflows" / "ghcr.yml"


def _load(p: Path) -> dict:
    assert p.exists(), f"manquant : {p}"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# ci.yml — lint + tests + brain-structure
# ─────────────────────────────────────────────────────────────────────────────


def test_ci_workflow_parse_yaml():
    """Le YAML CI doit être bien-formé (sinon GH Actions refuse le workflow)."""
    wf = _load(CI)
    assert wf["name"] == "CI"
    # `on:` est un mot-clé YAML → PyYAML le parse comme bool True. On accepte
    # les deux orthographes pour rester robuste (cf. ghcr.yml même note).
    assert "on" in wf or True in wf, "trigger `on:` manquant"


def test_ci_triggers_push_pr_main():
    """CI doit tourner sur push + pull_request main (sinon les PR ne sont pas vérifiées)."""
    wf = _load(CI)
    triggers = wf.get("on") or wf.get(True)
    assert "push" in triggers, "trigger push manquant"
    assert "pull_request" in triggers, "trigger pull_request manquant"
    assert "main" in triggers["push"]["branches"]
    assert "main" in triggers["pull_request"]["branches"]


def test_ci_jobs_lint_test_brain_present():
    """Les jobs canoniques sont déclarés (régression si on en supprime un).
    security + docker-build ajoutés en C15.3 (D-034). Le job brain-structure a
    été retiré en C19 (BRAIN sorti du repo public)."""
    jobs = _load(CI)["jobs"]
    assert "lint" in jobs, "job `lint` manquant"
    assert "test" in jobs, "job `test` manquant"
    assert "security" in jobs, "job `security` (pip-audit, D-034) manquant"
    assert "docker-build" in jobs, "job `docker-build` (D-034) manquant"


def test_ci_security_job_pip_audit_avec_ignore_justifie():
    """Le job security lance pip-audit ; les CVE ignorées doivent être listées
    EXPLICITEMENT (pas de --ignore-vuln générique non documenté)."""
    raw = CI.read_text(encoding="utf-8")
    assert "pip-audit" in raw, "pip-audit absent du CI"
    # La seule CVE ignorée autorisée = diskcache (sans fix publié, D-034).
    assert "--ignore-vuln CVE-2025-69872" in raw, (
        "CVE diskcache doit être ignorée explicitement avec justification"
    )


def test_ci_docker_build_les_4_images_sans_push():
    """docker-build vérifie les 4 Dockerfiles sur PR SANS pousser (push: false)."""
    jobs = _load(CI)["jobs"]
    db = jobs["docker-build"]
    matrix = db["strategy"]["matrix"]["include"]
    images = {m["image"] for m in matrix}
    assert images == {"api", "frontend", "airflow", "mlflow"}, (
        f"docker-build doit couvrir les 4 images, vu : {images}"
    )
    raw = CI.read_text(encoding="utf-8")
    assert "push: false" in raw, "docker-build ne doit JAMAIS pousser (CI PR)"


def test_ci_test_depends_on_lint():
    """`test` doit attendre `lint` — évite de gaspiller des minutes Actions sur
    du code non-formaté qui aurait de toute façon échoué au lint."""
    jobs = _load(CI)["jobs"]
    needs = jobs["test"].get("needs")
    assert needs == "lint" or "lint" in (needs or []), "test doit `needs: lint`"


def test_ci_test_installe_extras_attendus():
    """Régression : si on ajoute un extra (15.1 ajoute `monitoring` pour
    push_metrics + bcrypt), il faut le rajouter au CI sinon les tests cassent."""
    raw = CI.read_text(encoding="utf-8")
    # Vérifie que les extras critiques sont installés en CI.
    for extra in ("dev", "data", "ml", "api", "monitoring"):
        assert (
            f"[{extra}" in raw or f",{extra}" in raw or f"{extra}," in raw or f"{extra}]" in raw
        ), f"extra `{extra}` doit être installé dans le CI test job"


def test_ci_concurrence_cancel_pour_economiser_minutes():
    """Sans `cancel-in-progress`, chaque push pendant un build occupe un runner
    pendant 5 min de plus. Le quota GH Actions n'est pas illimité."""
    wf = _load(CI)
    conc = wf.get("concurrency", {})
    assert conc.get("cancel-in-progress") is True, "CI doit annuler les runs précédents"


# ─────────────────────────────────────────────────────────────────────────────
# ghcr.yml — build + push 4 images au GitHub Container Registry
# ─────────────────────────────────────────────────────────────────────────────


def test_ghcr_workflow_parse_yaml():
    """GHCR YAML bien-formé."""
    wf = _load(GHCR)
    assert wf["name"].startswith("Build"), "name doit commencer par 'Build'"


def test_ghcr_triggers_main_et_tags_semver():
    """Triggers : push main → :latest, push tag v*.*.* → semver. Si on retire
    un trigger, des releases ne sont plus publiées silencieusement."""
    wf = _load(GHCR)
    triggers = wf.get("on") or wf.get(True)
    assert "push" in triggers, "trigger push manquant"
    push = triggers["push"]
    assert "main" in push.get("branches", []), "push main → :latest manquant"
    tags = push.get("tags", [])
    assert any("v*" in t for t in tags), f"push tag semver manquant (vu {tags})"


def test_ghcr_permissions_packages_write():
    """Sans `packages: write`, le job ne peut pas push à ghcr.io."""
    wf = _load(GHCR)
    perms = wf.get("permissions", {})
    assert perms.get("packages") == "write", (
        f"permissions.packages doit être 'write' (vu {perms.get('packages')!r})"
    )


def test_ghcr_matrix_les_4_images_attendues():
    """Régression : un nouvel image ajoutée dans le compose doit être pushée
    aussi. La matrix est la source de vérité."""
    wf = _load(GHCR)
    jobs = wf["jobs"]["build-and-push"]
    matrix = jobs["strategy"]["matrix"]["include"]
    images = {m["image"] for m in matrix}
    assert images == {"api", "frontend", "airflow", "mlflow"}, (
        f"matrix doit avoir exactement les 4 images, vu : {images}"
    )


def test_ghcr_chaque_matrix_pointe_sur_un_dockerfile_existant():
    """Régression : si on rename infra/docker/Dockerfile.X, la matrix doit suivre."""
    wf = _load(GHCR)
    matrix = wf["jobs"]["build-and-push"]["strategy"]["matrix"]["include"]
    for entry in matrix:
        df = ROOT / entry["dockerfile"]
        assert df.exists(), f"Dockerfile {df} référencé par matrix mais absent du repo"


def test_ghcr_cache_gha_active_pour_eviter_re_download_torch():
    """Sans cache-from/cache-to, chaque build re-télécharge torch CPU (~1 Go)
    → CI prend 10-15 min au lieu de 2-3. Le quota cache GHA est 10 Go gratuit."""
    raw = GHCR.read_text(encoding="utf-8")
    assert "cache-from: type=gha" in raw, "cache-from gha manquant (build cold à chaque push)"
    assert "cache-to: type=gha" in raw, "cache-to gha manquant"


def test_ghcr_metadata_action_tags_semver():
    """Régression : si on retire un pattern semver de metadata-action, les
    releases v0.1.0 ne tagueront plus :0.1 / :0 → docker pull cassé."""
    raw = GHCR.read_text(encoding="utf-8")
    assert "type=semver,pattern={{version}}" in raw, "tag :0.1.0 manquant"
    assert "type=semver,pattern={{major}}.{{minor}}" in raw, "tag :0.1 manquant"
    assert "type=raw,value=latest,enable={{is_default_branch}}" in raw, ":latest sur main manquant"
