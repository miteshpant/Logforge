"""
Enrichment processors (Phase 3), applied at ingest next to threat intel:

* GeoIP and ASN from DB-IP Lite CSV range files (GEOIP_CITY_CSV,
  GEOIP_ASN_CSV): attrs.geo.<ip field> = {country, region, city, continent,
  asn, as_org}; internal addresses are skipped.
* Asset and user lookups from CSV (ASSETS_CSV keyed by host, USERS_CSV keyed
  by user): attrs.asset, attrs.identity; keys match case-insensitively.
* Reverse DNS (REVERSE_DNS=on): attrs.rdns.<ip field>, cached; off by default.
"""

import asyncio
from pathlib import Path

import pytest

from enrichment_processors import AssetLookup, Enrichers, GeoIP, ReverseDNS
from ingest_enrichment import enrich_events
from threat_intel_store import IndicatorIndex

FIX = Path(__file__).parent / "fixtures" / "enrichment"


@pytest.fixture
def geo():
    return GeoIP.from_files(city=FIX / "dbip-city-lite.csv", asn=FIX / "dbip-asn-lite.csv")


def test_geoip_ranges_v4_and_v6(geo):
    assert geo.lookup("50.16.16.211") == {"continent": "NA", "country": "US", "region": "Virginia",
                                          "city": "Ashburn", "asn": 14618, "as_org": "AMAZON-AES"}
    assert geo.lookup("2001:db8::1")["country"] == "DE"
    assert geo.lookup("8.8.8.8") is None
    assert geo.lookup("10.0.1.15") is None and geo.lookup("not an ip") is None
    assert geo.size() == (5, 3)


def test_asset_and_user_lookups():
    assets = AssetLookup.from_csv(FIX / "assets.csv", key="host")
    assert assets.lookup("ws-044") == {"owner": "carol", "criticality": "medium", "environment": "corp"}
    assert assets.lookup("unknown") is None
    users = AssetLookup.from_csv(FIX / "users.csv", key="user")
    assert users.lookup("OPS_ADMIN")["privileged"] == "true"


def test_reverse_dns_is_cached_and_skips_internal():
    calls = []

    def resolver(ip):
        calls.append(ip)
        return "ec2-50-16-16-211.compute-1.amazonaws.com"

    rdns = ReverseDNS(resolver=resolver)
    assert rdns.lookup("50.16.16.211") == "ec2-50-16-16-211.compute-1.amazonaws.com"
    rdns.lookup("50.16.16.211")
    assert calls == ["50.16.16.211"] and rdns.lookup("10.0.0.1") is None


def test_enrichers_from_environment(monkeypatch):
    assert not Enrichers.from_env({})
    env = {"GEOIP_CITY_CSV": str(FIX / "dbip-city-lite.csv"), "ASSETS_CSV": str(FIX / "assets.csv"),
           "USERS_CSV": str(FIX / "users.csv")}
    enrichers = Enrichers.from_env(env)
    assert enrichers.geo and enrichers.assets and enrichers.users and enrichers.rdns is None


def run(events, enrichers):
    async def empty(tenant_id, now):
        return []
    return asyncio.run(enrich_events("acme", events, IndicatorIndex(loader=empty), enrichers=enrichers))


def test_events_are_stamped(geo):
    enrichers = Enrichers(geo=geo, assets=AssetLookup.from_csv(FIX / "assets.csv", key="host"),
                          users=AssetLookup.from_csv(FIX / "users.csv", key="user"))
    events = [{"src_ip": "10.0.1.15", "host": "WS-044", "attrs": {"dst_ip": "50.16.16.211", "user": "carol"}},
              {"src_ip": "203.0.113.9", "attrs": {}}]
    run(events, enrichers)
    first = events[0]["attrs"]
    assert first["geo"] == {"dst_ip": {"continent": "NA", "country": "US", "region": "Virginia", "city": "Ashburn",
                                       "asn": 14618, "as_org": "AMAZON-AES"}}
    assert first["asset"]["criticality"] == "medium" and first["identity"]["department"] == "Finance"
    assert events[1]["attrs"]["geo"]["src_ip"]["country"] == "JP"
    assert "asset" not in events[1]["attrs"]


def test_reverse_dns_stamp():
    enrichers = Enrichers(rdns=ReverseDNS(resolver=lambda ip: "host.example"))
    events = [{"src_ip": "50.16.16.211", "attrs": {}}]
    run(events, enrichers)
    assert events[0]["attrs"]["rdns"] == {"src_ip": "host.example"}
