"""
Grouping on the evaluation corpus (Phase 2 acceptance: "grouping reduces
items needing triage by a measured percentage").

eval_harness.grouping_report replays every scenario (in one shared
timeline, so unrelated scenarios overlap in time) through the shipped
rules, then routes the alerts with the production grouping policy. Items
needing triage = cases; without grouping, every alert is an item.
"""

import eval_harness


def test_grouping_report_on_the_corpus():
    report = eval_harness.grouping_report()
    assert report["alerts"] > report["cases"] > 0
    assert report["reduction"] == round(1 - report["cases"] / report["alerts"], 3)
    assert report["reduction"] >= 0.5
    # Each scenario is one intrusion; its alerts land in one case, except
    # lateral movement, which by nature spans two hosts (linking source and
    # destination hosts is not done by entity grouping).
    spread = {sid: n for sid, n in report["cases_per_scenario"].items() if n > 1}
    assert spread == {"psexec-lateral-movement": 2}, f"scenarios split across cases: {spread}"
    # Scenarios that reuse a host (the corpus has a handful of workstations)
    # share its case; that is intended: same host, same 24 h, one case.
