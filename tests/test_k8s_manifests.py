"""Tests de contrat des manifests Kubernetes (Cycle 13.5, D-028).

Statiques : YAML parse + invariants (HPA bornes, ingress hosts, image policy).
Build et `kubectl apply` validés live au commit C13.5 sur cluster kind.
"""

from __future__ import annotations

from pathlib import Path

import yaml

K8S = Path(__file__).resolve().parents[1] / "infra" / "k8s"


def _docs(path: Path) -> list[dict]:
    """Charge un YAML multi-document (--- séparateurs)."""
    assert path.exists(), f"manquant : {path}"
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _all_manifests() -> list[dict]:
    """Renvoie tous les objets des manifests (sauf gabarit secret + kustomization)."""
    objs: list[dict] = []
    for f in sorted(K8S.glob("[0-9][0-9]-*.yaml")):
        objs.extend(_docs(f))
    return objs


def test_yaml_parsent_tous():
    """Tous les manifests numérotés + kustomization + kind-cluster + secret gabarit parsent."""
    for name in (
        "00-namespace.yaml",
        "01-configmap.yaml",
        "02-secrets.example.yaml",
        "10-minio.yaml",
        "20-postgres-mlflow.yaml",
        "30-mlflow-server.yaml",
        "40-api.yaml",
        "50-frontend.yaml",
        "60-ingress.yaml",
        "kustomization.yaml",
        "kind-cluster.yaml",
    ):
        _docs(K8S / name)  # lève si YAML invalide


def test_kustomization_reference_tous_les_manifests():
    """Aucun manifest oublié dans la kustomization (sinon `kubectl apply -k` skip)."""
    k = _docs(K8S / "kustomization.yaml")[0]
    resources = set(k.get("resources", []))
    expected = {
        "00-namespace.yaml",
        "01-configmap.yaml",
        "secrets.yaml",  # créé depuis le gabarit
        "10-minio.yaml",
        "20-postgres-mlflow.yaml",
        "30-mlflow-server.yaml",
        "40-api.yaml",
        "50-frontend.yaml",
        "60-ingress.yaml",
    }
    missing = expected - resources
    assert not missing, f"manifests absents de kustomization.yaml : {missing}"


def test_hpa_api_bornes_et_cpu_70():
    """HPA présent sur l'API : min 2 / max 5 / cible CPU 70% (D-028)."""
    hpas = [o for o in _docs(K8S / "40-api.yaml") if o.get("kind") == "HorizontalPodAutoscaler"]
    assert len(hpas) == 1, "1 HPA attendu sur l'API"
    spec = hpas[0]["spec"]
    assert spec["minReplicas"] == 2 and spec["maxReplicas"] == 5
    cpu = next(
        (m for m in spec["metrics"] if m["type"] == "Resource" and m["resource"]["name"] == "cpu"),
        None,
    )
    assert cpu is not None, "métrique CPU attendue"
    assert cpu["resource"]["target"]["averageUtilization"] == 70


def test_ingress_route_les_3_hotes_attendus():
    """Ingress mappe `rakuten.localhost`, `api.localhost`, `mlflow.localhost` (D-028)."""
    ing = [o for o in _docs(K8S / "60-ingress.yaml") if o.get("kind") == "Ingress"][0]
    hosts = {rule["host"] for rule in ing["spec"]["rules"]}
    assert hosts == {"rakuten.localhost", "api.localhost", "mlflow.localhost"}
    assert ing["spec"]["ingressClassName"] == "nginx"


def test_images_locales_imagepullpolicy_ifnotpresent():
    """Les 3 images `rakuten/*:dev` sont locales (kind load) — pullPolicy IfNotPresent
    obligatoire, sinon K8s tente un `docker pull` et échoue."""
    pods_specs = []
    for o in _all_manifests():
        spec = o.get("spec", {}).get("template", {}).get("spec")
        if spec:
            pods_specs.append((o["metadata"]["name"], spec))
    for name, spec in pods_specs:
        for c in spec.get("containers", []):
            if str(c.get("image", "")).startswith("rakuten/"):
                assert c.get("imagePullPolicy") == "IfNotPresent", (
                    f"{name} container {c['name']} image locale → imagePullPolicy=IfNotPresent requis"
                )


def test_namespace_rakuten_partout():
    """Tous les objets non-cluster-scoped vivent dans le namespace `rakuten`."""
    for o in _all_manifests():
        kind = o.get("kind")
        # Namespace + Cluster-scoped (HPA est namespacé, Ingress aussi).
        if kind == "Namespace":
            assert o["metadata"]["name"] == "rakuten"
            continue
        ns = o.get("metadata", {}).get("namespace")
        assert ns == "rakuten", f"{kind}/{o['metadata']['name']} pas dans namespace `rakuten`"
