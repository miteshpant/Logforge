"""
Phase 3 acceptance: threat-intel matching on a replayed corpus.

The detection harness enriches every event with the real ingest-time
matcher (ingest_enrichment.enrich_events) and an indicator set parsed from
the abuse.ch feed fixtures (Feodo Tracker captured live; URLhaus and
ThreatFox in their API formats). Then:

* the intel scenarios (traffic to Feodo C2s, a URLhaus download, a DNS
  lookup of a ThreatFox C2 domain) are detected by the lf-ti rules;
* nothing in the benign corpus matches an indicator, and neither do near
  misses: a neighbouring address, the parent of a listed domain, another
  path on a host whose URL is listed. The fixtures list no benign values, so
  the allowed error rate is zero.
"""

import eval_harness
from benign import benign_events

INTEL_SCENARIOS = {"c2-beacon-feodo": "logforge_lf-ti-known-c2",
                   "malware-download-urlhaus": "logforge_lf-ti-malware-delivery",
                   "dns-threatfox-c2": "logforge_lf-ti-known-c2"}
NEAR_MISSES = [
    {"service": "netflow", "src_ip": "10.0.1.20", "dst_ip": "50.16.16.212", "event_type": "network_connection"},
    {"service": "dns", "src_ip": "10.0.1.20", "query": "badactor.example", "event_type": "dns_query"},
    {"service": "proxy", "src_ip": "10.0.1.20", "url": "https://malware-drop.example.net/about.html"},
]


def test_feed_fixtures_build_an_index():
    sets = eval_harness.intel_sets()
    assert {"ip", "url", "domain"} <= set(sets)
    assert "50.16.16.211" in sets["ip"] and "c2.badactor.example" in sets["domain"]


def test_intel_scenarios_are_detected_by_the_intel_rules():
    report = eval_harness.run()
    for scenario_id, rule_id in INTEL_SCENARIOS.items():
        result = report["scenarios"][scenario_id]
        assert rule_id in result["rules"], (scenario_id, result)
        assert result["missing"] == [], (scenario_id, result)


def test_no_benign_event_or_near_miss_matches_an_indicator():
    events = eval_harness.enrich(benign_events() + [dict(e) for e in NEAR_MISSES])
    matched = [e for e in events if (e.get("attrs") or {}).get("threat")]
    assert matched == []


def test_intel_rules_raise_no_false_positives():
    report = eval_harness.run()
    for rule_id in set(INTEL_SCENARIOS.values()):
        assert report["rules"][rule_id]["false_positives"] == 0
