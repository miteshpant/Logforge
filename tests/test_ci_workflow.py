"""
Tests for ENH-011 -- the CI workflow must exist and stay coherent.

`.github/workflows/` was empty, so nothing prevented a broken or vulnerable
change from merging. Every guard added in ENH-001..ENH-033 is enforced by tests
that nothing was running.

These tests are cheap insurance: they catch a workflow that has been deleted,
renamed, or edited into something that no longer runs the suite. They do not
attempt to simulate GitHub Actions.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def workflow():
    assert WORKFLOW.exists(), (
        "CI workflow is missing. Without it nothing gates a merge (ENH-011)."
    )
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_is_valid_yaml(workflow):
    assert isinstance(workflow, dict)


def test_runs_on_pull_requests(workflow):
    """A gate that does not run on PRs gates nothing."""
    # PyYAML parses the bare key `on:` as the boolean True.
    triggers = workflow.get("on") or workflow.get(True)
    assert triggers is not None, "Workflow has no triggers"
    assert "pull_request" in triggers


def test_expected_jobs_are_present(workflow):
    jobs = set(workflow["jobs"])
    assert {"api-tests", "api-lint", "security-scan", "ui-build"} <= jobs


def test_api_tests_job_runs_pytest(workflow):
    steps = workflow["jobs"]["api-tests"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "pytest" in commands


def test_api_test_job_is_not_allowed_to_fail_silently(workflow):
    """
    The test job must NOT be `continue-on-error`. A green tick on a failing
    suite is worse than no CI at all, because it manufactures confidence.
    """
    job = workflow["jobs"]["api-tests"]
    assert job.get("continue-on-error") is not True

    for step in job["steps"]:
        if "pytest" in step.get("run", ""):
            assert step.get("continue-on-error") is not True, (
                "The pytest step must be blocking."
            )


def test_blocking_lint_rules_are_enforced(workflow):
    """
    The correctness lint gate (F821/F811) must stay blocking -- it caught three
    live crashes when introduced.
    """
    steps = workflow["jobs"]["api-lint"]["steps"]
    blocking = [
        s for s in steps
        if "ruff" in s.get("run", "") and s.get("continue-on-error") is not True
    ]
    assert blocking, "There must be at least one blocking ruff step."

    joined = " ".join(s["run"] for s in blocking)
    assert "F821" in joined
    assert "F811" in joined


def test_security_scanning_is_present(workflow):
    steps = workflow["jobs"]["security-scan"]["steps"]
    text = " ".join(
        str(step.get("run", "")) + str(step.get("uses", "")) for step in steps
    )
    assert "pip-audit" in text
    assert "bandit" in text
    assert "gitleaks" in text


def test_jobs_have_timeouts(workflow):
    """An untimed job can hang and burn CI minutes indefinitely."""
    for name, job in workflow["jobs"].items():
        assert "timeout-minutes" in job, f"Job '{name}' has no timeout"


def test_concurrency_cancels_superseded_runs(workflow):
    assert workflow.get("concurrency", {}).get("cancel-in-progress") is True


def test_permissions_are_least_privilege(workflow):
    assert workflow.get("permissions", {}).get("contents") == "read"
