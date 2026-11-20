"""
Fixture gate v2: aggregation and sequence rules (Phase 1).

Every packaged rule must prove itself before it is enabled. For count() and
correlation rules the proof is a timeline: `true_positive_batch` must fire,
`true_negative_batch` and the benign corpus must not, when replayed through
the runtime (detection_replay), so windows and ordering are checked too.

Correlation rules reference base rules by `name` (or id). The references must
resolve to rules that loaded; at runtime they are rewritten to the base rule's
`name`, or its runtime id (logforge_<id>) when it has none. Base rules keep
`name` and `generate` so the runtime can feed correlations from them.
"""

import json

import pytest

from mitre_default_loader import MitreDefaultLoader

FAILED = {"event_type": "authentication", "result": "failed", "src_ip": "203.0.113.9"}
SUCCESS = {"event_type": "authentication", "result": "success", "src_ip": "203.0.113.9"}


@pytest.fixture
def loader():
    instance = MitreDefaultLoader.__new__(MitreDefaultLoader)  # no database
    instance._condition_evaluator = None
    return instance


def base(rid, result, name=None, generate=False):
    data = {"id": rid, "title": rid, "level": "low", "tags": ["attack.t1110"],
            "detection": {"selection": {"event_type": "authentication", "result": result},
                          "condition": "selection"},
            "generate": generate,
            "fixtures": {"true_positive": dict(FAILED, result=result),
                         "true_negative": dict(FAILED, result="other")}}
    if name:
        data["name"] = name
    return data


def correlation(rules=("auth_failed", "auth_ok"), positive=None, negative=None, **corr):
    spec = {"type": "temporal_ordered", "rules": list(rules), "group-by": ["src_ip"], "timespan": "10m"}
    spec.update(corr)
    return {"id": "bf-success", "title": "Brute force then success", "level": "high",
            "tags": ["attack.credential_access", "attack.t1110", "attack.t1078"],
            "correlation": spec,
            "fixtures": {
                "true_positive_batch": positive or [{"repeat": 5, "event": FAILED}, SUCCESS],
                "true_negative_batch": negative or [SUCCESS, {"repeat": 5, "event": FAILED}],
            }}


BASES = [base("lf-auth-failed", "failed", name="auth_failed"), base("lf-auth-ok", "success", name="auth_ok")]


def load(loader, rules):
    return loader._rows_from_candidates([(r, f"{r['id']}.yml") for r in rules])


def test_correlation_rule_with_valid_fixtures_loads(loader):
    rows, awaiting = load(loader, BASES + [correlation()])
    assert awaiting == []
    row = next(r for r in rows if r["id"] == "logforge_bf-success")
    content = json.loads(row["rule_content"])
    assert content["correlation"]["rules"] == ["auth_failed", "auth_ok"]
    assert row["mitre_techniques"] == ["T1110", "T1078"]
    assert "true_positive_batch" in content["fixtures"]


def test_base_rules_keep_name_and_generate(loader):
    rows, _ = load(loader, BASES)
    content = json.loads(rows[0]["rule_content"])
    assert content["name"] == "auth_failed" and content["generate"] is False


def test_references_by_id_become_runtime_ids(loader):
    bases = [base("lf-auth-failed", "failed"), base("lf-auth-ok", "success")]
    rows, awaiting = load(loader, bases + [correlation(rules=("lf-auth-failed", "lf-auth-ok"))])
    assert awaiting == []
    content = json.loads(next(r for r in rows if r["id"] == "logforge_bf-success")["rule_content"])
    assert content["correlation"]["rules"] == ["logforge_lf-auth-failed", "logforge_lf-auth-ok"]


def test_unknown_base_rule_is_rejected(loader):
    _, awaiting = load(loader, BASES + [correlation(rules=("auth_failed", "missing"))])
    assert awaiting == ["bf-success.yml: references unknown base rule 'missing'"]


def test_invalid_correlation_is_rejected_with_the_reason(loader):
    _, awaiting = load(loader, BASES + [correlation(type="nonsense")])
    assert awaiting == ["bf-success.yml: unsupported correlation type 'nonsense'"]


def test_positive_timeline_must_fire(loader):
    too_slow = [{"repeat": 5, "event": FAILED}, {"at": "1h", "event": SUCCESS}]
    _, awaiting = load(loader, BASES + [correlation(positive=too_slow)])
    assert awaiting == ["bf-success.yml: true_positive_batch does not fire"]


def test_negative_timeline_must_not_fire(loader):
    _, awaiting = load(loader, BASES + [correlation(negative=[FAILED, SUCCESS])])
    assert awaiting == ["bf-success.yml: true_negative_batch fires"]


def test_correlation_must_not_fire_on_the_benign_corpus(loader):
    noisy = {"id": "noisy", "title": "Any failed login", "level": "low", "tags": ["attack.t1110"],
             "correlation": {"type": "event_count", "rules": ["auth_failed"], "timespan": "1h",
                             "condition": {"gte": 1}},
             "fixtures": {"true_positive_batch": [FAILED], "true_negative_batch": [SUCCESS]}}
    _, awaiting = load(loader, BASES + [noisy])
    assert awaiting == ["noisy.yml: fires on the benign event corpus"]


def test_count_rule_fixtures_respect_the_timeframe(loader):
    rule = {"id": "t-count", "title": "t", "level": "high", "tags": ["attack.t1110"],
            "detection": {"selection": {"event_type": "authentication", "result": "failed"},
                          "timeframe": "5m", "condition": "count(selection) >= 3 by src_ip"},
            "fixtures": {"true_positive_batch": [{"repeat": 3, "every": "10m", "event": FAILED}],
                         "true_negative_batch": [SUCCESS]}}
    _, awaiting = load(loader, [rule])
    assert awaiting == ["t-count.yml: true_positive_batch does not reach the threshold"]


def test_correlations_can_reference_correlations_in_any_order(loader):
    burst = {"id": "lf-burst", "name": "brute_burst", "title": "burst", "level": "low", "generate": False,
             "tags": ["attack.t1110"],
             "correlation": {"type": "event_count", "rules": ["auth_failed"], "group-by": ["src_ip"],
                             "timespan": "5m", "condition": {"gte": 3}},
             "fixtures": {"true_positive_batch": [{"repeat": 3, "event": FAILED}],
                          "true_negative_batch": [{"repeat": 2, "event": FAILED}]}}
    chain = correlation(rules=("brute_burst", "auth_ok"),
                        positive=[{"repeat": 3, "event": FAILED}, SUCCESS],
                        negative=[FAILED, SUCCESS])
    rows, awaiting = load(loader, [chain] + BASES + [burst])
    assert awaiting == []
    by_id = {r["id"]: json.loads(r["rule_content"]) for r in rows}
    assert by_id["logforge_bf-success"]["correlation"]["rules"] == ["brute_burst", "auth_ok"]
    assert by_id["logforge_lf-burst"]["generate"] is False and by_id["logforge_lf-burst"]["name"] == "brute_burst"


def test_a_correlation_cycle_is_rejected(loader):
    a = correlation(rules=("auth_failed", "b_rule"))
    a.update(id="a", name="a_rule")
    b = correlation(rules=("auth_failed", "a_rule"))
    b.update(id="b", name="b_rule")
    _, awaiting = load(loader, BASES + [a, b])
    assert sorted(awaiting) == ["a.yml: references unknown base rule 'b_rule'",
                                "b.yml: references unknown base rule 'a_rule'"]


def test_until_references_resolve_and_are_gated(loader):
    reset = base("lf-pw-reset", "reset", name="pw_reset")
    negative = [{"repeat": 5, "event": FAILED}, dict(FAILED, result="reset"), SUCCESS]
    rows, awaiting = load(loader, BASES + [reset, correlation(until="lf-pw-reset", negative=negative)])
    assert awaiting == []
    content = json.loads(next(r for r in rows if r["id"] == "logforge_bf-success")["rule_content"])
    assert content["correlation"]["until"] == ["pw_reset"]  # named rules are referenced by name
    assert "logforge_lf-pw-reset" in content["replay_rules"]
    _, awaiting = load(loader, BASES + [correlation(until="missing")])
    assert awaiting == ["bf-success.yml: references unknown base rule 'missing'"]
