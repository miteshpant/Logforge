"""SLA targets per tenant: a tenant can override the default time to
acknowledge and resolve per severity; metrics count breaches against the
tenant's targets."""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import case_metrics as cm  # noqa: E402
from cases import Case  # noqa: E402

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def case(severity, age, acknowledged_after=None):
    created = NOW - age
    return Case(id="c", tenant_id="t", title="x", severity=severity, status="investigating" if acknowledged_after else "new",
                created_at=created, acknowledged_at=created + acknowledged_after if acknowledged_after else None)


def test_defaults_apply_without_overrides():
    targets = cm.sla_targets(None)
    assert targets["acknowledge"]["critical"] == timedelta(minutes=15)


def test_overrides_replace_only_what_they_name():
    targets = cm.sla_targets({"acknowledge": {"critical": 5}})
    assert targets["acknowledge"]["critical"] == timedelta(minutes=5)
    assert targets["acknowledge"]["high"] == timedelta(hours=1)
    assert targets["resolve"]["critical"] == timedelta(hours=4)


def test_breaches_follow_the_tenants_targets():
    cases = [case("critical", timedelta(minutes=10))]  # unacknowledged for 10 minutes
    assert cm.case_metrics(cases, NOW)["sla_breaches"]["acknowledge"]["critical"] == 0
    strict = cm.case_metrics(cases, NOW, targets=cm.sla_targets({"acknowledge": {"critical": 5}}))
    assert strict["sla_breaches"]["acknowledge"]["critical"] == 1
    assert strict["sla_targets_minutes"]["acknowledge"]["critical"] == 5


@pytest.mark.parametrize("bad", [
    {"respond": {"critical": 5}},                      # unknown kind
    {"acknowledge": {"urgent": 5}},                    # unknown severity
    {"acknowledge": {"critical": 0}},                  # too short
    {"acknowledge": {"critical": 10 ** 7}},            # longer than a year
    {"acknowledge": {"critical": 300}, "resolve": {"critical": 60}},  # acknowledge after resolve
])
def test_invalid_overrides_are_refused(bad):
    with pytest.raises(ValueError):
        cm.validate_sla_overrides(bad)
