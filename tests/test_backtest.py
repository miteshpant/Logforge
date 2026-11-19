"""
Backtesting a rule over stored logs (Phase 1):
POST /v1/security/rules/{rule_id}/backtest.

`run_backtest` reads the tenant's logs_raw_mt rows in the time range, in
time order and in time chunks, narrowed by the compiled prefilter, and
replays them through the engine (detection_replay) with one correlation
store for the whole range, so windows span chunk boundaries. Correlation and
count rules bring the base rules they reference.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from backtest import BacktestError, RuleNotFound, row_to_event, run_backtest

T0 = datetime(2026, 11, 10, tzinfo=timezone.utc)


def row(seconds, **attrs):
    return {"ts": T0 + timedelta(seconds=seconds), "host": "", "service": "sshd", "level": "info",
            "msg": "auth", "trace_id": "", "span_id": "", "status": 0, "src_ip": "203.0.113.9",
            "user_id": "", "attrs": json.dumps(attrs)}


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    async def fetch_all(self, sql, params=None):
        self.queries.append((" ".join(sql.split()), params))
        lo, hi = params["chunk_start"], params["chunk_end"]
        selected = [r for r in self.rows if lo <= r["ts"] < hi]
        return selected[: params["limit"]]


BRUTE = {"id": "bf", "title": "Brute force", "severity": "high", "attack_techniques": ["T1110"],
         "detection": {"selection": {"event_type": "authentication", "result": "failed"},
                       "timeframe": "5m", "condition": "count(selection) >= 10 by src_ip"}}
AUTH_FAILED = {"id": "base-f", "name": "auth_failed", "generate": False,
               "detection": {"selection": {"event_type": "authentication", "result": "failed"},
                             "condition": "selection"}}
SPRAY = {"id": "spray", "title": "Spray", "severity": "high", "tags": ["attack.t1110.003"],
         "correlation": {"type": "value_count", "rules": ["auth_failed"], "group-by": ["src_ip"],
                         "timespan": "10m", "condition": {"field": "user", "gte": 5}}}
FAILED = {"event_type": "authentication", "result": "failed"}


def backtest(rows, rule_id="bf", rules=(BRUTE,), **kwargs):
    db = FakeDB(rows)
    kwargs.setdefault("start", T0)
    kwargs.setdefault("end", T0 + timedelta(days=1))
    result = asyncio.run(run_backtest(db, list(rules), rule_id, "t1", chunk=timedelta(hours=1), **kwargs))
    return result, db


def test_row_to_event_matches_what_the_live_path_sees():
    event = row_to_event(dict(row(0, user="bob", event_type="authentication"), host="web-01"))
    assert event["hostname"] == "web-01" and event["message"] == "auth"
    assert event["attrs"] == {"user": "bob", "event_type": "authentication"}
    assert event["ts"].startswith("2026-11-10T00:00:00")


def test_count_rule_fires_across_chunk_boundaries():
    rows = [row(3600 - 30 + i * 5, **FAILED) for i in range(10)]  # 10 failures straddling 01:00
    result, db = backtest(rows)
    assert result["alerts_total"] == 1
    assert result["alerts"][0]["group"] == {"src_ip": "203.0.113.9"}
    assert result["events_scanned"] == 10
    assert len(db.queries) == 24  # one per hour


def test_queries_are_tenant_scoped_time_bounded_and_prefiltered():
    _, db = backtest([row(0, **FAILED)])
    sql, params = db.queries[0]
    assert "FROM logs_raw_mt WHERE customer_id = %(tenant_id)s" in sql
    assert "ts >= %(chunk_start)s AND ts < %(chunk_end)s" in sql
    assert "ORDER BY ts" in sql
    assert params["tenant_id"] == "t1"
    assert "authentication" in params.values()  # the compiled prefilter's parameter


def test_correlation_rules_bring_their_base_rules():
    rows = [row(i, user=f"u{i}", **FAILED) for i in range(5)]
    result, _ = backtest(rows, rule_id="spray", rules=[BRUTE, AUTH_FAILED, SPRAY])
    assert result["alerts_total"] == 1
    assert result["rules_replayed"] == ["base-f", "spray"]


def test_other_rules_do_not_count_as_alerts():
    rows = [row(i, **FAILED) for i in range(12)]
    result, _ = backtest(rows, rule_id="spray", rules=[BRUTE, AUTH_FAILED, SPRAY])
    assert result["alerts_total"] == 0


def test_scan_is_capped():
    rows = [row(i, **FAILED) for i in range(50)]
    result, _ = backtest(rows, max_events=20)
    assert result["truncated"] is True and result["events_scanned"] == 20


def test_alert_samples_are_capped_but_counted():
    rows = [row(i * 2, **FAILED) for i in range(100)]  # 10 bursts of 10
    result, _ = backtest(rows, sample_limit=3)
    assert result["alerts_total"] == 10 and len(result["alerts"]) == 3
    assert result["by_day"] == {"2026-11-10": 10}


def test_unknown_rule_and_bad_ranges_are_rejected():
    with pytest.raises(RuleNotFound):
        backtest([], rule_id="missing")
    with pytest.raises(BacktestError, match="end must be after start"):
        backtest([], end=T0)
    with pytest.raises(BacktestError, match="at most 31 days"):
        backtest([], end=T0 + timedelta(days=40))
