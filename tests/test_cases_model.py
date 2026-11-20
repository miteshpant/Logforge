"""
Case model (Phase 2): an investigation owned by an analyst.

A case has a title, severity, status, assignee, linked alerts and entities,
tags, pinned evidence and SLA timestamps. Every change is an action that
returns the new case and the timeline events it produced, so the timeline is
also the audit trail.

Statuses: new -> investigating -> contained -> resolved | false_positive.
Closing needs a reason; a closed case can be reopened. The first move out of
`new` (or the first assignment) is the acknowledgement for the SLA.
"""

from datetime import datetime, timedelta, timezone

import pytest

from cases import Case, CaseError, apply_action, mentions_in, merge_cases, new_case, split_case

T0 = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)
ALERT = {"id": "a1", "severity": "medium", "rule_id": "bf001", "title": "Brute force",
         "entities": {"src_ip": ["203.0.113.9"]}, "ts": T0.isoformat()}


def make(**kwargs):
    case, events = new_case("acme", title="Brute force on bastion", actor="alice", now=T0, **kwargs)
    return case, events


def test_new_case_has_defaults_and_a_created_event():
    case, events = make(severity="high", tags=["ssh"])
    assert (case.status, case.severity, case.assignee, case.tags) == ("new", "high", None, ["ssh"])
    assert case.id and case.tenant_id == "acme" and case.created_at == T0
    assert [e["kind"] for e in events] == ["created"]
    assert events[0]["actor"] == "alice" and events[0]["case_id"] == case.id


def test_creating_from_alerts_links_them_and_takes_the_highest_severity():
    case, events = make(alerts=[ALERT, dict(ALERT, id="a2", severity="critical", entities={"user": ["root"]})])
    assert case.alert_ids == ["a1", "a2"] and case.severity == "critical"
    assert case.entities == {"src_ip": ["203.0.113.9"], "user": ["root"]}
    assert [e["kind"] for e in events] == ["created", "alert_attached", "alert_attached"]


def test_attaching_an_alert_raises_severity_and_records_its_time():
    case, _ = make(severity="low")
    case, events = apply_action(case, "attach_alert", "system", T0 + timedelta(minutes=5), alert=ALERT)
    assert case.severity == "medium" and case.alert_ids == ["a1"]
    assert case.last_alert_at == T0 + timedelta(minutes=5)
    again, events = apply_action(case, "attach_alert", "system", T0, alert=ALERT)
    assert events == [] and again.alert_ids == ["a1"]  # idempotent


def test_status_flow_and_sla_timestamps():
    case, _ = make()
    case, _ = apply_action(case, "set_status", "bob", T0 + timedelta(minutes=10), status="investigating")
    assert case.acknowledged_at == T0 + timedelta(minutes=10)
    case, _ = apply_action(case, "set_status", "bob", T0 + timedelta(minutes=30), status="contained")
    assert case.contained_at == T0 + timedelta(minutes=30)
    case, events = apply_action(case, "set_status", "bob", T0 + timedelta(hours=2), status="resolved",
                                reason="Password reset, source blocked")
    assert case.resolved_at == T0 + timedelta(hours=2) and case.close_reason == "Password reset, source blocked"
    assert events[0]["kind"] == "status_changed"
    assert events[0]["data"] == {"from": "contained", "to": "resolved", "reason": "Password reset, source blocked"}


def test_closing_needs_a_reason():
    case, _ = make()
    with pytest.raises(CaseError, match="reason"):
        apply_action(case, "set_status", "bob", T0, status="false_positive")


def test_invalid_transitions_are_rejected():
    case, _ = make()
    with pytest.raises(CaseError, match="unknown status"):
        apply_action(case, "set_status", "bob", T0, status="done")
    with pytest.raises(CaseError, match="already"):
        apply_action(case, "set_status", "bob", T0, status="new")


def test_reopening_clears_the_resolution_but_keeps_the_acknowledgement():
    case, _ = make()
    case, _ = apply_action(case, "set_status", "bob", T0 + timedelta(minutes=1), status="false_positive", reason="test")
    case, _ = apply_action(case, "set_status", "bob", T0 + timedelta(minutes=2), status="investigating")
    assert case.resolved_at is None and case.close_reason == "" and case.acknowledged_at == T0 + timedelta(minutes=1)


def test_assignment_acknowledges_and_is_recorded():
    case, _ = make()
    case, events = apply_action(case, "assign", "lead", T0 + timedelta(minutes=3), assignee="bob")
    assert case.assignee == "bob" and case.acknowledged_at == T0 + timedelta(minutes=3)
    assert events[0]["data"] == {"from": None, "to": "bob"}
    case, events = apply_action(case, "assign", "lead", T0 + timedelta(minutes=4), assignee=None)
    assert case.assignee is None and case.acknowledged_at == T0 + timedelta(minutes=3)


def test_comments_record_mentions():
    case, events = apply_action(make()[0], "comment", "alice", T0, text="@bob can you check @carol.ops's box? mail x@y.z")
    assert events[0]["kind"] == "comment"
    assert events[0]["data"] == {"text": "@bob can you check @carol.ops's box? mail x@y.z", "mentions": ["bob", "carol.ops"]}
    with pytest.raises(CaseError, match="empty"):
        apply_action(case, "comment", "alice", T0, text="  ")


def test_mentions_parsing():
    assert mentions_in("@bob @bob, @dana_ops!") == ["bob", "dana_ops"]
    assert mentions_in("no mentions, email a@b.c") == []


def test_tags_and_evidence():
    case, _ = make(tags=["ssh"])
    case, events = apply_action(case, "tags", "alice", T0, add=["brute-force", "ssh"], remove=["ssh"])
    assert case.tags == ["brute-force"]
    case, events = apply_action(case, "pin_evidence", "alice", T0, evidence={
        "kind": "search", "title": "Failed logins from source", "ref": "service:sshd src_ip:203.0.113.9"})
    assert events[0]["kind"] == "evidence_pinned" and events[0]["data"]["kind"] == "search"
    with pytest.raises(CaseError, match="evidence kind"):
        apply_action(case, "pin_evidence", "alice", T0, evidence={"kind": "photo", "ref": "x"})
    # pinning is reversible: unpinning records which pin it takes back
    pinned = events[0]["id"]
    case, events = apply_action(case, "unpin_evidence", "alice", T0, evidence_id=pinned)
    assert events[0]["kind"] == "evidence_unpinned" and events[0]["data"] == {"evidence_id": pinned}
    with pytest.raises(CaseError, match="evidence_id"):
        apply_action(case, "unpin_evidence", "alice", T0, evidence_id="")


def test_pinned_evidence_is_what_was_pinned_and_not_taken_back():
    from cases import pinned_evidence

    timeline = [{"id": "e1", "kind": "evidence_pinned", "data": {"kind": "search", "ref": "a"}},
                {"id": "e2", "kind": "evidence_pinned", "data": {"kind": "event", "ref": "b"}},
                {"id": "e3", "kind": "comment", "data": {}},
                {"id": "e4", "kind": "evidence_unpinned", "data": {"evidence_id": "e1"}}]
    assert [e["id"] for e in pinned_evidence(timeline)] == ["e2"]


def test_merge_moves_alerts_and_entities_and_closes_the_sources():
    target, _ = make(alerts=[ALERT])
    other, _ = new_case("acme", title="Same source", actor="system", now=T0,
                        alerts=[dict(ALERT, id="a9", severity="high", entities={"user": ["deploy"]})])
    merged, closed, events = merge_cases(target, [other], "alice", T0 + timedelta(hours=1))
    assert merged.alert_ids == ["a1", "a9"] and merged.severity == "high"
    assert merged.entities == {"src_ip": ["203.0.113.9"], "user": ["deploy"]}
    assert closed[0].status == "resolved" and closed[0].merged_into == merged.id
    assert closed[0].close_reason == f"merged into {merged.id}"
    kinds = sorted((e["case_id"] == merged.id, e["kind"]) for e in events)
    assert kinds == [(False, "merged_into"), (True, "merged")]


def test_merge_rejects_cross_tenant_and_self():
    target, _ = make()
    other, _ = new_case("other-tenant", title="x", actor="a", now=T0)
    with pytest.raises(CaseError, match="tenant"):
        merge_cases(target, [other], "alice", T0)
    with pytest.raises(CaseError, match="itself"):
        merge_cases(target, [target], "alice", T0)


def test_split_moves_alerts_to_a_new_case():
    case, _ = make(alerts=[ALERT, dict(ALERT, id="a2"), dict(ALERT, id="a3", entities={"user": ["eve"]})])
    remaining, created, events = split_case(case, ["a3"], "alice", T0, title="Eve's activity")
    assert remaining.alert_ids == ["a1", "a2"] and created.alert_ids == ["a3"]
    assert created.title == "Eve's activity" and created.severity == case.severity
    assert {e["kind"] for e in events} == {"split", "created", "split_from"}
    with pytest.raises(CaseError, match="not in the case"):
        split_case(case, ["zzz"], "alice", T0)
    with pytest.raises(CaseError, match="at least one"):
        split_case(case, ["a1", "a2", "a3"], "alice", T0)


def test_cases_round_trip_to_rows():
    case, _ = make(alerts=[ALERT], tags=["x"])
    assert Case.from_row(case.to_row()) == case


def test_unknown_action():
    with pytest.raises(CaseError, match="unknown action"):
        apply_action(make()[0], "delete", "a", T0)
