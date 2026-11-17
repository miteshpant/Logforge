"""
Sigma correlation rules: parsing and validation (Phase 1).

Correlation rules use the Sigma correlation format
(https://sigmahq.io/sigma-specification/specification/sigma-correlation-rules-specification.html):
a rule with a `correlation:` block that references base rules by name and
aggregates their matches per group over a time span.

Supported types: event_count, value_count, temporal, temporal_ordered, and a
Logforge extension value_sum. Conditions may only be thresholds that can be
decided while events stream in (gt / gte / eq): "fewer than N" can only be
known when a window closes, which a streaming engine can't evaluate.
"""

from datetime import timedelta

import pytest

from correlation import CorrelationRule, CorrelationRuleError, parse_timespan


def _rule(**correlation):
    base = {"type": "event_count", "rules": ["failed_login"], "group-by": ["src_ip"],
            "timespan": "5m", "condition": {"gte": 10}}
    base.update(correlation)
    return {"id": "c1", "title": "Brute force", "level": "high",
            "tags": ["attack.credential_access", "attack.t1110"], "correlation": base}


def test_parses_an_event_count_rule():
    rule = CorrelationRule.from_dict(_rule())
    assert rule.id == "c1"
    assert rule.type == "event_count"
    assert rule.rules == ["failed_login"]
    assert rule.group_by == ["src_ip"]
    assert rule.timespan == timedelta(minutes=5)
    assert (rule.operator, rule.threshold, rule.field) == ("gte", 10, None)
    assert rule.techniques == ["T1110"]


def test_value_count_needs_a_field():
    rule = CorrelationRule.from_dict(_rule(type="value_count", condition={"field": "user", "gte": 8}))
    assert (rule.field, rule.threshold) == ("user", 8)
    with pytest.raises(CorrelationRuleError, match="value_count needs condition.field"):
        CorrelationRule.from_dict(_rule(type="value_count", condition={"gte": 8}))


def test_value_sum_is_supported():
    rule = CorrelationRule.from_dict(_rule(type="value_sum", condition={"field": "bytes_out", "gt": 500_000_000}))
    assert (rule.type, rule.field, rule.operator) == ("value_sum", "bytes_out", "gt")


def test_temporal_rules_need_two_or_more_base_rules_and_no_condition():
    rule = CorrelationRule.from_dict(_rule(type="temporal_ordered", rules=["a", "b", "c"], condition=None))
    assert rule.rules == ["a", "b", "c"]
    with pytest.raises(CorrelationRuleError, match="at least two"):
        CorrelationRule.from_dict(_rule(type="temporal", rules=["a"], condition=None))


@pytest.mark.parametrize("bad, message", [
    ({"type": "nonsense"}, "unsupported correlation type"),
    ({"rules": []}, "needs base rules"),
    ({"timespan": "soon"}, "invalid timespan"),
    ({"condition": {"lt": 3}}, "only gt, gte or eq"),
    ({"condition": {"gte": -1}}, "positive"),
])
def test_invalid_rules_are_rejected_with_a_reason(bad, message):
    with pytest.raises(CorrelationRuleError, match=message):
        CorrelationRule.from_dict(_rule(**bad))


def test_group_by_is_optional_and_accepts_a_single_field():
    assert CorrelationRule.from_dict(_rule(**{"group-by": None})).group_by == []
    assert CorrelationRule.from_dict(_rule(**{"group-by": "user"})).group_by == ["user"]


@pytest.mark.parametrize("text, expected", [
    ("30s", timedelta(seconds=30)), ("5m", timedelta(minutes=5)),
    ("2h", timedelta(hours=2)), ("1d", timedelta(days=1)),
])
def test_parse_timespan(text, expected):
    assert parse_timespan(text) == expected


def test_threshold_check():
    rule = CorrelationRule.from_dict(_rule(condition={"gt": 3}))
    assert not rule.threshold_met(3) and rule.threshold_met(4)
    eq = CorrelationRule.from_dict(_rule(condition={"eq": 3}))
    assert eq.threshold_met(3) and not eq.threshold_met(4)
