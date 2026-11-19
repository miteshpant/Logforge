"""
Detection evaluation harness (Phase 0): measures what the shipped rules
detect on labelled attack scenarios and how often they fire on benign
traffic, and gates CI on regressions against a committed baseline.

These tests pin the harness's own logic with small hand-made rules.
test_detection_eval_baseline.py runs it on the real rules and corpus.
"""

import pytest

from eval_harness import compare, evaluate

RULE_MIMIKATZ = {
    "id": "r-mimikatz", "techniques": ["T1003.001"],
    "detection": {"selection": {"process_name|endswith": "mimikatz.exe"}, "condition": "selection"},
}
RULE_BRUTE = {
    "id": "r-brute", "techniques": ["T1110"],
    "detection": {"selection": {"event_type": "authentication", "result": "failed"},
                  "condition": "count(selection) >= 3 by src_ip"},
}
RULE_NOISY = {
    "id": "r-noisy", "techniques": ["T1059"],
    "detection": {"selection": {"process_name|endswith": "powershell.exe"}, "condition": "selection"},
}

FAIL = {"event_type": "authentication", "result": "failed", "src_ip": "203.0.113.5"}
SCENARIOS = [
    {"id": "creds-dump", "techniques": ["T1003.001"],
     "events": [{"process_name": "C:\\tools\\mimikatz.exe"}]},
    {"id": "spray", "techniques": ["T1110"], "events": [FAIL, FAIL, FAIL]},
    {"id": "missed", "techniques": ["T1021"], "events": [{"process_name": "psexec.exe"}]},
]
BENIGN = [
    {"process_name": "C:\\Windows\\explorer.exe"},
    {"process_name": "C:\\Windows\\System32\\powershell.exe", "command_line": "Get-Date"},
    FAIL, FAIL,  # two failures: below the brute-force threshold
]


@pytest.fixture
def report():
    return evaluate([RULE_MIMIKATZ, RULE_BRUTE, RULE_NOISY], SCENARIOS, BENIGN)


def test_scenarios_record_which_expected_techniques_were_detected(report):
    assert report["scenarios"]["creds-dump"] == {
        "expected": ["T1003.001"], "detected": ["T1003.001"], "missing": [], "rules": ["r-mimikatz"]}
    assert report["scenarios"]["spray"]["detected"] == ["T1110"]
    assert report["scenarios"]["missed"]["missing"] == ["T1021"]


def test_rules_count_true_and_false_positives(report):
    assert report["rules"]["r-mimikatz"] == {"true_positives": 1, "false_positives": 0}
    assert report["rules"]["r-noisy"] == {"true_positives": 0, "false_positives": 1}
    # count rules fire per batch: below threshold on benign, at threshold in "spray"
    assert report["rules"]["r-brute"] == {"true_positives": 1, "false_positives": 0}


def test_summary_reports_rates(report):
    summary = report["summary"]
    assert summary["benign_events"] == 4
    assert summary["false_positive_alerts"] == 1
    assert summary["false_positives_per_1000"] == 250.0
    assert summary["scenarios_detected"] == 2
    assert summary["scenarios_total"] == 3


def test_compare_with_itself_finds_no_regressions(report):
    assert compare(report, report) == []


def test_compare_flags_a_scenario_that_stopped_being_detected(report):
    current = evaluate([RULE_BRUTE, RULE_NOISY], SCENARIOS, BENIGN)  # mimikatz rule gone
    problems = compare(current, report)
    assert "scenario creds-dump no longer detects T1003.001" in problems


def test_compare_flags_new_false_positives(report):
    noisy_benign = BENIGN + [{"process_name": "C:\\Windows\\System32\\powershell.exe"}]
    current = evaluate([RULE_MIMIKATZ, RULE_BRUTE, RULE_NOISY], SCENARIOS, noisy_benign)
    problems = compare(current, report)
    assert "rule r-noisy false positives rose from 1 to 2" in problems


def test_new_detections_and_fewer_false_positives_are_not_regressions(report):
    quieter_benign = [e for e in BENIGN if "powershell" not in e.get("process_name", "")]
    psexec_rule = {"id": "r-psexec", "techniques": ["T1021"],
                   "detection": {"selection": {"process_name": "psexec.exe"}, "condition": "selection"}}
    better = evaluate([RULE_MIMIKATZ, RULE_BRUTE, RULE_NOISY, psexec_rule], SCENARIOS, quieter_benign)

    assert better["scenarios"]["missed"]["detected"] == ["T1021"]  # newly detected
    assert compare(better, report) == []


def test_removing_a_rule_must_be_recorded_in_the_baseline(report):
    """Intentional removals are fine, but only once the baseline is updated."""
    without_noisy = evaluate([RULE_MIMIKATZ, RULE_BRUTE], SCENARIOS, BENIGN)
    assert compare(without_noisy, report) == ["rule r-noisy is no longer in the rule set"]
    assert compare(without_noisy, without_noisy) == []


def test_compare_flags_a_rule_that_stopped_detecting_even_if_another_rule_covers_it(report):
    """Redundant coverage must not hide a broken rule."""
    backup = dict(RULE_MIMIKATZ, id="r-mimikatz-2")
    baseline = evaluate([RULE_MIMIKATZ, backup, RULE_BRUTE, RULE_NOISY], SCENARIOS, BENIGN)
    broken = dict(RULE_MIMIKATZ, detection={"selection": {"process_name|endswith": "nothing.exe"},
                                            "condition": "selection"})
    current = evaluate([broken, backup, RULE_BRUTE, RULE_NOISY], SCENARIOS, BENIGN)

    assert current["scenarios"]["creds-dump"]["detected"] == ["T1003.001"]  # still covered
    assert compare(current, baseline) == ["rule r-mimikatz true positives fell from 1 to 0"]


def test_compare_flags_a_rule_that_disappeared(report):
    current = evaluate([RULE_BRUTE, RULE_NOISY], SCENARIOS, BENIGN)
    assert "rule r-mimikatz is no longer in the rule set" in compare(current, report)


# --- Phase 1: correlation rules and timed scenarios ----------------------------

OK = {"event_type": "authentication", "result": "success", "src_ip": "203.0.113.5"}
BASE_FAILED = {"id": "b-failed", "name": "auth_failed", "generate": False, "techniques": ["T1110"],
               "detection": {"selection": {"event_type": "authentication", "result": "failed"},
                             "condition": "selection"}}
BASE_OK = {"id": "b-ok", "name": "auth_ok", "generate": False, "techniques": ["T1078"],
           "detection": {"selection": {"event_type": "authentication", "result": "success"},
                         "condition": "selection"}}
RULE_CHAIN = {"id": "r-chain", "techniques": ["T1110", "T1078"], "detection": {},
              "correlation": {"type": "temporal_ordered", "rules": ["auth_failed", "auth_ok"],
                              "group-by": ["src_ip"], "timespan": "10m"}}
CHAIN_RULES = [BASE_FAILED, BASE_OK, RULE_CHAIN]


def test_correlation_rules_are_evaluated_on_scenarios():
    scenario = {"id": "takeover", "techniques": ["T1078"], "events": [FAIL, FAIL, OK]}
    report = evaluate(CHAIN_RULES, [scenario], [OK])
    assert report["scenarios"]["takeover"]["rules"] == ["r-chain"]
    assert report["scenarios"]["takeover"]["detected"] == ["T1078"]


def test_building_blocks_are_not_scored_as_alerting_rules():
    report = evaluate(CHAIN_RULES, [{"id": "s", "techniques": ["T1110"], "events": [FAIL]}], [OK, FAIL])
    assert set(report["rules"]) == {"r-chain"}
    assert report["summary"]["false_positive_alerts"] == 0
    assert report["summary"]["rules"] == 1


def test_scenario_timing_is_respected():
    slow = {"id": "slow", "techniques": ["T1110"],
            "events": [{"repeat": 3, "every": "10m", "event": FAIL}]}  # 3 failures over 20 minutes
    fast = {"id": "fast", "techniques": ["T1110"], "events": [{"repeat": 3, "event": FAIL}]}
    brute = dict(RULE_BRUTE, detection=dict(RULE_BRUTE["detection"], timeframe="5m"))
    report = evaluate([brute], [slow, fast], [])
    assert report["scenarios"]["slow"]["detected"] == []
    assert report["scenarios"]["fast"]["detected"] == ["T1110"]
