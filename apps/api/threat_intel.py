"""
Threat-intelligence enrichment at detection time (ENH-022).

`threat_intel_mt` exists (`init_simple.sql:617`) and a `ThreatIntelHandler`
stores IOCs, but nothing ever **matched** a log against them: there was no feed
ingestion and no lookup in the detection path. Known-bad indicators passed
through unflagged, which is table stakes for every competing SIEM.

Design
------
* **Lookup is O(1) per field** against a Redis-backed IOC set, so enrichment can
  sit on the hot detection path without adding a database round trip per log.
* **Feed fetching is behind an injectable `FeedSource`.** Network I/O is a
  parameter, not a hard-coded HTTP call, so the parsing, normalisation, matching
  and storage logic are all exercised offline. Shipping untested integration
  code is how feeds silently rot.
* **Enrichment never fails a detection.** If the IOC store is unavailable the
  log passes through un-enriched and the failure is logged. A threat-intel
  outage must not stop security events from being written -- losing detections
  is far worse than losing enrichment.
* **Indicator values are normalised** (lowercased, defanged forms expanded) so
  `hxxp://EVIL[.]com` matches `http://evil.com`.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)

# Log fields inspected for indicators, mapped to the IOC type they can carry.
DEFAULT_FIELD_MAP: Dict[str, str] = {
    "src_ip": "ip",
    "dest_ip": "ip",
    "dst_ip": "ip",
    "remote_addr": "ip",
    "client_ip": "ip",
    "domain": "domain",
    "hostname": "domain",
    "url": "url",
    "http_uri": "url",
    "file_hash": "hash",
    "hash": "hash",
    "md5": "hash",
    "sha256": "hash",
    "email": "email",
    "filename": "filename",
}

# "Defanged" indicator forms used in threat reports so links are not clickable.
_DEFANG_PATTERNS = (
    (re.compile(r"\[\.\]"), "."),
    (re.compile(r"\(\.\)"), "."),
    (re.compile(r"^hxxp", re.IGNORECASE), "http"),
    (re.compile(r"\[:\]"), ":"),
)


def normalize_indicator(value: Any) -> str:
    """
    Normalise an indicator so feed and log forms compare equal.

    Threat feeds routinely publish defanged indicators (`evil[.]com`,
    `hxxp://...`) while logs contain the live form. Without this they would
    never match.
    """
    if value is None:
        return ""

    text = str(value).strip().lower()
    for pattern, replacement in _DEFANG_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


@dataclass(frozen=True)
class Indicator:
    """A single indicator of compromise."""

    value: str
    indicator_type: str
    threat_type: str = "malware"
    confidence: int = 50
    source: str = "unknown"
    tags: List[str] = field(default_factory=list)

    def normalized(self) -> str:
        return normalize_indicator(self.value)


@dataclass(frozen=True)
class IOCMatch:
    """A log field that matched a known indicator."""

    field_name: str
    value: str
    indicator: Indicator

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field_name,
            "value": self.value,
            "indicator_type": self.indicator.indicator_type,
            "threat_type": self.indicator.threat_type,
            "confidence": self.indicator.confidence,
            "source": self.indicator.source,
            "tags": list(self.indicator.tags),
        }


class FeedSource(Protocol):
    """
    A source of indicators.

    Deliberately abstract: an HTTP/MISP/STIX client is one implementation, and a
    static list is another. Keeping network I/O behind this boundary is what
    lets everything else be tested without a network.
    """

    name: str

    async def fetch(self) -> Iterable[Indicator]:
        ...


class StaticFeedSource:
    """A feed backed by an in-memory list (tests, and local allow/deny lists)."""

    def __init__(self, name: str, indicators: Iterable[Indicator]):
        self.name = name
        self._indicators = list(indicators)

    async def fetch(self) -> Iterable[Indicator]:
        return list(self._indicators)


def parse_feed_payload(
    payload: str,
    source_name: str,
    default_type: str = "ip",
) -> List[Indicator]:
    """
    Parse a feed payload into indicators.

    Accepts the two formats feeds actually ship:
      * JSON: a list of objects, or {"indicators": [...]}
      * Plain text: one indicator per line, `#` comments ignored

    Unparseable entries are skipped rather than aborting the whole feed -- one
    malformed line must not discard thousands of good indicators.
    """
    indicators: List[Indicator] = []
    text = (payload or "").strip()
    if not text:
        return indicators

    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Feed payload is not valid JSON", source=source_name, error=str(exc))
            return indicators

        entries = data.get("indicators", []) if isinstance(data, dict) else data
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            value = entry.get("value") or entry.get("indicator")
            if not value:
                continue
            indicators.append(
                Indicator(
                    value=str(value),
                    indicator_type=str(
                        entry.get("type") or entry.get("indicator_type") or default_type
                    ),
                    threat_type=str(entry.get("threat_type", "malware")),
                    confidence=int(entry.get("confidence", 50)),
                    source=source_name,
                    tags=[str(t) for t in (entry.get("tags") or [])],
                )
            )
        return indicators

    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        indicators.append(
            Indicator(
                value=candidate,
                indicator_type=infer_indicator_type(candidate, default_type),
                source=source_name,
            )
        )

    return indicators


def infer_indicator_type(value: str, fallback: str = "ip") -> str:
    """Infer an indicator's type from its shape."""
    candidate = normalize_indicator(value)

    try:
        ipaddress.ip_address(candidate)
        return "ip"
    except ValueError:
        pass

    if candidate.startswith(("http://", "https://")):
        return "url"
    if "@" in candidate:
        return "email"
    if re.fullmatch(r"[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64}", candidate):
        return "hash"
    if "." in candidate and " " not in candidate:
        return "domain"
    return fallback


class ThreatIntelStore:
    """
    Redis-backed IOC lookup.

    A hash keyed by `type:value` gives O(1) membership tests, so enrichment adds
    no database round trip per log.
    """

    KEY = "threatintel:indicators"

    def __init__(self, redis_manager=None):
        self._redis = redis_manager

    async def _client(self):
        if self._redis is None:
            from events.management.cache.redis_manager import get_redis_manager

            self._redis = await get_redis_manager()
        return getattr(self._redis, "client", None) or self._redis

    @staticmethod
    def _field(indicator_type: str, value: str) -> str:
        return f"{indicator_type}:{normalize_indicator(value)}"

    async def load(self, indicators: Iterable[Indicator]) -> int:
        """Replace-or-insert indicators. Returns the number stored."""
        indicators = list(indicators)
        if not indicators:
            return 0

        client = await self._client()
        stored = 0
        for indicator in indicators:
            await client.hset(
                self.KEY,
                self._field(indicator.indicator_type, indicator.value),
                json.dumps(
                    {
                        "value": indicator.value,
                        "indicator_type": indicator.indicator_type,
                        "threat_type": indicator.threat_type,
                        "confidence": indicator.confidence,
                        "source": indicator.source,
                        "tags": indicator.tags,
                    }
                ),
            )
            stored += 1
        return stored

    async def lookup(self, indicator_type: str, value: str) -> Optional[Indicator]:
        """Return the matching indicator, or None."""
        client = await self._client()
        raw = await client.hget(self.KEY, self._field(indicator_type, value))
        if raw is None:
            return None

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        return Indicator(
            value=data["value"],
            indicator_type=data["indicator_type"],
            threat_type=data.get("threat_type", "malware"),
            confidence=int(data.get("confidence", 50)),
            source=data.get("source", "unknown"),
            tags=list(data.get("tags", [])),
        )


class ThreatIntelEnricher:
    """Matches log fields against known indicators."""

    def __init__(
        self,
        store: Optional[ThreatIntelStore] = None,
        field_map: Optional[Dict[str, str]] = None,
    ):
        self.store = store or ThreatIntelStore()
        self.field_map = field_map or dict(DEFAULT_FIELD_MAP)

    async def match(self, log_entry: Dict[str, Any]) -> List[IOCMatch]:
        """
        Find indicators present in a log entry.

        Returns an empty list on any store failure: enrichment must never fail
        a detection. Losing enrichment is a degraded signal; losing the
        detection itself would be a security incident.
        """
        matches: List[IOCMatch] = []

        for field_name, indicator_type in self.field_map.items():
            value = log_entry.get(field_name)
            if not value:
                continue

            try:
                indicator = await self.store.lookup(indicator_type, value)
            except Exception as exc:
                logger.warning(
                    "Threat intel lookup failed; continuing without enrichment",
                    field=field_name,
                    error=str(exc),
                )
                continue

            if indicator is not None:
                matches.append(
                    IOCMatch(
                        field_name=field_name,
                        value=str(value),
                        indicator=indicator,
                    )
                )

        return matches

    async def enrich(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return an enrichment block for a log entry.

        `threat_score` is the highest confidence among matches, so a single
        high-confidence IOC is not diluted by low-confidence ones -- averaging
        would let a genuine C2 hit be buried.
        """
        matches = await self.match(log_entry)

        if not matches:
            return {"threat_intel_matched": False, "matches": [], "threat_score": 0}

        return {
            "threat_intel_matched": True,
            "matches": [m.to_dict() for m in matches],
            "threat_score": max(m.indicator.confidence for m in matches),
            "threat_types": sorted({m.indicator.threat_type for m in matches}),
            "enriched_at": datetime.now(timezone.utc).isoformat(),
        }


class FeedIngestor:
    """Pulls indicators from configured feeds into the store."""

    def __init__(
        self,
        store: Optional[ThreatIntelStore] = None,
        sources: Optional[List[FeedSource]] = None,
    ):
        self.store = store or ThreatIntelStore()
        self.sources = sources or []

    async def refresh(self) -> Dict[str, Any]:
        """
        Refresh all feeds.

        One failing feed must not prevent the others from loading -- a single
        unreachable provider should not blind the whole platform.
        """
        results: Dict[str, Any] = {"loaded": 0, "sources": {}, "errors": {}}

        for source in self.sources:
            try:
                indicators = list(await source.fetch())
                count = await self.store.load(indicators)
                results["sources"][source.name] = count
                results["loaded"] += count
            except Exception as exc:
                logger.error(
                    "Threat feed refresh failed", source=source.name, error=str(exc)
                )
                results["errors"][source.name] = str(exc)

        return results


_enricher: Optional[ThreatIntelEnricher] = None


def get_threat_intel_enricher() -> ThreatIntelEnricher:
    """Get the shared enricher, constructing it on first use."""
    global _enricher
    if _enricher is None:
        _enricher = ThreatIntelEnricher()
    return _enricher


def reset_threat_intel() -> None:
    """Reset the singleton (tests only)."""
    global _enricher
    _enricher = None


def is_enabled() -> bool:
    """Enrichment is opt-in until feeds are configured for a deployment."""
    return os.getenv("THREAT_INTEL_ENABLED", "false").strip().lower() in {
        "true", "1", "yes"
    }
