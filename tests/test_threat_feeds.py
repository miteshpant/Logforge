"""
Threat feed parsers (Phase 3).

parse_feed(kind, payload, source=...) turns a provider's payload into
indicators of the canonical types ip, domain, url, hash, email:

* abuse.ch Feodo (JSON and plain list), URLhaus API, ThreatFox API,
  AlienVault OTX pulses, MISP attribute search (to_ids only), STIX 2.1
  bundles (stix patterns), CSV (configurable columns) and plain lists;
* values are normalised (defanged forms, case), ports are stripped from
  ip:port, invalid values and private/loopback addresses are dropped (a feed
  listing 10.0.0.5 would flag internal traffic);
* duplicates within a payload merge: highest confidence, tags combined.
"""

import json
from pathlib import Path

import pytest

from threat_feeds import FeedParseError, dedupe, parse_feed

FIXTURES = Path(__file__).parent / "fixtures" / "threat_feeds"


def load(name):
    return (FIXTURES / name).read_text()


def by_value(indicators):
    return {i.normalized(): i for i in indicators}


def test_feodo_json_captured_live():
    indicators = parse_feed("feodo_json", load("feodo_ipblocklist.json"), source="feodo")
    assert len(indicators) == len(json.loads(load("feodo_ipblocklist.json")))
    first = indicators[0]
    assert first.indicator_type == "ip" and first.threat_type == "botnet_cc"
    assert "emotet" in [t.lower() for t in first.tags] and first.source == "feodo"


def test_plain_lists_skip_comments():
    indicators = parse_feed("plain", load("feodo_ipblocklist.txt"), source="feodo-txt")
    assert indicators and all(i.indicator_type == "ip" for i in indicators)
    assert not any(i.value.startswith("#") for i in indicators)


def test_urlhaus_api():
    indicators = by_value(parse_feed("urlhaus", load("urlhaus_recent.json"), source="urlhaus"))
    url = indicators["http://198.51.100.66/bins/mozi.m"]
    assert url.indicator_type == "url" and url.threat_type == "malware_download" and "mozi" in url.tags
    assert "https://malware-drop.example.net/invoice.zip" in indicators


def test_threatfox_api():
    indicators = by_value(parse_feed("threatfox", load("threatfox_iocs.json"), source="threatfox"))
    c2 = indicators["203.0.113.66"]  # ip:port -> ip
    assert c2.indicator_type == "ip" and c2.confidence == 100 and c2.threat_type == "botnet_cc"
    assert "Cobalt Strike" in c2.tags
    assert indicators["c2.badactor.example"].indicator_type == "domain"
    assert indicators["44d88612fea8a8f36de82e1278abb02f"].indicator_type == "hash"
    assert indicators["http://evil.example/gate.php"].confidence == 90


def test_otx_pulses_keep_known_types_only():
    indicators = by_value(parse_feed("otx", load("otx_pulses.json"), source="otx"))
    assert set(indicators) == {"login-secure-update.example", "192.0.2.77",
                               "https://login-secure-update.example/office365/",
                               "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
    assert "phishing" in indicators["192.0.2.77"].tags


def test_misp_uses_ids_attributes_only():
    indicators = by_value(parse_feed("misp", load("misp_attributes.json"), source="misp"))
    assert set(indicators) == {"203.0.113.200", "exfil.example.org", "198.51.100.9"}


def test_stix_bundle_patterns_and_expiry():
    indicators = by_value(parse_feed("stix", load("stix_bundle.json"), source="taxii"))
    assert set(indicators) == {"198.51.100.23", "stix-c2.example", "http://stix-c2.example/a",
                               "aec070645fe53ee3b3763059376134f058cc337247c978add178b6ccdfb0019f"}
    ip = indicators["198.51.100.23"]
    assert ip.confidence == 80 and ip.expires_at is not None and ip.expires_at.year == 2027


def test_csv_with_column_mapping_drops_private_and_invalid():
    indicators = by_value(parse_feed("csv", load("custom.csv"), source="local",
                                     options={"value_column": "indicator", "type_column": "kind"}))
    assert set(indicators) == {"203.0.113.5", "bad-domain.example"}


def test_defanged_values_are_normalised():
    indicators = parse_feed("plain", "hxxp://evil[.]example/x\nbad[.]example\n", source="report")
    assert {i.normalized() for i in indicators} == {"http://evil.example/x", "bad.example"}


def test_private_and_loopback_addresses_are_dropped():
    indicators = parse_feed("plain", "10.1.2.3\n127.0.0.1\n192.168.1.1\n::1\n8.8.8.8\n", source="x")
    assert [i.value for i in indicators] == ["8.8.8.8"]


def test_dedupe_merges_confidence_and_tags():
    a = parse_feed("plain", "203.0.113.9", source="a", confidence=40)[0]
    b = parse_feed("plain", "203.0.113.9", source="a", confidence=90)[0]
    merged = dedupe([a, b])
    assert len(merged) == 1 and merged[0].confidence == 90


def test_bad_payloads_raise_a_parse_error():
    with pytest.raises(FeedParseError, match="not valid JSON"):
        parse_feed("threatfox", "<html>410 Gone</html>", source="threatfox")
    with pytest.raises(FeedParseError, match="query_status"):
        parse_feed("threatfox", '{"query_status": "unknown_auth_key"}', source="threatfox")
    with pytest.raises(FeedParseError, match="unknown feed kind"):
        parse_feed("gopher", "", source="x")
