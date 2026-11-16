"""
packages/rules/ (Logforge's hand-written rules and content pack) is loaded at
startup through the same fixture gate as the vendored SigmaHQ content.
Before, only tests read it, so none of these detections ran in a deployment.
"""

from pathlib import Path

import pytest
import yaml

from mitre_default_loader import MitreDefaultLoader, packaged_rules_dir

REPO_RULES = Path(__file__).resolve().parents[1] / "packages" / "rules"


@pytest.fixture
def loader():
    instance = MitreDefaultLoader.__new__(MitreDefaultLoader)  # no database
    instance._condition_evaluator = None
    return instance


def test_rules_dir_resolves_to_the_checkout(monkeypatch):
    monkeypatch.delenv("PACKAGED_RULES_DIR", raising=False)
    assert packaged_rules_dir() == REPO_RULES


def test_standalone_rules_and_content_pack_are_loaded(loader):
    rows, awaiting = loader._load_packaged_rules()
    ids = {row["id"] for row in rows}

    standalone = len(list(REPO_RULES.glob("*.yml"))) - 1  # minus content_pack.yml
    pack = len(yaml.safe_load((REPO_RULES / "content_pack.yml").read_text())["rules"])
    assert len(rows) + len(awaiting) == standalone + pack

    assert "logforge_cd001-lsass-memory-dump" in ids  # a standalone file
    assert "logforge_dp001-host-network-enumeration" in ids  # a content-pack rule
    for row in rows:
        assert row["id"].startswith("logforge_")
        assert row["customer_id"] == "default"
        assert row["mitre_techniques"], row["id"]
        assert '"fixtures"' in row["rule_content"], row["id"]


def test_aggregation_rule_is_reported_not_loaded(loader):
    rows, awaiting = loader._load_packaged_rules()
    assert "logforge_bf001-brute-force-login" not in {r["id"] for r in rows}
    assert any(a.startswith("brute_force_detection.yml: aggregation rule") for a in awaiting)


def test_hand_written_fixtures_are_verified(loader, tmp_path, monkeypatch):
    rule = yaml.safe_load((REPO_RULES / "data_exfiltration.yml").read_text())
    good, reason = loader._packaged_rule_to_row(rule, "data_exfiltration.yml")
    assert good is not None, reason

    rule["fixtures"]["true_negative"] = dict(rule["fixtures"]["true_positive"])
    bad, reason = loader._packaged_rule_to_row(rule, "data_exfiltration.yml")
    assert bad is None and reason == "true_negative fixture matches"


def test_rules_dir_is_configurable(loader, tmp_path, monkeypatch):
    (tmp_path / "only.yml").write_text((REPO_RULES / "credential_dumping_lsass.yml").read_text())
    monkeypatch.setenv("PACKAGED_RULES_DIR", str(tmp_path))

    rows, awaiting = loader._load_packaged_rules()
    assert [r["id"] for r in rows] == ["logforge_cd001-lsass-memory-dump"]
    assert awaiting == []
