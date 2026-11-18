"""
Threat feed parsers (Phase 3).

parse_feed(kind, payload, source) turns a provider's payload into
Indicators of the canonical types ip, domain, url, hash and email.

Kinds: feodo_json, plain (one indicator per line), csv, urlhaus (API),
threatfox (API), otx (pulses), misp (attribute search), stix (2.1 bundle).

Values are normalised (defanged forms, case), ports are stripped from
ip:port, and invalid values and internal addresses (RFC 1918, loopback,
link-local, ...) are dropped: a feed that lists 10.0.0.5 would otherwise
flag every internal connection. Documentation ranges (RFC 5737) are kept;
corpora use them as stand-ins for external hosts.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from threat_intel import Indicator, infer_indicator_type, normalize_indicator

KINDS = ("feodo_json", "plain", "csv", "urlhaus", "threatfox", "otx", "misp", "stix")
TYPES = ("ip", "domain", "url", "hash", "email")
_INTERNAL_V4 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
                                                    "169.254.0.0/16", "0.0.0.0/8", "100.64.0.0/10", "224.0.0.0/4",
                                                    "255.255.255.255/32")]
_INTERNAL_V6 = [ipaddress.ip_network(n) for n in ("::1/128", "::/128", "fc00::/7", "fe80::/10", "ff00::/8")]
_DOMAIN = re.compile(r"^(?=.{1,253}$)([a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")
_HASH = re.compile(r"^(?:[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64})$")
_EMAIL = re.compile(r"^[^@\s]+@[a-z0-9.-]+\.[a-z]{2,}$")


class FeedParseError(ValueError):
    """The payload can't be read as the configured feed kind."""


def _is_internal(ip: str) -> bool:
    address = ipaddress.ip_address(ip)
    networks = _INTERNAL_V4 if address.version == 4 else _INTERNAL_V6
    return any(address in net for net in networks)


def clean(value: Any, indicator_type: Optional[str]) -> Optional[tuple]:
    """(canonical type, normalised value), or None if it isn't a usable IOC."""
    text = normalize_indicator(value)
    if not text:
        return None
    kind = indicator_type if indicator_type in TYPES else infer_indicator_type(text, fallback="")
    if kind == "ip":
        candidate = text.split("|")[0]
        if candidate.count(":") == 1 and "." in candidate:  # ip:port
            candidate = candidate.split(":")[0]
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            return None
        return None if _is_internal(candidate) else ("ip", candidate)
    if kind == "domain":
        return ("domain", text.rstrip(".")) if _DOMAIN.match(text.rstrip(".")) else None
    if kind == "url":
        return ("url", text) if re.match(r"^[a-z][a-z0-9+.-]*://\S+$", text) else None
    if kind == "hash":
        return ("hash", text) if _HASH.match(text) else None
    if kind == "email":
        return ("email", text) if _EMAIL.match(text) else None
    return None


def _time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace(" UTC", "").replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _make(value: Any, indicator_type: Optional[str], source: str, confidence: int, threat_type: str = "malicious",
          tags: Iterable[Any] = (), **extra: Any) -> Optional[Indicator]:
    cleaned = clean(value, indicator_type)
    if cleaned is None:
        return None
    kind, normalised = cleaned
    return Indicator(value=normalised, indicator_type=kind, threat_type=threat_type or "malicious",
                     confidence=max(0, min(100, int(confidence))), source=source,
                     tags=sorted({str(t) for t in (tags or []) if t}), **extra)


def _json(payload: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        raise FeedParseError("the payload is not valid JSON")


def _api_ok(data: Any) -> None:
    if isinstance(data, dict) and data.get("query_status") not in (None, "ok"):
        raise FeedParseError(f"the provider answered query_status={data.get('query_status')!r}")


def _feodo(payload, source, confidence, options):
    for row in _json(payload):
        yield _make(row.get("ip_address"), "ip", source, confidence, "botnet_cc",
                    tags=[row.get("malware")], first_seen=_time(row.get("first_seen")),
                    last_seen=_time(row.get("last_online")))


def _plain(payload, source, confidence, options):
    for line in payload.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", ";", "//")):
            yield _make(line.split()[0], options.get("type"), source, confidence, options.get("threat_type", "malicious"))


def _csv(payload, source, confidence, options):
    reader = csv.DictReader(io.StringIO(payload))
    value_column = options.get("value_column", "indicator")
    type_column = options.get("type_column")
    for row in reader:
        yield _make(row.get(value_column), row.get(type_column) if type_column else options.get("type"), source,
                    confidence, options.get("threat_type", "malicious"))


def _urlhaus(payload, source, confidence, options):
    data = _json(payload)
    _api_ok(data)
    for row in data.get("urls") or []:
        yield _make(row.get("url"), "url", source, confidence, row.get("threat") or "malware_download",
                    tags=row.get("tags") or [], first_seen=_time(row.get("date_added")))


_THREATFOX_TYPES = {"ip:port": "ip", "domain": "domain", "url": "url", "md5_hash": "hash", "sha1_hash": "hash",
                    "sha256_hash": "hash"}


def _threatfox(payload, source, confidence, options):
    data = _json(payload)
    _api_ok(data)
    for row in data.get("data") or []:
        kind = _THREATFOX_TYPES.get(row.get("ioc_type"))
        if kind:
            yield _make(row.get("ioc"), kind, source, row.get("confidence_level", confidence),
                        row.get("threat_type") or "malicious",
                        tags=(row.get("tags") or []) + [row.get("malware_printable")],
                        first_seen=_time(row.get("first_seen")), last_seen=_time(row.get("last_seen")),
                        reference=row.get("reference") or "")


_OTX_TYPES = {"IPv4": "ip", "IPv6": "ip", "domain": "domain", "hostname": "domain", "URL": "url",
              "FileHash-MD5": "hash", "FileHash-SHA1": "hash", "FileHash-SHA256": "hash", "email": "email"}


def _otx(payload, source, confidence, options):
    data = _json(payload)
    for pulse in data.get("results") or []:
        for row in pulse.get("indicators") or []:
            kind = _OTX_TYPES.get(row.get("type"))
            if kind:
                yield _make(row.get("indicator"), kind, source, confidence, "malicious",
                            tags=pulse.get("tags") or [], description=pulse.get("name") or "")


_MISP_TYPES = {"ip-dst": "ip", "ip-src": "ip", "ip-dst|port": "ip", "ip-src|port": "ip", "domain": "domain",
               "hostname": "domain", "url": "url", "md5": "hash", "sha1": "hash", "sha256": "hash",
               "email-src": "email", "email-dst": "email"}


def _misp(payload, source, confidence, options):
    data = _json(payload)
    attributes = (data.get("response") or {}).get("Attribute") if isinstance(data, dict) else None
    for row in attributes or []:
        kind = _MISP_TYPES.get(row.get("type"))
        if kind and row.get("to_ids"):
            yield _make(row.get("value"), kind, source, confidence, row.get("category") or "malicious",
                        tags=[t.get("name") for t in row.get("Tag") or []])


_STIX = re.compile(r"\[\s*(ipv4-addr|ipv6-addr|domain-name|url|email-addr|file)(?::value|:hashes\.'?[\w-]+'?)\s*=\s*'([^']+)'\s*\]")
_STIX_TYPES = {"ipv4-addr": "ip", "ipv6-addr": "ip", "domain-name": "domain", "url": "url", "email-addr": "email",
               "file": "hash"}


def _stix(payload, source, confidence, options):
    data = _json(payload)
    for obj in data.get("objects") or []:
        if obj.get("type") != "indicator" or obj.get("pattern_type", "stix") != "stix":
            continue
        for object_type, value in _STIX.findall(obj.get("pattern") or ""):
            yield _make(value, _STIX_TYPES[object_type], source, obj.get("confidence", confidence),
                        "malicious", tags=obj.get("labels") or [], expires_at=_time(obj.get("valid_until")),
                        description=obj.get("name") or "")


_PARSERS = {"feodo_json": _feodo, "plain": _plain, "csv": _csv, "urlhaus": _urlhaus, "threatfox": _threatfox,
            "otx": _otx, "misp": _misp, "stix": _stix}


def dedupe(indicators: Iterable[Indicator]) -> List[Indicator]:
    """One indicator per (type, value): highest confidence, tags merged."""
    merged: Dict[tuple, Indicator] = {}
    for indicator in indicators:
        key = (indicator.indicator_type, indicator.normalized())
        current = merged.get(key)
        if current is None:
            merged[key] = indicator
            continue
        best = indicator if indicator.confidence > current.confidence else current
        merged[key] = Indicator(**{**best.__dict__, "tags": sorted(set(current.tags) | set(indicator.tags))})
    return list(merged.values())


def parse_feed(kind: str, payload: str, source: str, confidence: int = 70,
               options: Optional[Dict[str, Any]] = None) -> List[Indicator]:
    parser = _PARSERS.get(kind)
    if parser is None:
        raise FeedParseError(f"unknown feed kind {kind!r} (one of {', '.join(KINDS)})")
    try:
        found = [i for i in parser(payload or "", source, confidence, options or {}) if i is not None]
    except FeedParseError:
        raise
    except (AttributeError, TypeError, KeyError) as e:
        raise FeedParseError(f"the payload doesn't look like a {kind} feed ({e})")
    return dedupe(found)
