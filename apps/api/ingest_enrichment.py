"""
Ingest-time enrichment (Phase 3): threat intelligence matches stamped onto
events before they are stored and evaluated.

Each event's IPs, domains, URLs (and their hosts), hashes and emails, from
model fields and attrs, are looked up in the tenant's indicator index
(threat_intel_store.IndicatorIndex, in memory). Matches are written to
attrs.threat:

    {"matched": true, "max_confidence": 90, "threat_types": [...],
     "indicators": [{"field", "value", "type", "threat_type", "confidence",
                     "source", "tags"}]}

so they are searchable, visible on the event, and usable by rules
(`threat.matched: true`). Enrichment never fails ingestion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlsplit

import structlog

from threat_intel_store import IndicatorIndex, get_indicator_index

logger = structlog.get_logger(__name__)

FIELDS = {
    "ip": ("src_ip", "dst_ip", "dest_ip", "remote_addr", "client_ip", "server_ip", "ip"),
    "domain": ("domain", "query", "dns_query", "server_name", "sni", "dest_domain"),
    "url": ("url", "http_uri", "request_url", "referrer"),
    "hash": ("md5", "sha1", "sha256", "hash", "file_hash"),
    "email": ("email", "sender", "recipient", "from_address"),
}
MAX_MATCHES = 10


def _values(event: Dict[str, Any], name: str) -> List[Any]:
    attrs = event.get("attrs") if isinstance(event.get("attrs"), dict) else {}
    found = []
    for source in (event, attrs):
        value = source.get(name)
        if value not in (None, "") and value not in found:
            found.append(value)
    return found


def _matches(sets, event: Dict[str, Any], now: datetime) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    seen = set()

    def add(field: str, kind: str, value: Any) -> None:
        indicator = IndicatorIndex.find(sets, kind, value, now)
        if indicator is None or (kind, indicator.normalized()) in seen:
            return
        seen.add((kind, indicator.normalized()))
        hits.append({"field": field, "value": indicator.value, "type": kind, "threat_type": indicator.threat_type,
                     "confidence": indicator.confidence, "source": indicator.source, "tags": list(indicator.tags)})

    for kind, names in FIELDS.items():
        if kind not in sets:
            continue
        for name in names:
            for value in _values(event, name):
                add(name, kind, value)
    if "domain" in sets:
        for name in FIELDS["url"]:
            for value in _values(event, name):
                host = urlsplit(str(value)).hostname
                if host:
                    add("url.host", "domain", host)
    return hits[:MAX_MATCHES]


HOST_FIELDS = ("host", "hostname")
USER_FIELDS = ("user", "user_id", "username")


def _first(event: Dict[str, Any], names) -> Any:
    for name in names:
        for value in _values(event, name):
            return value
    return None


def _process(event: Dict[str, Any], enrichers) -> None:
    attrs = event.setdefault("attrs", {})
    if not isinstance(attrs, dict):
        return
    if enrichers.geo or enrichers.rdns:
        geo, rdns = {}, {}
        for name in FIELDS["ip"]:
            for value in _values(event, name):
                if enrichers.geo:
                    found = enrichers.geo.lookup(value)
                    if found:
                        geo[name] = found
                if enrichers.rdns:
                    host = enrichers.rdns.lookup(value)
                    if host:
                        rdns[name] = host
        if geo:
            attrs["geo"] = geo
        if rdns:
            attrs["rdns"] = rdns
    if enrichers.assets:
        asset = enrichers.assets.lookup(_first(event, HOST_FIELDS))
        if asset:
            attrs["asset"] = asset
    if enrichers.users:
        identity = enrichers.users.lookup(_first(event, USER_FIELDS))
        if identity:
            attrs["identity"] = identity


async def enrich_events(tenant_id: str, events: Iterable[Dict[str, Any]], index: Optional[IndicatorIndex] = None,
                        now: Optional[datetime] = None, enrichers=None) -> Dict[str, Any]:
    events = list(events)
    stats: Dict[str, Any] = {"events": len(events), "matched": 0}
    now = now or datetime.now(timezone.utc)
    if enrichers is None:
        from enrichment_processors import get_enrichers

        enrichers = get_enrichers()
    sets = {}
    try:
        sets = await (index or get_indicator_index()).tenant_set(tenant_id, now)
    except Exception as e:
        logger.warning(f"Threat intel unavailable for {tenant_id}, ingesting without it: {e}")
        stats["error"] = str(e)
    if not sets and not enrichers:
        return stats
    for event in events:
        if enrichers:
            try:
                _process(event, enrichers)
            except Exception as e:  # never fail ingestion
                logger.warning(f"Enrichment processor failed: {e}")
        if not sets:
            continue
        hits = _matches(sets, event, now)
        if not hits:
            continue
        attrs = event.setdefault("attrs", {})
        if not isinstance(attrs, dict):
            continue
        attrs["threat"] = {"matched": True, "max_confidence": max(h["confidence"] for h in hits),
                           "threat_types": sorted({h["threat_type"] for h in hits}), "indicators": hits}
        stats["matched"] += 1
    return stats
