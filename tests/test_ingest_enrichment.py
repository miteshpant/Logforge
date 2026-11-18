"""
Ingest-time threat intelligence matching (Phase 3).

enrich_events(tenant, events, index) looks up the IPs, domains, URLs, hashes
and emails in each event (model fields and attrs) against the tenant's
indicators and stamps matches onto the event as attrs.threat:

    {"matched": true, "max_confidence": 90, "threat_types": [...],
     "indicators": [{"field", "value", "type", "threat_type", "confidence",
                     "source", "tags"}]}

A URL's host is also checked as a domain. Events without matches are left
alone, a tenant with no indicators costs one dict lookup per batch, and an
index failure never fails ingestion. Rules match the stamp through dotted
paths into attrs (threat.matched).
"""

import asyncio
from datetime import datetime, timezone

from ingest_enrichment import enrich_events
from sigma_engine import SigmaConditionEvaluator
from threat_intel import Indicator
from threat_intel_store import IndicatorIndex

T0 = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
IOCS = [Indicator(value="162.243.103.246", indicator_type="ip", threat_type="botnet_cc", confidence=90,
                  source="abuse.ch Feodo Tracker", tags=["Emotet"]),
        Indicator(value="c2.badactor.example", indicator_type="domain", confidence=75, source="ThreatFox"),
        Indicator(value="http://198.51.100.66/bins/mozi.m", indicator_type="url", threat_type="malware_download",
                  confidence=80, source="URLhaus"),
        Indicator(value="44d88612fea8a8f36de82e1278abb02f", indicator_type="hash", confidence=50, source="ThreatFox")]


def index(iocs=IOCS):
    async def loader(tenant_id, now):
        return iocs if tenant_id == "acme" else []
    return IndicatorIndex(loader=loader)


def enrich(events, idx=None, tenant="acme"):
    return asyncio.run(enrich_events(tenant, events, idx or index(), now=T0))


def test_matching_fields_are_stamped():
    events = [{"src_ip": "10.0.1.15", "attrs": {"dst_ip": "162.243.103.246", "port": 8080}},
              {"src_ip": "10.0.1.15", "attrs": {"query": "www.c2.badactor.example"}},
              {"attrs": {"url": "http://198.51.100.66/bins/mozi.m", "md5": "44D88612FEA8A8F36DE82E1278ABB02F"}},
              {"src_ip": "10.0.1.16", "attrs": {"url": "https://github.com/"}}]
    stats = enrich(events)
    first = events[0]["attrs"]["threat"]
    assert first["matched"] is True and first["max_confidence"] == 90 and first["threat_types"] == ["botnet_cc"]
    assert first["indicators"] == [{"field": "dst_ip", "value": "162.243.103.246", "type": "ip",
                                    "threat_type": "botnet_cc", "confidence": 90,
                                    "source": "abuse.ch Feodo Tracker", "tags": ["Emotet"]}]
    assert events[1]["attrs"]["threat"]["indicators"][0]["value"] == "c2.badactor.example"
    third = events[2]["attrs"]["threat"]
    assert {i["type"] for i in third["indicators"]} == {"url", "hash"} and third["max_confidence"] == 80
    assert "threat" not in events[3]["attrs"]
    assert stats == {"events": 4, "matched": 3}


def test_url_hosts_are_checked_as_domains():
    events = [{"attrs": {"url": "https://cdn.c2.badactor.example/x.js"}}]
    enrich(events)
    assert events[0]["attrs"]["threat"]["indicators"][0]["field"] == "url.host"


def test_top_level_fields_count_too():
    events = [{"src_ip": "162.243.103.246", "attrs": {}}]
    enrich(events)
    assert events[0]["attrs"]["threat"]["indicators"][0]["field"] == "src_ip"


def test_tenants_without_indicators_are_untouched():
    events = [{"src_ip": "162.243.103.246", "attrs": {}}]
    assert enrich(events, tenant="other") == {"events": 1, "matched": 0}
    assert events[0]["attrs"] == {}


def test_index_failures_never_fail_ingestion():
    async def broken(tenant_id, now):
        raise ConnectionError("clickhouse down")
    events = [{"src_ip": "162.243.103.246", "attrs": {}}]
    assert enrich(events, idx=IndicatorIndex(loader=broken)) == {"events": 1, "matched": 0, "error": "clickhouse down"}


def test_events_without_attrs_get_them():
    events = [{"src_ip": "162.243.103.246"}]
    enrich(events)
    assert events[0]["attrs"]["threat"]["matched"] is True


def test_rules_can_match_the_stamp_through_attrs():
    events = [{"src_ip": "10.0.1.15", "attrs": {"dst_ip": "162.243.103.246"}}]
    enrich(events)
    evaluator = SigmaConditionEvaluator()
    assert evaluator.evaluate_selection(events[0], {"threat.matched": True})[0]
    assert evaluator.evaluate_selection(events[0], {"threat.max_confidence|gte": 80})[0]
    assert not evaluator.evaluate_selection({"attrs": {}}, {"threat.matched": True})[0]
