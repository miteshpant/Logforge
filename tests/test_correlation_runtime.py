"""
Correlation in the live detection path (sigma_engine.evaluate_logs_against_rules).

* count() rules are windowed across ingest batches. They were evaluated per
  batch only, so 10 failed logins arriving in two batches of 5 never fired.
* Correlation rules (Sigma correlation format) consume base-rule matches.
  A base rule with `generate: false` feeds correlations without alerting on
  its own.
* An invalid correlation rule is skipped without breaking the others.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from correlation import CorrelationStore
from dao.security_dao import SecurityDAO
from sigma_engine import SigmaConditionEvaluator, SigmaRuleEngine

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    instance = SigmaRuleEngine.__new__(SigmaRuleEngine)  # no subscription service / DB
    instance.condition_evaluator = SigmaConditionEvaluator()
    instance.correlation_store = CorrelationStore()
    instance.published = []

    async def capture(match):
        instance.published.append(match)

    instance._publish_detection_event = capture
    return instance


def rule_dict(rid, detection=None, **extra):
    data = {"id": rid, "title": rid, "description": "", "severity": "high", "status": "active",
            "enabled": True, "attack_techniques": ["T1110"], "tags": ["attack.t1110"],
            "kill_chain_phases": ["credential-access"], "logsource": {},
            "detection": detection or {}, "references": [], "falsepositives": []}
    data.update(extra)
    return data


FAILED_SEL = {"selection": {"event_type": "authentication", "result": "failed"}}
BRUTE = rule_dict("bf", {**FAILED_SEL, "timeframe": "5m", "condition": "count(selection) >= 10 by src_ip"})


def logs(n, start_s=0, ip="203.0.113.9", **fields):
    return [{"ts": (T0 + timedelta(seconds=start_s + i)).isoformat(), "src_ip": ip,
             "attrs": {"event_type": "authentication", "result": "failed", **fields}} for i in range(n)]


def run(engine, batch, rules):
    return asyncio.run(engine.evaluate_logs_against_rules(batch, rules, "t1", logs_normalized=True))


def test_count_rules_are_windowed_across_batches(engine):
    assert run(engine, logs(5), [BRUTE]) == []
    matches = run(engine, logs(5, start_s=30), [BRUTE])

    assert [m.rule_id for m in matches] == ["bf"]
    assert matches[0].matched_fields["_correlation"]["value"] == 10
    assert matches[0].matched_fields["_correlation"]["group"] == {"src_ip": "203.0.113.9"}
    assert [m.rule_id for m in engine.published] == ["bf"]


def test_count_rule_window_comes_from_timeframe(engine):
    run(engine, logs(5), [BRUTE])
    assert run(engine, logs(5, start_s=600), [BRUTE]) == []  # 10 minutes later: outside 5m


SPRAY = rule_dict("spray", tags=["attack.t1110.003"], attack_techniques=["T1110.003"], correlation={
    "type": "value_count", "rules": ["auth_failed"], "group-by": ["src_ip"], "timespan": "10m",
    "condition": {"field": "target_user", "gte": 5}})
AUTH_FAILED = rule_dict("base-1", {**FAILED_SEL, "condition": "selection"}, name="auth_failed", generate=False)


def test_correlation_rules_consume_base_rule_matches(engine):
    batch = [e for i in range(5) for e in logs(1, start_s=i, target_user=f"user{i}")]
    matches = run(engine, batch, [AUTH_FAILED, SPRAY])

    assert [m.rule_id for m in matches] == ["spray"]
    assert matches[0].attack_techniques == ["T1110.003"]
    assert matches[0].matched_fields["_correlation"]["type"] == "value_count"


def test_generate_false_base_rules_do_not_alert_on_their_own(engine):
    run(engine, logs(3), [AUTH_FAILED, SPRAY])
    assert engine.published == []


def test_base_rules_without_generate_false_still_alert(engine):
    alerting_base = dict(AUTH_FAILED, generate=True)
    matches = run(engine, logs(2), [alerting_base, SPRAY])
    assert [m.rule_id for m in matches] == ["base-1", "base-1"]


def test_an_invalid_correlation_rule_is_skipped(engine):
    broken = rule_dict("broken", correlation={"type": "nonsense", "rules": ["x"], "timespan": "5m"})
    batch = [e for i in range(5) for e in logs(1, start_s=i, target_user=f"user{i}")]
    matches = run(engine, batch, [broken, AUTH_FAILED, SPRAY])
    assert [m.rule_id for m in matches] == ["spray"]


def test_dao_passes_correlation_fields_through():
    import json

    class _DB:
        async def fetch_all(self, sql, params=None):
            content = {"correlation": {"type": "event_count"}, "name": "auth_failed", "generate": False,
                       "detection": {}}
            return [{"id": "r", "name": "R", "description": "", "severity": "high", "is_enabled": 1,
                     "created_by": "system", "created_at": T0, "updated_at": T0, "customer_id": "default",
                     "mitre_techniques": [], "rule_content": json.dumps(content)}]

    dao = SecurityDAO.__new__(SecurityDAO)
    dao.db = _DB()
    rule = asyncio.run(dao.get_sigma_rules("default", enabled=True))[0]
    assert rule["correlation"] == {"type": "event_count"}
    assert rule["name"] == "auth_failed"
    assert rule["generate"] is False
