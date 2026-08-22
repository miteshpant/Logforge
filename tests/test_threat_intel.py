"""
Tests for ENH-022 -- threat-intelligence enrichment at detection time.

`threat_intel_mt` existed and a handler stored IOCs, but nothing ever MATCHED a
log against them: no feed ingestion, no lookup in the detection path. Known-bad
indicators passed through unflagged, which every competing SIEM does out of the
box.

Network I/O sits behind an injectable `FeedSource`, so parsing, normalisation,
matching, storage and the detection-path integration are all tested here without
a network or a database.
"""

import json

import pytest

from threat_intel import (
    FeedIngestor,
    Indicator,
    StaticFeedSource,
    ThreatIntelEnricher,
    ThreatIntelStore,
    infer_indicator_type,
    normalize_indicator,
    parse_feed_payload,
    reset_threat_intel,
)


class _FakeRedisClient:
    def __init__(self, fail=False):
        self.hashes = {}
        self.fail = fail

    async def hset(self, key, field, value):
        if self.fail:
            raise ConnectionError("redis down")
        self.hashes.setdefault(key, {})[field] = value
        return 1

    async def hget(self, key, field):
        if self.fail:
            raise ConnectionError("redis down")
        return self.hashes.get(key, {}).get(field)


class _FakeRedisManager:
    def __init__(self, fail=False):
        self.client = _FakeRedisClient(fail=fail)


@pytest.fixture(autouse=True)
def clean():
    reset_threat_intel()
    yield
    reset_threat_intel()


def _store(fail=False):
    return ThreatIntelStore(redis_manager=_FakeRedisManager(fail=fail))


BAD_IP = Indicator(
    value="203.0.113.66",
    indicator_type="ip",
    threat_type="c2",
    confidence=95,
    source="test-feed",
    tags=["apt"],
)


# ---------------------------------------------------------------------------
# Normalisation -- feeds and logs must compare equal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("EVIL.COM", "evil.com"),
        ("evil[.]com", "evil.com"),
        ("evil(.)com", "evil.com"),
        ("hxxp://evil.com", "http://evil.com"),
        ("hxxp://evil[.]com", "http://evil.com"),
        ("  1.2.3.4  ", "1.2.3.4"),
        (None, ""),
    ],
)
def test_indicator_normalisation(raw, expected):
    """
    Threat feeds publish DEFANGED indicators so links are not clickable, while
    logs contain the live form. Without normalisation they would never match --
    the feed would appear loaded but detect nothing.
    """
    assert normalize_indicator(raw) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("8.8.8.8", "ip"),
        ("2001:db8::1", "ip"),
        ("http://evil.com/x", "url"),
        ("user@evil.com", "email"),
        ("d41d8cd98f00b204e9800998ecf8427e", "hash"),
        ("a" * 64, "hash"),
        ("evil.com", "domain"),
    ],
)
def test_indicator_type_inference(value, expected):
    assert infer_indicator_type(value) == expected


# ---------------------------------------------------------------------------
# Feed parsing
# ---------------------------------------------------------------------------


def test_parses_plain_text_feed():
    indicators = parse_feed_payload("1.2.3.4\n5.6.7.8\n", "feed-a")

    assert [i.value for i in indicators] == ["1.2.3.4", "5.6.7.8"]
    assert all(i.source == "feed-a" for i in indicators)


def test_plain_text_comments_are_ignored():
    indicators = parse_feed_payload("# header\n1.2.3.4\n\n# note\n", "feed-a")
    assert [i.value for i in indicators] == ["1.2.3.4"]


def test_parses_json_list_feed():
    payload = json.dumps(
        [{"value": "evil.com", "type": "domain", "confidence": 80}]
    )
    indicators = parse_feed_payload(payload, "feed-b")

    assert indicators[0].indicator_type == "domain"
    assert indicators[0].confidence == 80


def test_parses_json_object_feed():
    payload = json.dumps({"indicators": [{"indicator": "1.2.3.4", "type": "ip"}]})
    assert parse_feed_payload(payload, "feed-c")[0].value == "1.2.3.4"


def test_malformed_entries_do_not_discard_the_whole_feed():
    """One bad line must not throw away thousands of good indicators."""
    payload = json.dumps(
        [{"value": "good.com", "type": "domain"}, {"no_value": True}, "not-an-object"]
    )
    assert len(parse_feed_payload(payload, "feed-d")) == 1


def test_invalid_json_returns_no_indicators_rather_than_raising():
    assert parse_feed_payload("{not json", "feed-e") == []


def test_empty_payload_is_handled():
    assert parse_feed_payload("", "feed-f") == []


# ---------------------------------------------------------------------------
# Store and lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_indicators_can_be_stored_and_retrieved():
    store = _store()
    await store.load([BAD_IP])

    found = await store.lookup("ip", "203.0.113.66")

    assert found is not None
    assert found.threat_type == "c2"
    assert found.confidence == 95


@pytest.mark.asyncio
async def test_lookup_of_unknown_indicator_returns_none():
    store = _store()
    await store.load([BAD_IP])

    assert await store.lookup("ip", "10.0.0.1") is None


@pytest.mark.asyncio
async def test_lookup_matches_defanged_feed_entries():
    """A defanged feed entry must match the live value seen in a log."""
    store = _store()
    await store.load(
        [Indicator(value="evil[.]com", indicator_type="domain", source="f")]
    )

    assert await store.lookup("domain", "evil.com") is not None


@pytest.mark.asyncio
async def test_lookup_is_case_insensitive():
    store = _store()
    await store.load([Indicator(value="EVIL.COM", indicator_type="domain")])

    assert await store.lookup("domain", "evil.com") is not None


@pytest.mark.asyncio
async def test_type_is_part_of_the_key():
    """An IP and a domain with the same text must not collide."""
    store = _store()
    await store.load([Indicator(value="1.2.3.4", indicator_type="ip")])

    assert await store.lookup("domain", "1.2.3.4") is None


# ---------------------------------------------------------------------------
# Matching against logs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_with_known_bad_ip_is_matched():
    store = _store()
    await store.load([BAD_IP])
    enricher = ThreatIntelEnricher(store=store)

    matches = await enricher.match({"src_ip": "203.0.113.66", "msg": "hello"})

    assert len(matches) == 1
    assert matches[0].field_name == "src_ip"
    assert matches[0].indicator.threat_type == "c2"


@pytest.mark.asyncio
async def test_clean_log_produces_no_matches():
    store = _store()
    await store.load([BAD_IP])
    enricher = ThreatIntelEnricher(store=store)

    assert await enricher.match({"src_ip": "10.0.0.5"}) == []


@pytest.mark.asyncio
async def test_multiple_fields_are_inspected():
    store = _store()
    await store.load(
        [BAD_IP, Indicator(value="evil.com", indicator_type="domain", confidence=70)]
    )
    enricher = ThreatIntelEnricher(store=store)

    matches = await enricher.match(
        {"src_ip": "203.0.113.66", "domain": "evil.com"}
    )

    assert {m.field_name for m in matches} == {"src_ip", "domain"}


@pytest.mark.asyncio
async def test_enrichment_reports_the_highest_confidence():
    """
    Averaging would let a high-confidence C2 hit be diluted by low-confidence
    matches and drop below an alerting threshold.
    """
    store = _store()
    await store.load(
        [
            BAD_IP,  # confidence 95
            Indicator(value="evil.com", indicator_type="domain", confidence=20),
        ]
    )
    enricher = ThreatIntelEnricher(store=store)

    result = await enricher.enrich({"src_ip": "203.0.113.66", "domain": "evil.com"})

    assert result["threat_score"] == 95


@pytest.mark.asyncio
async def test_enrichment_of_a_clean_log_is_explicit():
    store = _store()
    enricher = ThreatIntelEnricher(store=store)

    result = await enricher.enrich({"src_ip": "10.0.0.1"})

    assert result["threat_intel_matched"] is False
    assert result["threat_score"] == 0


# ---------------------------------------------------------------------------
# Failure must never break detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_failure_yields_no_matches_rather_than_raising():
    """
    A threat-intel outage must not stop security events being written. Losing
    enrichment is a degraded signal; losing the detection is an incident.
    """
    enricher = ThreatIntelEnricher(store=_store(fail=True))

    assert await enricher.match({"src_ip": "203.0.113.66"}) == []


@pytest.mark.asyncio
async def test_enrichment_survives_a_store_outage():
    enricher = ThreatIntelEnricher(store=_store(fail=True))

    result = await enricher.enrich({"src_ip": "203.0.113.66"})

    assert result["threat_intel_matched"] is False


# ---------------------------------------------------------------------------
# Feed ingestion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feeds_are_loaded_into_the_store():
    store = _store()
    ingestor = FeedIngestor(
        store=store, sources=[StaticFeedSource("feed-a", [BAD_IP])]
    )

    result = await ingestor.refresh()

    assert result["loaded"] == 1
    assert await store.lookup("ip", "203.0.113.66") is not None


@pytest.mark.asyncio
async def test_one_failing_feed_does_not_block_the_others():
    """A single unreachable provider must not blind the whole platform."""

    class _BrokenFeed:
        name = "broken"

        async def fetch(self):
            raise ConnectionError("provider unreachable")

    store = _store()
    ingestor = FeedIngestor(
        store=store,
        sources=[_BrokenFeed(), StaticFeedSource("good", [BAD_IP])],
    )

    result = await ingestor.refresh()

    assert "broken" in result["errors"]
    assert result["sources"]["good"] == 1
    assert await store.lookup("ip", "203.0.113.66") is not None


# ---------------------------------------------------------------------------
# Detection-path integration
# ---------------------------------------------------------------------------


def test_detection_path_builds_enrichment():
    import inspect

    from events.management.processors.sigma_processor import SigmaProcessor

    source = inspect.getsource(SigmaProcessor._build_enrichment)

    assert "threat_intel" in source
    assert "matched_fields" in source, (
        "Sigma matched fields must be preserved alongside IOC enrichment."
    )


@pytest.mark.asyncio
async def test_enrichment_failure_does_not_fail_a_detection():
    """The integration must swallow enrichment errors, not propagate them."""
    from events.management.processors.sigma_processor import SigmaProcessor

    processor = SigmaProcessor.__new__(SigmaProcessor)

    class _Match:
        matched_fields = {"src_ip": {"log_value": "1.2.3.4"}}
        log_entry = {"src_ip": "1.2.3.4"}

    result = await processor._build_enrichment(_Match())

    assert result["matched_fields"] == {"src_ip": {"log_value": "1.2.3.4"}}


def test_enrichment_is_opt_in(monkeypatch):
    """Until feeds are configured, enrichment stays off."""
    from threat_intel import is_enabled

    monkeypatch.delenv("THREAT_INTEL_ENABLED", raising=False)
    assert is_enabled() is False

    monkeypatch.setenv("THREAT_INTEL_ENABLED", "true")
    assert is_enabled() is True
