"""
Retro-hunting (Phase 3): when new indicators arrive, search the tenant's
recent stored logs for them and raise an alert for each past match.

* One parameterised query per indicator type over logs_raw_mt (src_ip and
  the caller's fields in attrs); domains also match subdomains.
* Each hit becomes an alert (rule logforge_lf-ti-retro-match) carrying the
  event, stamped with the indicator like ingest-time matching would have;
  severity follows the indicator's confidence (>= 80 high, else medium).
* At most `max_alerts` per run; the result says when it was cut short.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from retro_hunt import RETRO_RULE_ID, retro_hunt
from threat_intel import Indicator

T0 = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
INDICATORS = {
    ("ip", "50.16.16.211"): Indicator(value="50.16.16.211", indicator_type="ip", threat_type="botnet_cc",
                                      confidence=90, source="Feodo"),
    ("domain", "c2.badactor.example"): Indicator(value="c2.badactor.example", indicator_type="domain",
                                                 confidence=60, source="ThreatFox"),
}


def row(seconds_ago, **attrs):
    return {"ts": T0 - timedelta(seconds=seconds_ago), "host": "fw-01", "service": "firewall", "level": "info",
            "msg": "conn", "trace_id": "", "span_id": "", "status": 0, "src_ip": "10.0.1.15", "user_id": "",
            "attrs": json.dumps(attrs)}


class DB:
    def __init__(self, rows_by_type):
        self.rows_by_type = rows_by_type
        self.calls = []

    async def fetch_all(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        kind = params["kind"]
        return self.rows_by_type.get(kind, [])


def hunt(db, keys=None, **kwargs):
    alerts = []

    async def sink(tenant_id, alert):
        alerts.append((tenant_id, alert))

    keys = keys if keys is not None else list(INDICATORS)
    result = asyncio.run(retro_hunt("acme", keys, INDICATORS.get, db=db, sink=sink, now=T0, **kwargs))
    return result, alerts


def test_queries_are_tenant_scoped_time_bounded_and_per_type():
    db = DB({})
    result, _ = hunt(db)
    assert result == {"indicators": 2, "matches": 0, "alerts": 0, "truncated": False}
    kinds = sorted(p["kind"] for _, p in db.calls)
    assert kinds == ["domain", "ip"]
    sql, params = next(c for c in db.calls if c[1]["kind"] == "ip")
    assert "FROM logs_raw_mt WHERE customer_id = %(tenant_id)s AND ts >= %(since)s" in sql
    assert "src_ip IN %(values)s" in sql and "JSONExtractString(attrs, 'dst_ip') IN %(values)s" in sql
    assert params["values"] == ["50.16.16.211"] and params["tenant_id"] == "acme"
    assert params["since"] == "2026-11-11 12:00:00.000"
    domain_sql, domain_params = next(c for c in db.calls if c[1]["kind"] == "domain")
    assert "endsWith(lower(JSONExtractString(attrs, 'query')), %(suffix_0)s)" in domain_sql
    assert domain_params["suffix_0"] == ".c2.badactor.example"


def test_hits_become_stamped_alerts():
    db = DB({"ip": [row(3600, dst_ip="50.16.16.211")], "domain": [row(60, query="www.c2.badactor.example")]})
    result, alerts = hunt(db)
    assert result["matches"] == 2 and result["alerts"] == 2
    by_value = {a["matched_fields"]["retro_hunt"]["value"]: a for _, a in alerts}
    ip_alert = by_value["50.16.16.211"]
    assert ip_alert["rule_id"] == RETRO_RULE_ID and ip_alert["severity"] == "high"
    event = ip_alert["event"]
    assert event["attrs"]["threat"]["indicators"][0]["source"] == "Feodo"
    assert by_value["c2.badactor.example"]["severity"] == "medium"
    assert all(tenant == "acme" for tenant, _ in alerts)


def test_alerts_are_capped():
    db = DB({"ip": [row(i, dst_ip="50.16.16.211") for i in range(30)]})
    result, alerts = hunt(db, keys=[("ip", "50.16.16.211")], max_alerts=10)
    assert result["alerts"] == 10 and result["truncated"] is True and len(alerts) == 10


def test_no_new_indicators_no_queries():
    db = DB({})
    result, _ = hunt(db, keys=[])
    assert result["indicators"] == 0 and db.calls == []


def test_domains_are_also_found_in_url_hosts():
    """Found live: a domain indicator missed a past log whose URL pointed at
    it, although ingest-time matching checks URL hosts."""
    db = DB({"domain": [row(60, url="http://www.c2.badactor.example/beacon")]})
    result, alerts = hunt(db, keys=[("domain", "c2.badactor.example")])
    sql, _ = db.calls[0]
    assert "domain(JSONExtractString(attrs, 'url'))" in sql
    assert result["alerts"] == 1 and alerts[0][1]["matched_fields"]["retro_hunt"]["field"] == "url.host"
