"""
Phase 1 detection content: aggregation and sequence rules, gap rules, and
the noisy sudo rule.

Acceptance (docs/PLATFORM_ROADMAP.md, Phase 1): the brute-force rule plus at
least 10 new aggregation/sequence rules pass the fixture gate and the
evaluation. Measured with the detection eval harness on the real rule set:
each new rule detects its labelled scenario and raises no alert on the
benign corpus; every scenario is detected as all of its techniques; and the
shipped rules raise no false positives on the benign corpus (pe001 used to
alert on every routine sudo).
"""

from pathlib import Path

import pytest

import eval_harness

NEW_SEQUENCE_RULES = [
    "logforge_lf-c-password-spray",
    "logforge_lf-c-brute-force-then-success",
    "logforge_lf-c-web-scanning",
    "logforge_lf-c-discovery-burst",
    "logforge_lf-c-sudo-failure-burst",
    "logforge_lf-c-archive-then-cloud-upload",
    "logforge_lf-c-outbound-volume",
    "logforge_lf-c-lateral-logon-fanout",
    "logforge_lf-c-discovery-then-credential-dump",
    "logforge_lf-c-account-lockout-burst",
    "logforge_lf-c-mass-file-encryption",
    "logforge_lf-c-mfa-fatigue",
]
GAP_TECHNIQUES = {"certutil-download": "T1105", "encoded-powershell-download": "T1105",
                  "linux-reverse-shell": "T1059.004", "psexec-lateral-movement": "T1569.002",
                  "domain-discovery": "T1069.002"}


@pytest.fixture(scope="module")
def rules():
    return eval_harness.shipped_rules()


@pytest.fixture(scope="module")
def report(rules):
    from benign import benign_events

    return eval_harness.evaluate(rules, eval_harness.load_scenarios(), benign_events())


def _is_sequence(rule):
    return bool(rule.get("correlation")) or "count(" in str(rule["detection"].get("condition", ""))


def test_at_least_ten_new_aggregation_or_sequence_rules_ship(rules):
    by_id = {r["id"]: r for r in rules}
    missing = [rid for rid in NEW_SEQUENCE_RULES if rid not in by_id]
    assert missing == [], f"not loaded (see the loader's awaiting list): {missing}"
    assert all(_is_sequence(by_id[rid]) for rid in NEW_SEQUENCE_RULES)
    assert len(NEW_SEQUENCE_RULES) >= 10


@pytest.mark.parametrize("rule_id", NEW_SEQUENCE_RULES + ["logforge_bf001-brute-force-login"])
def test_each_sequence_rule_detects_a_scenario_without_false_positives(report, rule_id):
    assert report["rules"][rule_id] == {"true_positives": report["rules"][rule_id]["true_positives"],
                                        "false_positives": 0}
    assert report["rules"][rule_id]["true_positives"] >= 1


def test_every_scenario_is_detected_as_all_its_techniques(report):
    incomplete = {sid: s["missing"] for sid, s in report["scenarios"].items() if s["missing"]}
    assert incomplete == {}


@pytest.mark.parametrize("scenario, technique", GAP_TECHNIQUES.items())
def test_detection_gaps_are_closed(report, scenario, technique):
    assert technique in report["scenarios"][scenario]["detected"]


def test_the_shipped_rules_raise_no_alerts_on_the_benign_corpus(report):
    noisy = {rid: s["false_positives"] for rid, s in report["rules"].items() if s["false_positives"]}
    assert noisy == {}


def test_a_rule_file_can_hold_several_rules(tmp_path, monkeypatch):
    """Base rules and the correlations built on them live together in one
    multi-document YAML file."""
    import mitre_default_loader

    (tmp_path / "correlations").mkdir()
    (tmp_path / "correlations" / "pair.yml").write_text(Path(eval_harness.REPO, "packages", "rules",
                                            "correlations", "credential_access.yml").read_text())
    monkeypatch.setattr(mitre_default_loader, "packaged_rules_dir", lambda: tmp_path)
    loader = mitre_default_loader.MitreDefaultLoader.__new__(mitre_default_loader.MitreDefaultLoader)
    loader._condition_evaluator = None
    rows, awaiting = loader._load_packaged_rules()
    assert awaiting == []
    assert {"logforge_lf-c-password-spray", "logforge_lf-c-brute-force-then-success"} <= {r["id"] for r in rows}
