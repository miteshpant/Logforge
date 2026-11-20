"""
Behaviour baselines (Phase 11): unusual hours, new countries, volume (the
3-sigma rule of services/anomaly_detector.py) and peer-group spread, each
against the entity's last 30 days.
"""

import asyncio
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from entity_baselines import (BaselineStore, country_anomalies, detect, hour_anomalies, peer_anomaly,
                              volume_anomaly)

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def test_activity_at_an_hour_it_never_works_is_flagged():
    office = Counter({h: 30 for h in range(9, 18)})
    assert [a.label for a in hour_anomalies(office, Counter({3: 4, 10: 5}), days=20, now=NOW)] == \
        ["4 event(s) at 03:00 UTC, an hour with 0% of its usual activity"]
    # too little history: nothing to compare with
    assert hour_anomalies(Counter({10: 5}), Counter({3: 4}), days=2, now=NOW) == []


def test_a_new_country_is_flagged_only_against_a_known_history():
    found = country_anomalies({"DE", "FR"}, Counter({"RO": 3, "DE": 9}), baseline_events=200, now=NOW)
    assert len(found) == 1 and "from RO" in found[0].label and found[0].severity == "medium"
    assert country_anomalies(set(), Counter({"RO": 3}), baseline_events=200, now=NOW) == []


def test_volume_uses_the_three_sigma_rule_and_the_detectors_severity_scale():
    usual = [100, 110, 95, 105, 98, 102, 101]
    assert volume_anomaly(usual, 108, NOW) is None
    burst = volume_anomaly(usual, 400, NOW)
    assert burst and burst.severity == "high" and "400 events today" in burst.label


def test_peers():
    spreads = {f"u{i}": 2 for i in range(40)} | {"svc-backup": 30}
    found = peer_anomaly("user", "svc-backup", spreads, NOW)
    assert found and "30 distinct hosts today" in found.label and found.severity == "high"
    assert peer_anomaly("user", "u1", spreads, NOW) is None


def test_detect_combines_the_four():
    hours = [{"v": "bob", "h": h, "recent": 0, "c": 20} for h in range(9, 18)] + [{"v": "bob", "h": 3, "recent": 1, "c": 5}]
    countries = [{"v": "bob", "country": "DE", "recent": 0, "c": 180}, {"v": "bob", "country": "RO", "recent": 1, "c": 5}]
    daily = [{"v": "bob", "d": date(2026, 11, d), "recent": 0, "c": 18} for d in range(1, 19)] + \
        [{"v": "bob", "d": date(2026, 11, 20), "recent": 1, "c": 90}]
    spreads = [{"v": f"u{i}", "n": 1} for i in range(20)] + [{"v": "bob", "n": 12}]
    found = detect("user", ["bob", "carol"], hours, countries, daily, spreads, NOW)
    assert set(found) == {"bob"} and {a.kind for a in found["bob"]} == {"hour", "country", "volume", "peers"}


class FakeDB:
    def __init__(self):
        self.calls = []

    async def fetch_all(self, sql, params):
        self.calls.append((sql, params))
        return []


def test_the_store_binds_the_tenant_and_values():
    db = FakeDB()
    asyncio.run(BaselineStore(db).anomalies("acme", "user", ["bob'"], now=NOW))
    assert len(db.calls) == 4
    for sql, params in db.calls:
        assert "customer_id = %(tenant)s" in sql and "bob'" not in sql
        assert params["tenant"] == "acme" and params["values"] == ["bob'"]
        assert params["start"] == NOW - timedelta(days=30)
    assert asyncio.run(BaselineStore(db).anomalies("acme", "service", ["x"])) == {}
