"""
Correlations over alerts: the reserved reference `alerts` matches every alert
another rule raises, once per ATT&CK technique ("three techniques on one host
in an hour").
"""

import json
from datetime import timedelta

import pytest

from correlation import CorrelationRule, CorrelationRuleError, CorrelationStore, feed_alert
from detection_replay import TIMELINE_START, replay

MULTI = {"id": "multi-technique", "title": "Several techniques on one host", "level": "critical",
         "tags": ["attack.t1078"],
         "correlation": {"type": "value_count", "rules": ["alerts"], "group-by": ["host"], "timespan": "1h",
                         "condition": {"field": "alert.technique", "gte": 3}}}


def base(rid, process, technique, level="medium"):
    return {"id": rid, "title": rid, "level": level, "severity": level, "tags": [f"attack.{technique.lower()}"],
            "detection": {"selection": {"process": process}, "condition": "selection"}}


RULES = [base("discovery", "whoami", "T1033"), base("dump", "procdump", "T1003"), base("tunnel", "plink", "T1572"),
         base("again", "whoami2", "T1033")]


def at(minutes, host, process):
    return {"timestamp": (TIMELINE_START + timedelta(minutes=minutes)).isoformat(), "host": host, "process": process}


def fired(events, rules=RULES, extra=MULTI):
    return [a for a in replay(rules + [extra], events) if a.rule_id == extra["id"]]


def test_three_distinct_techniques_on_a_host_fire():
    alerts = fired([at(0, "h1", "whoami"), at(10, "h1", "procdump"), at(20, "h1", "plink")])
    assert len(alerts) == 1 and alerts[0].group == {"host": "h1"} and alerts[0].value == 3


def test_repeated_techniques_and_other_hosts_dont_count():
    assert fired([at(0, "h1", "whoami"), at(5, "h1", "whoami2"), at(10, "h1", "procdump"),
                  at(15, "h2", "plink")]) == []


def test_the_window_applies():
    assert fired([at(0, "h1", "whoami"), at(30, "h1", "procdump"), at(90, "h1", "plink")]) == []


def test_severity_filter():
    high_only = dict(MULTI, id="high-only", correlation=dict(MULTI["correlation"], rules=["alerts:high"],
                                                            condition={"field": "alert.technique", "gte": 2}))
    rules = [base("discovery", "whoami", "T1033"), base("dump", "procdump", "T1003", level="high"),
             base("tunnel", "plink", "T1572", level="high")]
    assert fired([at(0, "h1", "whoami"), at(5, "h1", "procdump")], rules, high_only) == []
    assert len(fired([at(0, "h1", "procdump"), at(5, "h1", "plink")], rules, high_only)) == 1


def test_alert_correlations_are_not_fed_back():
    rule = CorrelationRule.from_dict(dict(MULTI, correlation=dict(MULTI["correlation"], condition={"gte": 1},
                                                                   type="event_count")))
    store = CorrelationStore()
    out = feed_alert(store, "t", [rule], {"host": "h"}, TIMELINE_START, "x", "high", ["T1"])
    assert len(out) == 1 and out[0].rule.reads_alerts  # callers don't feed reads_alerts rules' alerts


def test_alerts_cant_be_mixed_with_base_rules():
    with pytest.raises(CorrelationRuleError, match="only reference alerts"):
        CorrelationRule.from_dict(dict(MULTI, correlation=dict(MULTI["correlation"], rules=["alerts", "dump"])))


def test_the_gate_replays_every_rule_for_an_alert_correlation():
    from mitre_default_loader import MitreDefaultLoader

    loader = MitreDefaultLoader.__new__(MitreDefaultLoader)
    loader._condition_evaluator = None
    bases = [dict(b, fixtures={"true_positive": {"process": b["detection"]["selection"]["process"]},
                               "true_negative": {"process": "ls"}}) for b in RULES]
    corr = dict(MULTI, fixtures={
        "true_positive_batch": [{"host": "h1", "process": "whoami"}, {"host": "h1", "process": "procdump"},
                                {"host": "h1", "process": "plink"}],
        "true_negative_batch": [{"host": "h1", "process": "whoami"}, {"host": "h1", "process": "whoami2"},
                                {"host": "h2", "process": "plink"}]})
    rows, awaiting = loader._rows_from_candidates([(r, f"{r['id']}.yml") for r in [corr] + bases])
    assert awaiting == []
    content = json.loads(next(r for r in rows if r["id"] == "logforge_multi-technique")["rule_content"])
    assert content["correlation"]["rules"] == ["alerts"]
    assert set(content["replay_rules"]) == {"logforge_discovery", "logforge_dump", "logforge_tunnel", "logforge_again"}


def test_a_backtest_of_an_alert_correlation_replays_every_rule():
    from backtest import resolve_rules

    ids = [r["id"] for r in resolve_rules(RULES + [MULTI], "multi-technique")]
    assert ids[-1] == "multi-technique" and set(ids[:-1]) == {r["id"] for r in RULES}


def test_a_rule_with_several_techniques_counts_once():
    many = dict(base("enum", "nltest", "T1482"), tags=["attack.t1482", "attack.t1087.002", "attack.t1069.002"])
    assert fired([at(0, "h1", "nltest")], RULES + [many]) == []


def test_alerts_without_the_group_field_are_not_correlated():
    events = [{"timestamp": e["timestamp"], "process": e["process"]}
              for e in [at(0, "x", "whoami"), at(5, "x", "procdump"), at(10, "x", "plink")]]
    assert fired(events) == []
