"""
Replaying a timeline of events through the detection runtime (Phase 1).

`detection_replay.replay(rules, events)` runs events, in time order, through
the same logic as the live path: per-event base rules, count() rules as
windowed event_count correlations, and Sigma correlation rules on a fresh
CorrelationStore. It is what the rule fixture gate, the detection eval
harness and the backtest endpoint use, so all three agree with production.

`expand_timeline(entries)` turns fixture/scenario entries into timestamped
events:
* a plain event comes 1s after the previous one;
* {repeat: N, event: {...}, every: "10s"} repeats it (default every 1s);
* {at: "5m", event: {...}} places it at an offset from the start.
"""

from datetime import datetime, timedelta, timezone

from detection_replay import expand_timeline, replay

FAILED = {"event_type": "authentication", "result": "failed", "src_ip": "203.0.113.9"}
SUCCESS = {"event_type": "authentication", "result": "success", "src_ip": "203.0.113.9"}


def rule(rid, detection=None, **extra):
    data = {"id": rid, "title": rid, "severity": "high", "tags": ["attack.t1110"],
            "detection": detection or {}}
    data.update(extra)
    return data


BRUTE = rule("bf", {"selection": {"event_type": "authentication", "result": "failed"},
                    "timeframe": "5m", "condition": "count(selection) >= 10 by src_ip"})
AUTH_FAILED = rule("auth-failed", {"selection": {"event_type": "authentication", "result": "failed"},
                                   "condition": "selection"}, name="auth_failed", generate=False)
AUTH_OK = rule("auth-ok", {"selection": {"event_type": "authentication", "result": "success"},
                           "condition": "selection"}, name="auth_ok", generate=False)
BRUTE_THEN_SUCCESS = rule("bf-success", tags=["attack.t1110", "attack.t1078"], correlation={
    "type": "temporal_ordered", "rules": ["auth_failed", "auth_ok"], "group-by": ["src_ip"],
    "timespan": "10m"})


# --- expand_timeline -----------------------------------------------------------

def test_plain_events_are_one_second_apart():
    events = expand_timeline([FAILED, SUCCESS])
    first, second = (datetime.fromisoformat(e["ts"]) for e in events)
    assert second - first == timedelta(seconds=1)
    assert events[0]["result"] == "failed"


def test_repeat_with_every_and_at():
    events = expand_timeline([{"repeat": 3, "every": "10s", "event": FAILED},
                              {"at": "5m", "event": SUCCESS}])
    times = [datetime.fromisoformat(e["ts"]) for e in events]
    assert times[1] - times[0] == timedelta(seconds=10)
    assert times[3] - times[0] == timedelta(minutes=5)
    assert [e["result"] for e in events] == ["failed"] * 3 + ["success"]


def test_events_are_copies():
    events = expand_timeline([{"repeat": 2, "event": FAILED}])
    events[0]["src_ip"] = "changed"
    assert events[1]["src_ip"] == "203.0.113.9" and FAILED["src_ip"] == "203.0.113.9"


def test_existing_timestamps_are_kept():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    assert expand_timeline([dict(FAILED, ts=ts)])[0]["ts"] == ts


# --- replay --------------------------------------------------------------------

def test_count_rule_fires_inside_its_window():
    alerts = replay([BRUTE], expand_timeline([{"repeat": 10, "event": FAILED}]))
    assert [a.rule_id for a in alerts] == ["bf"]
    assert alerts[0].group == {"src_ip": "203.0.113.9"}


def test_count_rule_respects_its_timeframe():
    spread = expand_timeline([{"repeat": 10, "every": "1m", "event": FAILED}])  # 9 minutes
    assert replay([BRUTE], spread) == []


def test_correlation_fires_and_generate_false_bases_do_not():
    events = expand_timeline([{"repeat": 3, "event": FAILED}, SUCCESS])
    alerts = replay([AUTH_FAILED, AUTH_OK, BRUTE_THEN_SUCCESS], events)
    assert [a.rule_id for a in alerts] == ["bf-success"]
    assert alerts[0].techniques == ["T1110", "T1078"]


def test_temporal_ordered_needs_the_order():
    events = expand_timeline([SUCCESS, {"repeat": 3, "event": FAILED}])
    assert replay([AUTH_FAILED, AUTH_OK, BRUTE_THEN_SUCCESS], events) == []


def test_single_event_rules_alert_per_event():
    login = rule("login", {"selection": {"result": "failed"}, "condition": "selection"})
    alerts = replay([login], expand_timeline([FAILED, SUCCESS, FAILED]))
    assert [a.rule_id for a in alerts] == ["login", "login"]


def test_events_are_replayed_in_time_order():
    late = dict(SUCCESS, ts="2026-01-01T00:10:00+00:00")
    early = [dict(FAILED, ts=f"2026-01-01T00:0{i}:00+00:00") for i in range(3)]
    alerts = replay([AUTH_FAILED, AUTH_OK, BRUTE_THEN_SUCCESS], [late] + early)
    assert [a.rule_id for a in alerts] == ["bf-success"]
