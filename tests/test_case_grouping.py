"""
Automatic case grouping (Phase 2).

A new alert joins the open case for the same entity seen within the window
instead of becoming one more item to triage. The entity key is the Phase 1
correlation group when the alert has one, otherwise the most specific actor
in the event: source IP (network-origin activity), then host (endpoint
activity), then user. Alerts below the minimum severity join an existing
case but don't open one.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from case_grouping import GroupingPolicy, group_key, plan
from cases import new_case
from services.case_service import CaseService
from test_case_service import FakeAlerts, MemoryDAO, stored_alert

T0 = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)


def alert(severity="high", **entities):
    return {"id": "a", "severity": severity, "title": "Brute force",
            "entities": {k: [v] for k, v in entities.items()}}


# --- keys ----------------------------------------------------------------------

def test_correlation_groups_use_the_same_entity_priority():
    """A correlation grouped by (hostname, user) keys on the host, like that
    host's single-event alerts, so they land in one case (found on the
    eval corpus: discovery-burst was split across two cases)."""
    assert group_key(alert(user="x"), {"user": "bob", "hostname": "WS-043"}) == "hostname=WS-043"
    assert group_key(alert(), {"src_ip": "1.2.3.4", "user": "root"}) == "src_ip=1.2.3.4"


def test_correlation_groups_without_a_known_entity_use_all_fields():
    assert group_key(alert(src_ip="1.2.3.4"), {"tenant_app": "pay", "region": "eu"}) == "region=eu|tenant_app=pay"


@pytest.mark.parametrize("entities, key", [
    ({"src_ip": "1.2.3.4", "hostname": "h", "user": "u"}, "src_ip=1.2.3.4"),
    ({"hostname": "WS-044", "user": "carol"}, "hostname=WS-044"),
    ({"user": "carol"}, "user=carol"),
    ({}, ""),
])
def test_entity_priority(entities, key):
    assert group_key(alert(**entities)) == key


# --- plan ----------------------------------------------------------------------

POLICY = GroupingPolicy(window=timedelta(hours=24), min_severity="medium")


def open_case(**kwargs):
    case, _ = new_case("acme", "x", "system", T0, group_key="src_ip=1.2.3.4", **kwargs)
    case.last_alert_at = T0
    return case


def test_attaches_to_an_open_case_seen_within_the_window():
    assert plan(alert(src_ip="1.2.3.4"), open_case(), T0 + timedelta(hours=2), POLICY) == "attach"


def test_creates_when_there_is_no_case_and_skips_low_alerts():
    assert plan(alert(src_ip="1.2.3.4"), None, T0, POLICY) == "create"
    assert plan(alert("low", src_ip="1.2.3.4"), None, T0, POLICY) == "skip"
    assert plan(alert("low", src_ip="1.2.3.4"), open_case(), T0, POLICY) == "attach"


def test_alerts_without_an_entity_get_their_own_case():
    assert plan(alert(), None, T0, POLICY) == "create"


def test_policy_from_environment(monkeypatch):
    monkeypatch.setenv("CASE_GROUPING_WINDOW_HOURS", "6")
    monkeypatch.setenv("CASE_AUTO_MIN_SEVERITY", "high")
    policy = GroupingPolicy.from_env()
    assert policy.window == timedelta(hours=6) and policy.min_severity == "high"
    monkeypatch.setenv("CASE_GROUPING", "off")
    assert GroupingPolicy.from_env().enabled is False


# --- service -------------------------------------------------------------------

class GroupingDAO(MemoryDAO):
    async def find_open_by_group_key(self, tenant_id, key, since):
        found = [c for (t, _), c in self.cases.items() if t == tenant_id and c.group_key == key and c.is_open
                 and c.last_alert_at and c.last_alert_at >= since]
        return max(found, key=lambda c: c.last_alert_at) if found else None


def test_route_alert_creates_then_attaches(monkeypatch):
    clock = {"now": T0}
    alerts = FakeAlerts([stored_alert(f"a{i}") for i in range(3)] + [stored_alert("x1", src_ip="198.51.100.7")])
    service = CaseService(dao=GroupingDAO(), alerts=alerts, clock=lambda: clock["now"])

    first = asyncio.run(service.route_alert("acme", alerts.alerts["a0"], policy=POLICY))
    assert first.title == "Brute force: src_ip=203.0.113.9" and first.group_key == "src_ip=203.0.113.9"
    assert first.created_by == "system"
    clock["now"] = T0 + timedelta(minutes=30)
    second = asyncio.run(service.route_alert("acme", alerts.alerts["a1"], policy=POLICY))
    assert second.id == first.id and second.alert_ids == ["a0", "a1"]
    other = asyncio.run(service.route_alert("acme", alerts.alerts["x1"], policy=POLICY))
    assert other.id != first.id
    clock["now"] = T0 + timedelta(days=2)  # window passed: a new case
    later = asyncio.run(service.route_alert("acme", alerts.alerts["a2"], policy=POLICY))
    assert later.id not in (first.id, other.id)


def test_closed_cases_are_not_reused():
    alerts = FakeAlerts([stored_alert("a0"), stored_alert("a1")])
    service = CaseService(dao=GroupingDAO(), alerts=alerts, clock=lambda: T0)
    first = asyncio.run(service.route_alert("acme", alerts.alerts["a0"], policy=POLICY))
    asyncio.run(service.act("acme", first.id, "set_status", "bob", status="resolved", reason="done"))
    second = asyncio.run(service.route_alert("acme", alerts.alerts["a1"], policy=POLICY))
    assert second.id != first.id


def test_route_alert_uses_the_correlation_group():
    alerts = FakeAlerts([stored_alert("c1")])
    service = CaseService(dao=GroupingDAO(), alerts=alerts, clock=lambda: T0)
    case = asyncio.run(service.route_alert("acme", alerts.alerts["c1"], correlation_group={"hostname": "FS-01"},
                                           policy=POLICY))
    assert case.group_key == "hostname=FS-01"


def test_disabled_grouping_does_nothing():
    alerts = FakeAlerts([stored_alert("a0")])
    service = CaseService(dao=GroupingDAO(), alerts=alerts, clock=lambda: T0)
    off = GroupingPolicy(window=timedelta(hours=1), min_severity="medium", enabled=False)
    assert asyncio.run(service.route_alert("acme", alerts.alerts["a0"], policy=off)) is None
    assert service.dao.cases == {}


def test_concurrent_alerts_for_one_entity_open_one_case():
    alerts = FakeAlerts([stored_alert(f"a{i}") for i in range(5)])
    service = CaseService(dao=GroupingDAO(), alerts=alerts, clock=lambda: T0)

    async def burst():
        return await asyncio.gather(*(service.route_alert("acme", alerts.alerts[f"a{i}"], policy=POLICY)
                                      for i in range(5)))

    cases = asyncio.run(burst())
    assert len({c.id for c in cases}) == 1
    assert sorted(service.dao.cases[("acme", cases[0].id)].alert_ids) == [f"a{i}" for i in range(5)]


def test_case_titles_drop_the_detection_prefix():
    """Stored alerts are titled "Security Detection: <rule>"; the prefix only
    repeats what every case is about."""
    row = dict(stored_alert("p1"), title="Security Detection: Password spray")
    service = CaseService(dao=GroupingDAO(), alerts=FakeAlerts([row]), clock=lambda: T0)
    case = asyncio.run(service.route_alert("acme", row, policy=POLICY))
    assert case.title == "Password spray: src_ip=203.0.113.9"
