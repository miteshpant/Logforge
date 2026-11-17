"""
Streaming correlation engine (Phase 1).

CorrelationStore.process(tenant, rules, event, matched_rule_names, ts) feeds one
event (with the names of the base rules it matched) and returns the
correlation alerts it completes. State is kept per tenant, rule and group, and
is bounded: a threshold rule keeps at most `threshold` entries per group, and
the number of groups is capped with least-recently-used eviction.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest

from correlation import CorrelationRule, CorrelationStore

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def rule(ctype="event_count", rules=("failed_login",), group_by=("src_ip",), timespan="5m",
         condition=None, rid="c1"):
    corr = {"type": ctype, "rules": list(rules), "group-by": list(group_by), "timespan": timespan}
    if condition is not None:
        corr["condition"] = condition
    return CorrelationRule.from_dict({"id": rid, "title": rid, "level": "high", "correlation": corr})


BRUTE = rule(condition={"gte": 10})


def feed(store, rules, events, tenant="t1"):
    """events: (seconds_offset, event_dict, matched_names) -> all alerts produced."""
    alerts = []
    for offset, event, matched in events:
        alerts += store.process(tenant, rules, event, set(matched), T0 + timedelta(seconds=offset))
    return alerts


def fail(ip="203.0.113.9", user="root"):
    return {"src_ip": ip, "user": user}


# --- event_count -------------------------------------------------------------

def test_event_count_fires_when_the_threshold_is_reached_inside_the_window():
    store = CorrelationStore()
    alerts = feed(store, [BRUTE], [(i * 10, fail(), ["failed_login"]) for i in range(10)])

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule.id == "c1"
    assert alert.group == {"src_ip": "203.0.113.9"}
    assert alert.value == 10
    assert alert.first_seen == T0 and alert.last_seen == T0 + timedelta(seconds=90)
    assert 0 < len(alert.events) <= 10


def test_event_count_ignores_matches_spread_beyond_the_window():
    store = CorrelationStore()
    alerts = feed(store, [BRUTE], [(i * 60, fail(), ["failed_login"]) for i in range(10)])  # 9 minutes
    assert alerts == []


def test_groups_are_counted_separately():
    store = CorrelationStore()
    events = [(i, fail(ip=f"198.51.100.{i % 2}"), ["failed_login"]) for i in range(18)]
    assert feed(store, [BRUTE], events) == []  # 9 per IP


def test_a_group_fires_once_per_burst_then_starts_counting_again():
    store = CorrelationStore()
    alerts = feed(store, [BRUTE], [(i, fail(), ["failed_login"]) for i in range(25)])
    assert [a.value for a in alerts] == [10, 10]  # at the 10th and 20th, not on every event after


def test_events_that_match_no_referenced_rule_are_ignored():
    store = CorrelationStore()
    events = [(i, fail(), ["something_else"]) for i in range(20)] + [(30, fail(), [])]
    assert feed(store, [BRUTE], events) == []


def test_group_fields_are_read_from_attrs_too():
    store = CorrelationStore()
    events = [(i, {"attrs": {"src_ip": "192.0.2.7"}}, ["failed_login"]) for i in range(10)]
    alerts = feed(store, [BRUTE], events)
    assert alerts[0].group == {"src_ip": "192.0.2.7"}


def test_tenants_have_separate_state():
    store = CorrelationStore()
    events = [(i, fail(), ["failed_login"]) for i in range(5)]
    feed(store, [BRUTE], events, tenant="a")
    assert feed(store, [BRUTE], events, tenant="b") == []


def test_late_events_older_than_the_window_do_not_count():
    store = CorrelationStore()
    events = [(600 + i, fail(), ["failed_login"]) for i in range(9)] + [(0, fail(), ["failed_login"])]
    assert feed(store, [BRUTE], events) == []


# --- value_count / value_sum ---------------------------------------------------

def test_value_count_counts_distinct_values():
    spray = rule("value_count", timespan="10m", condition={"field": "user", "gte": 5})
    store = CorrelationStore()
    same_user = [(i, fail(user="root"), ["failed_login"]) for i in range(20)]
    assert feed(store, [spray], same_user) == []
    many_users = [(100 + i, fail(user=f"u{i}"), ["failed_login"]) for i in range(5)]
    alerts = feed(store, [spray], many_users)
    assert len(alerts) == 1 and alerts[0].value == 5


def test_value_sum_adds_a_numeric_field():
    exfil = rule("value_sum", rules=["outbound"], group_by=["src_ip"], timespan="1h",
                 condition={"field": "bytes_out", "gt": 1000})
    store = CorrelationStore()
    events = [(i, {"src_ip": "10.0.0.5", "bytes_out": "400"}, ["outbound"]) for i in range(3)]
    alerts = feed(store, [exfil], events)
    assert len(alerts) == 1 and alerts[0].value == 1200


# --- temporal / temporal_ordered ---------------------------------------------

def test_temporal_needs_every_rule_in_the_window_in_any_order():
    both = rule("temporal", rules=["recon", "dump"], group_by=["host"], timespan="10m")
    store = CorrelationStore()
    alerts = feed(store, [both], [(0, {"host": "h1"}, ["dump"]), (60, {"host": "h1"}, ["recon"])])
    assert len(alerts) == 1 and alerts[0].group == {"host": "h1"}


def test_temporal_ordered_requires_the_listed_order():
    chain = rule("temporal_ordered", rules=["brute", "success"], group_by=["src_ip"], timespan="10m")
    store = CorrelationStore()
    wrong = feed(store, [chain], [(0, fail(), ["success"]), (30, fail(), ["brute"])])
    assert wrong == []
    right = feed(store, [chain], [(60, fail(), ["success"])])
    assert len(right) == 1  # brute at 30s, success at 60s


def test_temporal_ordered_chain_must_fit_in_the_window():
    chain = rule("temporal_ordered", rules=["a", "b"], group_by=["host"], timespan="5m")
    store = CorrelationStore()
    assert feed(store, [chain], [(0, {"host": "h"}, ["a"]), (600, {"host": "h"}, ["b"])]) == []


# --- bounded state -------------------------------------------------------------

def test_threshold_rules_keep_at_most_threshold_entries_per_group():
    store = CorrelationStore()
    feed(store, [rule(condition={"gte": 1000})], [(i % 200, fail(), ["failed_login"]) for i in range(5000)])
    assert store.max_entries_per_group() <= 1000


def test_group_count_is_capped_with_lru_eviction():
    store = CorrelationStore(max_groups=100)
    events = [(i, fail(ip=f"10.{i // 250}.{i % 250}.1"), ["failed_login"]) for i in range(1000)]
    feed(store, [BRUTE], events)
    assert store.group_count() == 100
    assert store.evictions == 900


def test_soak_state_stays_bounded():
    store = CorrelationStore(max_groups=5000)
    rng = random.Random(7)
    rules = [BRUTE, rule("value_count", rid="c2", timespan="10m", condition={"field": "user", "gte": 20})]
    for i in range(200_000):
        event = fail(ip=f"10.{rng.randrange(64)}.{rng.randrange(256)}.1", user=f"u{rng.randrange(500)}")
        store.process("t1", rules, event, {"failed_login"}, T0 + timedelta(seconds=i * 0.01))
    assert store.group_count() <= 5000
    assert store.max_entries_per_group() <= 20


# --- chained correlations ------------------------------------------------------

def test_a_correlation_can_feed_another_in_the_same_event():
    """`brute force, then a success from the same source`: the burst is itself a
    correlation (by name), and the chain consumes it like a base rule."""
    burst = CorrelationRule.from_dict({"id": "burst", "name": "brute_burst", "title": "b", "level": "low",
                                       "correlation": {"type": "event_count", "rules": ["failed_login"],
                                                       "group-by": ["src_ip"], "timespan": "5m",
                                                       "condition": {"gte": 3}}})
    chain = rule("temporal_ordered", rules=["brute_burst", "success"], timespan="15m", rid="chain")
    store = CorrelationStore()
    events = [(i, fail(), ["failed_login"]) for i in range(3)] + [(60, fail(), ["success"])]
    alerts = feed(store, [burst, chain], events)
    assert [a.rule.id for a in alerts] == ["burst", "chain"]
    assert burst.name == "brute_burst"
