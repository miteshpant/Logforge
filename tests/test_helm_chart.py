"""
Helm chart (Phase 12): render deploy/helm/logforge and check what it
deploys. Needs `helm` on PATH (or HELM=/path/to/helm); CI installs it.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

CHART = Path(__file__).resolve().parents[1] / "deploy" / "helm" / "logforge"
HELM = os.getenv("HELM") or shutil.which("helm")

pytestmark = pytest.mark.skipif(not HELM and not os.getenv("LOGFORGE_REQUIRE_HELM"), reason="helm not installed")


def render(*sets, ok=True):
    args = [HELM, "template", "t", str(CHART)]
    for s in sets:
        args += ["--set", s]
    out = subprocess.run(args, capture_output=True, text=True)
    if not ok:
        assert out.returncode != 0
        return out.stderr
    assert out.returncode == 0, out.stderr
    docs = [d for d in yaml.safe_load_all(out.stdout) if d]
    return {(d["kind"], d["metadata"]["name"]): d for d in docs}


def test_lint():
    out = subprocess.run([HELM, "lint", str(CHART), "--set", "secrets.jwtSecret=x"], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_default_install():
    objs = render("secrets.jwtSecret=x")
    kinds = sorted({k for k, _ in objs})
    assert kinds == ["ConfigMap", "CronJob", "Deployment", "Job", "PodDisruptionBudget", "Secret", "Service"]
    api = objs[("Deployment", "t-logforge-api")]
    assert api["spec"]["replicas"] == 2
    assert api["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == 0
    container = api["spec"]["template"]["spec"]["containers"][0]
    assert "--reload" not in container["command"]  # the image's dev default
    assert container["readinessProbe"]["httpGet"]["path"] == "/health"
    secret_refs = {e["name"] for e in container["env"] if "valueFrom" in e}
    assert {"JWT_SECRET", "CLICKHOUSE_PASSWORD", "LOGFORGE_S3_SECRET_KEY"} <= secret_refs
    config = objs[("ConfigMap", "t-logforge-config")]["data"]
    assert config["LOGFORGE_RETENTION_JOB"] == "off"  # the CronJob runs it, once per cluster
    assert objs[("PodDisruptionBudget", "t-logforge-api")]["spec"]["minAvailable"] == 1
    retention = objs[("CronJob", "t-logforge-retention")]["spec"]
    assert retention["concurrencyPolicy"] == "Forbid"
    pod = retention["jobTemplate"]["spec"]["template"]["spec"]
    assert pod["containers"][0]["command"] == ["python", "-m", "tier_manager", "run"]
    backup = objs[("CronJob", "t-logforge-backup")]["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    assert backup["containers"][0]["command"] == ["python", "-m", "backup", "create"]
    job = objs[("Job", "t-logforge-migrations")]
    assert job["metadata"]["annotations"]["helm.sh/hook"] == "pre-install,pre-upgrade"
    env = {e["name"]: e.get("value") for e in job["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["REPLICATED_ENGINES"] == "true" and env["CLICKHOUSE_CLUSTER"] == "logforge"


def test_the_jwt_secret_is_required_and_an_existing_secret_can_replace_the_charts():
    assert "secrets.jwtSecret is required" in render(ok=False)
    objs = render("secrets.existingSecret=mine")
    assert not any(k == "Secret" for k, _ in objs)
    api = objs[("Deployment", "t-logforge-api")]["spec"]["template"]["spec"]["containers"][0]
    refs = {e["valueFrom"]["secretKeyRef"]["name"] for e in api["env"] if "valueFrom" in e}
    assert refs == {"mine"}


def test_autoscaling_and_ingress():
    objs = render("secrets.jwtSecret=x", "api.autoscaling.enabled=true", "ingress.enabled=true", "backup.enabled=false")
    assert "replicas" not in objs[("Deployment", "t-logforge-api")]["spec"]
    assert objs[("HorizontalPodAutoscaler", "t-logforge-api")]["spec"]["minReplicas"] == 2
    paths = [p["path"] for p in objs[("Ingress", "t-logforge")]["spec"]["rules"][0]["http"]["paths"]]
    assert paths == ["/v1", "/health", "/"]
    assert ("CronJob", "t-logforge-backup") not in objs
