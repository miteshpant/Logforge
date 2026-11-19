"""
CI gate: the shipped rules must not regress on the detection corpus.

Runs tests/eval/detection/eval_harness.py over the real rule set (vendored
SigmaHQ + packages/rules, built by the startup loader) and compares with the
committed baseline.json. A scenario technique that stops being detected, or a
rule that fires on more benign events than before, fails the build.

Improved results are allowed; to record them run:

    python tests/eval/detection/eval_harness.py --update-baseline
"""

import eval_harness


def test_baseline_exists():
    assert eval_harness.load_baseline() is not None, (
        "tests/eval/detection/baseline.json is missing; run "
        "python tests/eval/detection/eval_harness.py --update-baseline")


def test_no_detection_regressions_against_baseline():
    report = eval_harness.run()
    problems = eval_harness.compare(report, eval_harness.load_baseline() or {})
    assert problems == [], "\n".join(problems)


def test_every_scenario_is_labelled_with_techniques():
    for scenario in eval_harness.load_scenarios():
        assert scenario.get("techniques"), f"{scenario['id']} has no ATT&CK techniques"
        assert scenario.get("events"), f"{scenario['id']} has no events"
