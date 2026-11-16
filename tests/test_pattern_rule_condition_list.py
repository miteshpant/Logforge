"""
Regression tests: pattern rules in the documented `conditions` format fire.

The alerts API accepts `rule_type: "pattern"` with
`conditions: [{field, operator, value}]` (+ optional `filters`), but
PatternMatcher only understood `pattern_type`/`pattern(s)` or nested AND/OR,
so these rules were stored, evaluated, and silently never matched.
"""

import json

import pytest

from events.management.matchers.pattern_matcher import PatternMatcher


def _rule(conditions, filters=None):
    return {
        "id": "r1", "rule_type": "pattern",
        "condition_config": json.dumps({"conditions": conditions, "filters": filters or []}),
    }


LOGS = [
    {"service": "payments", "level": "error", "msg": "card network error"},
    {"service": "checkout", "level": "info", "msg": "payment declined for order 7"},
]


@pytest.mark.asyncio
async def test_condition_list_rule_matches():
    rule = _rule([{"field": "msg", "operator": "contains", "value": "declined"}],
                 [{"field": "service", "operator": "eq", "value": "checkout"}])
    assert await PatternMatcher().matches(LOGS, rule) is True


@pytest.mark.asyncio
async def test_all_clauses_must_hold_for_the_same_log():
    # One log has level=error, another has service=checkout -- not the same log.
    rule = _rule([{"field": "level", "operator": "eq", "value": "error"}],
                 [{"field": "service", "operator": "eq", "value": "checkout"}])
    assert await PatternMatcher().matches(LOGS, rule) is False


@pytest.mark.asyncio
async def test_case_insensitive_and_uppercase_operator():
    rule = _rule([{"field": "level", "operator": "EQ", "value": "ERROR"}])
    assert await PatternMatcher().matches(LOGS, rule) is True


@pytest.mark.asyncio
async def test_no_match_returns_false():
    rule = _rule([{"field": "msg", "operator": "contains", "value": "panic"}])
    assert await PatternMatcher().matches(LOGS, rule) is False


@pytest.mark.asyncio
async def test_legacy_keyword_pattern_still_works():
    rule = {"id": "r2", "rule_type": "pattern", "condition_config": json.dumps(
        {"pattern_type": "keyword", "patterns": ["declined"], "fields": ["msg"]})}
    assert await PatternMatcher().matches(LOGS, rule) is True
