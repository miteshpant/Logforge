"""
Sigma rules see caller-supplied fields that ingestion keeps under `attrs`.

JSON ingestion stores fields that aren't part of the log model (event_type,
result, command_line, process_name, ...) under `attrs`. The evaluator only
read top-level keys, so a rule like the brute-force rule
(`event_type: authentication, result: failed`) matched 0 of 12 failed-login
events sent through /v1/ingest/logs/batch. Field lookup now falls back to
`attrs`; a top-level value still wins.
"""

import asyncio

import pytest

from sigma_engine import CountCondition, SigmaConditionEvaluator, SigmaRuleEngine

EVENT = {
    "service": "sshd",
    "msg": "Failed password for admin from 203.0.113.66",
    "src_ip": "203.0.113.66",
    "attrs": {"event_type": "authentication", "result": "failed", "command_line": "sshd -D"},
}
SELECTION = {"event_type": "authentication", "result": ["failed", "denied"]}


def test_selection_matches_fields_found_only_in_attrs():
    matched, _ = SigmaConditionEvaluator().evaluate_selection(EVENT, SELECTION)
    assert matched


def test_modifiers_work_on_attrs_fields():
    matched, _ = SigmaConditionEvaluator().evaluate_selection(
        EVENT, {"command_line|contains": "sshd"})
    assert matched


def test_top_level_value_wins_over_attrs():
    event = dict(EVENT, result="success")  # top-level says success
    matched, _ = SigmaConditionEvaluator().evaluate_selection(event, SELECTION)
    assert not matched


def test_missing_field_still_does_not_match():
    matched, _ = SigmaConditionEvaluator().evaluate_selection(
        EVENT, {"process_name": "mimikatz.exe"})
    assert not matched


def test_dotted_names_still_resolve_nested_fields():
    value = SigmaConditionEvaluator()._get_field_value(EVENT, "attrs.event_type")
    assert value == "authentication"


@pytest.fixture
def engine(monkeypatch):
    instance = SigmaRuleEngine.__new__(SigmaRuleEngine)  # no subscription service / DB
    instance.condition_evaluator = SigmaConditionEvaluator()
    return instance


def test_count_rule_groups_by_a_field_in_attrs(engine):
    """Group-by keys are resolved like selection fields, so `by user` works
    when `user` is only in attrs."""
    events = [
        dict(EVENT, attrs=dict(EVENT["attrs"], target_user=f"u{i % 2}"))
        for i in range(6)
    ]
    rule = {
        "id": "r1",
        "title": "spray",
        "level": "high",
        "status": "stable",
        "detection": {"selection": SELECTION, "condition": "count(selection) >= 3 by target_user"},
        "tags": ["attack.t1110"],
    }
    condition = CountCondition.parse(rule["detection"]["condition"])
    matches = asyncio.run(engine._evaluate_count_rule(
        [(e, e) for e in events], rule, condition, "tenant-1"))

    groups = sorted(m.matched_fields["_count"]["group_key"] for m in matches)
    assert groups == ["target_user=u0", "target_user=u1"]


# --- The precompiled fast path must agree with the evaluator above. ---------

from services.high_performance_rule_matcher import HighPerformanceRuleMatcher  # noqa: E402

FAST_RULE = {
    "id": "fast-1",
    "title": "Failed auth",
    "level": "medium",
    "status": "stable",
    "detection": {"selection": SELECTION, "condition": "selection"},
    "tags": ["attack.t1110"],
}


def test_fast_matcher_matches_fields_found_only_in_attrs():
    matcher = HighPerformanceRuleMatcher()
    matcher.compile_rules([FAST_RULE], "tenant-1")

    matches = matcher.match_log(EVENT, "tenant-1")
    assert [rule.rule_id for rule, _ in matches] == ["fast-1"]


def test_fast_matcher_top_level_value_wins():
    matcher = HighPerformanceRuleMatcher()
    matcher.compile_rules([FAST_RULE], "tenant-1")

    assert matcher.match_log(dict(EVENT, result="success"), "tenant-1") == []


def test_fast_count_path_groups_and_matches_attrs_fields(engine):
    from services.high_performance_rule_matcher import HighPerformanceRuleMatcher as HP

    engine.hp_matcher = HP()
    count_rule = dict(FAST_RULE, id="fast-count",
                      detection={"selection": SELECTION, "condition": "count(selection) >= 3 by src_ip"})
    engine.hp_matcher.compile_rules([count_rule], "tenant-1")
    rule = engine.hp_matcher.get_count_rules("tenant-1")[0]

    matches = asyncio.run(engine._evaluate_count_rule_fast([EVENT] * 3, rule, "tenant-1"))
    assert len(matches) == 1
