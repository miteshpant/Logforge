"""
Tuning in the live detection path and in backtests (Phase 1).

The engine asks for the tenant's tuning (cached) and skips alerts that an
exclusion matches or a throttle holds back. Suppressed matches still feed
correlations. Backtests apply the same tuning and report what was suppressed.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from correlation import CorrelationStore
from detection_tuning import Throttler, TuningSet
from sigma_engine import SigmaConditionEvaluator, SigmaRuleEngine

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def records(*items):
    return [dict(id=f"x{i}", reason="test", **item) for i, item in enumerate(items)]


@pytest.fixture
def make_engine():
    def make(tuning_records):
        engine = SigmaRuleEngine.__new__(SigmaRuleEngine)
        engine.condition_evaluator = SigmaConditionEvaluator()
        engine.correlation_store = CorrelationStore()
        engine.throttler = Throttler()
        engine.published = []

        async def capture(match):
            engine.published.append(match)

        async def tuning_for(tenant):
            return TuningSet.from_records(tuning_records)

        engine._publish_detection_event = capture
        engine.tuning_provider = tuning_for
        return engine
    return make


LOGIN = {"id": "login-fail", "title": "Failed login", "severity": "medium", "attack_techniques": ["T1110"],
         "detection": {"selection": {"result": "failed"}, "condition": "selection"}, "name": "auth_failed"}
SPRAY = {"id": "spray", "title": "Spray", "severity": "high", "attack_techniques": ["T1110.003"],
         "correlation": {"type": "value_count", "rules": ["auth_failed"], "group-by": ["src_ip"],
                         "timespan": "10m", "condition": {"field": "user", "gte": 3}}}


def log(i, ip="10.0.5.5", user=None):
    return {"ts": (T0 + timedelta(seconds=i)).isoformat(), "src_ip": ip,
            "attrs": {"result": "failed", "user": user or f"u{i}"}}


def run(engine, logs, rules):
    return asyncio.run(engine.evaluate_logs_against_rules(logs, rules, "t1", logs_normalized=True))


def test_excluded_alerts_are_not_raised(make_engine):
    engine = make_engine(records({"rule_id": "login-fail", "kind": "exclusion",
                                  "spec": {"conditions": {"src_ip": "10.0.5.5"}}}))
    matches = run(engine, [log(0), log(1, ip="45.155.205.10")], [LOGIN])
    assert [m.log_entry["src_ip"] for m in matches] == ["45.155.205.10"]
    assert len(engine.published) == 1


def test_suppressed_matches_still_feed_correlations(make_engine):
    engine = make_engine(records({"rule_id": "login-fail", "kind": "exclusion",
                                  "spec": {"conditions": {"src_ip": "10.0.5.5"}}}))
    matches = run(engine, [log(i) for i in range(3)], [LOGIN, SPRAY])
    assert [m.rule_id for m in matches] == ["spray"]


def test_correlation_alerts_can_be_excluded_and_throttled(make_engine):
    engine = make_engine(records({"rule_id": "spray", "kind": "throttle",
                                  "spec": {"window": "1h", "group_by": ["src_ip"]}},
                                 {"rule_id": "login-fail", "kind": "exclusion",
                                  "spec": {"conditions": {"result": "failed"}}}))
    first = run(engine, [log(i) for i in range(3)], [LOGIN, SPRAY])
    second = run(engine, [log(10 + i, user=f"v{i}") for i in range(3)], [LOGIN, SPRAY])
    assert [m.rule_id for m in first] == ["spray"] and second == []


def test_no_tuning_changes_nothing(make_engine):
    engine = make_engine([])
    assert len(run(engine, [log(0), log(1)], [LOGIN])) == 2


def test_backtests_apply_tuning_and_report_suppressed():
    from backtest import run_backtest

    rows = [{"ts": T0 + timedelta(seconds=i), "host": "", "service": "s", "level": "info", "msg": "m",
             "trace_id": "", "span_id": "", "status": 0, "src_ip": "10.0.5.5" if i % 2 else "1.2.3.4",
             "user_id": "", "attrs": json.dumps({"result": "failed", "user": f"u{i}"})} for i in range(6)]

    class DB:
        async def fetch_all(self, sql, params=None):
            return [r for r in rows if params["chunk_start"] <= r["ts"] < params["chunk_end"]]

    tuning = TuningSet.from_records(records({"rule_id": "login-fail", "kind": "exclusion",
                                             "spec": {"conditions": {"src_ip": "10.0.5.5"}}}))
    result = asyncio.run(run_backtest(DB(), [LOGIN], "login-fail", "t1", T0, T0 + timedelta(hours=1),
                                      tuning=tuning))
    assert result["alerts_total"] == 3 and result["alerts_suppressed"] == 3
