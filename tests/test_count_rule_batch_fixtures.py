"""
Aggregation (`count()`) rules are verified with batch fixtures.

A threshold rule cannot be proven with one event, so the loader rejected every
count rule ("awaiting content"), including packages/rules/brute_force_detection.yml.
Batch fixtures are lists of events: the positive batch must trip the threshold
for at least one group, the negative batch must not, and neither may the benign
corpus. Verification uses the engine's own CountCondition parser and selection
evaluator, i.e. the same logic that evaluates count rules at runtime.
"""

from pathlib import Path

import pytest
import yaml

from mitre_default_loader import MitreDefaultLoader

REPO_RULES = Path(__file__).resolve().parents[1] / "packages" / "rules"

FAILED = {"event_type": "authentication", "result": "failed", "src_ip": "203.0.113.9"}
OK = {"event_type": "authentication", "result": "success", "src_ip": "203.0.113.9"}


@pytest.fixture
def loader():
    instance = MitreDefaultLoader.__new__(MitreDefaultLoader)  # no database
    instance._condition_evaluator = None
    return instance


def _rule(condition="selection | count() >= 3 by src_ip", fixtures=None):
    rule = {
        "id": "t-count",
        "title": "Test count rule",
        "level": "high",
        "tags": ["attack.credential_access", "attack.t1110"],
        "detection": {
            "selection": {"event_type": "authentication", "result": "failed"},
            "condition": condition,
        },
    }
    if fixtures is not None:
        rule["fixtures"] = fixtures
    return rule


def _batches(positive, negative):
    return {"true_positive_batch": positive, "true_negative_batch": negative}


def test_count_rule_with_valid_batch_fixtures_loads(loader):
    rule = _rule(fixtures=_batches(
        [{"repeat": 3, "event": FAILED}],
        [{"repeat": 2, "event": FAILED}, {"repeat": 5, "event": OK}],
    ))
    row, reason = loader._packaged_rule_to_row(rule, "t.yml")

    assert row is not None, reason
    assert "true_positive_batch" in row["rule_content"]


def test_repeat_entries_expand_to_that_many_events(loader):
    events = loader._expand_batch([{"repeat": 3, "event": FAILED}, OK])
    assert events == [FAILED, FAILED, FAILED, OK]


def test_positive_batch_below_threshold_is_rejected(loader):
    rule = _rule(fixtures=_batches([{"repeat": 2, "event": FAILED}], [OK]))
    row, reason = loader._packaged_rule_to_row(rule, "t.yml")

    assert row is None
    assert reason == "true_positive_batch does not reach the threshold"


def test_negative_batch_that_fires_is_rejected(loader):
    rule = _rule(fixtures=_batches(
        [{"repeat": 3, "event": FAILED}], [{"repeat": 4, "event": FAILED}]))
    row, reason = loader._packaged_rule_to_row(rule, "t.yml")

    assert row is None
    assert reason == "true_negative_batch reaches the threshold"


def test_grouping_is_respected(loader):
    """Three failures spread over three IPs must not trip a per-IP threshold."""
    spread = [dict(FAILED, src_ip=f"198.51.100.{i}") for i in range(3)]
    rule = _rule(fixtures=_batches([{"repeat": 3, "event": FAILED}], spread))

    row, reason = loader._packaged_rule_to_row(rule, "t.yml")
    assert row is not None, reason


def test_count_rule_without_batch_fixtures_is_rejected(loader):
    row, reason = loader._packaged_rule_to_row(_rule(), "t.yml")

    assert row is None
    assert reason == "aggregation rule needs true_positive_batch and true_negative_batch fixtures"


def test_condition_the_engine_does_not_aggregate_is_refused(loader):
    """The runtime evaluates count rules on the `selection` block only; a gate
    that verified a richer condition would be verifying different logic."""
    rule = _rule(
        condition="selection and not filter | count() >= 3 by src_ip",
        fixtures=_batches([{"repeat": 3, "event": FAILED}], [OK]),
    )
    rule["detection"]["filter"] = {"src_ip": "10.0.0.1"}

    row, reason = loader._packaged_rule_to_row(rule, "t.yml")
    assert row is None
    assert reason == "count rules are evaluated on the 'selection' block only"


def test_shipped_brute_force_rule_now_loads(loader):
    rule = yaml.safe_load((REPO_RULES / "brute_force_detection.yml").read_text())
    row, reason = loader._packaged_rule_to_row(rule, "brute_force_detection.yml")

    assert row is not None, reason
    assert row["id"] == "logforge_bf001-brute-force-login"


def test_all_packaged_rules_load(loader):
    rows, awaiting = loader._load_packaged_rules()
    assert awaiting == []
    assert "logforge_bf001-brute-force-login" in {r["id"] for r in rows}


def test_standard_sigma_count_form_loads(loader):
    """`count(selection) >= N by field` (no pipe) is what the shipped rule uses."""
    rule = _rule(
        condition="count(selection) >= 3 by src_ip",
        fixtures=_batches([{"repeat": 3, "event": FAILED}], [{"repeat": 2, "event": FAILED}]),
    )
    row, reason = loader._packaged_rule_to_row(rule, "t.yml")
    assert row is not None, reason


def test_standard_form_counting_another_block_is_refused(loader):
    rule = _rule(
        condition="count(other) >= 3 by src_ip",
        fixtures=_batches([{"repeat": 3, "event": FAILED}], [OK]),
    )
    rule["detection"]["other"] = {"result": "failed"}
    row, reason = loader._packaged_rule_to_row(rule, "t.yml")

    assert row is None
    assert reason == "count rules are evaluated on the 'selection' block only"
