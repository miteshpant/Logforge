"""
Case service (Phase 2): case actions over storage and the tenant's alerts.

* Creating a case from alerts loads them (severity, rule, entities from the
  stored event) so the case is enriched without the caller restating them.
* Every action saves a new case version and appends its timeline events.
* Closing a case sets the verdict of its alerts: false_positive feeds the
  Phase 1 tuning suggestions; resolved resolves them. Merging doesn't.
* Bulk actions report per-case failures instead of stopping.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from cases import CaseError
from services.case_service import CaseNotFound, CaseService, alert_summary

T0 = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)


class MemoryDAO:
    def __init__(self):
        self.cases = {}
        self.log = []

    async def save(self, case):
        self.cases[(case.tenant_id, case.id)] = case

    async def save_all(self, cases):
        for case in cases:
            await self.save(case)

    async def append_events(self, events):
        self.log += events

    async def get(self, tenant_id, case_id):
        return self.cases.get((tenant_id, case_id))

    async def get_many(self, tenant_id, case_ids):
        return [c for (t, i), c in self.cases.items() if t == tenant_id and i in case_ids]

    async def events_of(self, case_id):
        return [e for e in self.log if e["case_id"] == case_id]

    async def events(self, tenant_id, case_id):
        return [e for e in self.log if e["case_id"] == case_id and e["tenant_id"] == tenant_id]


def stored_alert(alert_id, severity="high", **log):
    return {"id": alert_id, "rule_id": "logforge_bf001", "title": "Brute force", "severity": severity,
            "status": "new", "created_at": T0,
            "raw_log_data": json.dumps({"normalized_log": {"src_ip": "203.0.113.9", "hostname": "bastion-01",
                                                           "attrs": {"user": "root"}, **log}})}


class FakeAlerts:
    def __init__(self, alerts):
        self.alerts = {a["id"]: a for a in alerts}
        self.verdicts = []

    async def get(self, tenant_id, alert_id):
        return self.alerts.get(alert_id)

    async def set_verdict(self, tenant_id, alert_id, verdict, actor, notes):
        self.verdicts.append((alert_id, verdict, actor, notes))


@pytest.fixture
def service():
    alerts = FakeAlerts([stored_alert("a1"), stored_alert("a2", severity="critical", src_ip="198.51.100.7"),
                         stored_alert("a3", severity="low")])
    return CaseService(dao=MemoryDAO(), alerts=alerts, clock=lambda: T0)


def run(coro):
    return asyncio.run(coro)


def test_alert_summary_extracts_entities():
    summary = alert_summary(stored_alert("a1"))
    assert summary["entities"] == {"src_ip": ["203.0.113.9"], "hostname": ["bastion-01"], "user": ["root"]}
    assert (summary["severity"], summary["rule_id"]) == ("high", "logforge_bf001")


def test_create_from_alerts_enriches_the_case(service):
    case = run(service.create("acme", "alice", "Brute force on bastion", alert_ids=["a1", "a2"]))
    assert case.severity == "critical" and case.alert_ids == ["a1", "a2"]
    assert case.entities["src_ip"] == ["203.0.113.9", "198.51.100.7"]
    assert [e["kind"] for e in service.dao.log] == ["created", "alert_attached", "alert_attached"]


def test_unknown_alerts_are_rejected(service):
    with pytest.raises(CaseError, match="unknown alert zzz"):
        run(service.create("acme", "alice", "x", alert_ids=["zzz"]))


def test_actions_save_and_append(service):
    case = run(service.create("acme", "alice", "Case"))
    run(service.act("acme", case.id, "assign", "lead", assignee="bob"))
    updated = run(service.act("acme", case.id, "comment", "bob", text="@alice looking"))
    assert updated.assignee == "bob"
    assert [e["kind"] for e in service.dao.log][-2:] == ["assigned", "comment"]
    with pytest.raises(CaseNotFound):
        run(service.act("other-tenant", case.id, "comment", "x", text="hi"))


def test_closing_as_false_positive_sets_the_alert_verdicts(service):
    case = run(service.create("acme", "alice", "Case", alert_ids=["a1", "a2"]))
    run(service.act("acme", case.id, "set_status", "bob", status="false_positive", reason="pentest"))
    assert service.alerts.verdicts == [("a1", "false_positive", "bob", "pentest"),
                                       ("a2", "false_positive", "bob", "pentest")]
    case2 = run(service.create("acme", "alice", "Other", alert_ids=["a3"]))
    run(service.act("acme", case2.id, "set_status", "bob", status="resolved", reason="contained"))
    assert service.alerts.verdicts[-1] == ("a3", "resolved", "bob", "contained")


def test_attach_alerts_to_an_existing_case(service):
    case = run(service.create("acme", "alice", "Case", alert_ids=["a3"]))
    updated = run(service.attach_alerts("acme", case.id, ["a1", "a3"], "alice"))
    assert updated.alert_ids == ["a3", "a1"] and updated.severity == "high"


def test_merge_and_split(service):
    target = run(service.create("acme", "alice", "Target", alert_ids=["a1"]))
    source = run(service.create("acme", "alice", "Source", alert_ids=["a2", "a3"]))
    merged = run(service.merge("acme", target.id, [source.id], "alice"))
    assert merged.alert_ids == ["a1", "a2", "a3"]
    assert run(service.dao.get("acme", source.id)).merged_into == target.id
    assert service.alerts.verdicts == []  # merging is not a verdict
    remaining, created = run(service.split("acme", target.id, ["a3"], "alice", title="Low one"))
    assert remaining.alert_ids == ["a1", "a2"] and created.alert_ids == ["a3"]
    assert run(service.dao.get("acme", created.id)).title == "Low one"


def test_bulk_reports_failures_per_case(service):
    one = run(service.create("acme", "alice", "One"))
    two = run(service.create("acme", "alice", "Two"))
    result = run(service.bulk("acme", [one.id, two.id, "missing"], "set_status", "bob", status="investigating"))
    assert sorted(result["updated"]) == sorted([one.id, two.id])
    assert result["errors"] == {"missing": "case not found"}
    again = run(service.bulk("acme", [one.id], "set_status", "bob", status="investigating"))
    assert again["errors"] == {one.id: "the case is already investigating"}


def test_bulk_only_allows_safe_actions(service):
    with pytest.raises(CaseError, match="bulk"):
        run(service.bulk("acme", ["x"], "comment", "bob", text="hi"))


def test_details_include_timeline_and_alerts(service):
    case = run(service.create("acme", "alice", "Case", alert_ids=["a1"]))
    detail = run(service.details("acme", case.id, timeline=service.dao.events_of))
    assert detail["case"]["id"] == case.id and detail["case"]["created_at"] == T0.isoformat()
    assert [a["id"] for a in detail["alerts"]] == ["a1"]
    assert [e["kind"] for e in detail["timeline"]] == ["created", "alert_attached"]


def test_alert_summary_carries_threat_intel_and_geo():
    """Phase 3: the case page badges alerts whose event matched intel."""
    row = stored_alert("t1", attrs={"user": "root", "threat": {"matched": True, "max_confidence": 90,
                                                               "threat_types": ["botnet_cc"],
                                                               "indicators": [{"source": "Feodo"}]},
                                    "geo": {"src_ip": {"country": "US"}}})
    summary = alert_summary(row)
    assert summary["threat"] == {"max_confidence": 90, "threat_types": ["botnet_cc"], "sources": ["Feodo"]}
    assert summary["geo"] == {"src_ip": {"country": "US"}}
    assert "threat" not in alert_summary(stored_alert("t2"))
