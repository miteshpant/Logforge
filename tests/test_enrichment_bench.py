"""
Enrichment benchmark (Phase 3 acceptance: ingest throughput drops by less
than 10% with threat-intel matching on). The live runner needs a stack;
these tests pin the deterministic parts.
"""

import asyncio

import pytest

import enrichment_bench as bench
from threat_feeds import clean


def test_synthetic_indicators_are_public_unique_and_mixed():
    indicators = bench.synthetic_indicators(3000)
    assert len({(i.indicator_type, i.normalized()) for i in indicators}) == 3000
    assert {i.indicator_type for i in indicators} == {"ip", "domain", "url"}
    assert all(clean(i.value, i.indicator_type) for i in indicators[:300])  # survive the feed filter
    assert bench.synthetic_indicators(10)[0] == bench.synthetic_indicators(10)[0]


def test_traffic_hits_indicators_at_the_requested_rate():
    indicators = bench.synthetic_indicators(5000)
    events = bench.traffic(2000, "r1", indicators, hit_rate=0.01)
    stats = asyncio.run(bench.enrich(events, indicators))
    assert stats["events"] == 2000
    assert 10 <= stats["matched"] <= 40


def test_drop_is_relative_to_the_baseline():
    result = bench.compare({"events_per_second": 1000.0}, {"events_per_second": 940.0}, limit_pct=10)
    assert result == {"off_eps": 1000.0, "on_eps": 940.0, "drop_pct": 6.0, "limit_pct": 10, "pass": True}
    assert bench.compare({"events_per_second": 1000.0}, {"events_per_second": 850.0})["pass"] is False
    assert bench.compare({"events_per_second": 1000.0}, {"events_per_second": 1010.0})["drop_pct"] == pytest.approx(-1.0)
