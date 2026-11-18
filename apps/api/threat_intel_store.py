"""
Threat intelligence storage, the in-memory index and the feed runner
(Phase 3).

* Feeds and indicators are per tenant (threat_feeds_mt, threat_indicators_mt,
  migration 018). A feed's API key is read from the environment variable
  the feed names (secret_env) at fetch time; it is never stored or returned.
* IndicatorIndex answers lookups from memory so matching at ingest adds no
  database round trip: exact values, plus parent domains for domains. Each
  tenant's set reloads after `ttl_seconds`.
* run_feed fetches a feed, parses it (threat_feeds), applies the feed's
  confidence and TTL, upserts, records the run's status and reports which
  indicators are new, for retro-hunting.
"""

from __future__ import annotations

import json
import os
import re
import time as _time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import structlog

from threat_feeds import KINDS, FeedParseError, parse_feed
from threat_intel import Indicator, normalize_indicator

logger = structlog.get_logger(__name__)

MAX_INDICATORS_PER_FEED = 1_000_000
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_HEADER = re.compile(r"^[A-Za-z0-9-]{1,64}$")
Key = Tuple[str, str]

#: Ready-made feeds. URLhaus, ThreatFox and OTX need a free account key,
#: set in the environment variable the template names.
BUILTIN_FEEDS: List[Dict[str, Any]] = [
    {"name": "abuse.ch Feodo Tracker", "kind": "feodo_json",
     "url": "https://feodotracker.abuse.ch/downloads/ipblocklist.json",
     "interval_minutes": 60, "confidence": 90, "ttl_days": 7},
    {"name": "abuse.ch URLhaus", "kind": "urlhaus", "method": "POST",
     "url": "https://urlhaus-api.abuse.ch/v1/urls/recent/", "auth_header": "Auth-Key",
     "secret_env": "ABUSECH_AUTH_KEY", "interval_minutes": 60, "confidence": 80, "ttl_days": 14},
    {"name": "abuse.ch ThreatFox", "kind": "threatfox", "method": "POST",
     "url": "https://threatfox-api.abuse.ch/api/v1/", "body": {"query": "get_iocs", "days": 1},
     "auth_header": "Auth-Key", "secret_env": "ABUSECH_AUTH_KEY", "interval_minutes": 60, "confidence": 75,
     "ttl_days": 30},
    {"name": "AlienVault OTX (subscribed pulses)", "kind": "otx",
     "url": "https://otx.alienvault.com/api/v1/pulses/subscribed?limit=50", "auth_header": "X-OTX-API-KEY",
     "secret_env": "OTX_API_KEY", "interval_minutes": 120, "confidence": 60, "ttl_days": 30},
]


def _ms(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _as_time(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime):
        if value.year <= 1970:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


@dataclass
class FeedConfig:
    name: str
    kind: str
    url: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: str = "GET"
    body: Optional[Dict[str, Any]] = None
    auth_header: str = ""
    secret_env: str = ""
    options: Dict[str, Any] = field(default_factory=dict)
    interval_minutes: int = 60
    confidence: int = 70
    ttl_days: int = 7
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    last_status: str = "never"
    last_error: str = ""
    last_count: int = 0
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedConfig":
        values = {k: data[k] for k in cls.__dataclass_fields__ if k in data and data[k] is not None}
        for key in ("body", "options"):
            if isinstance(values.get(key), str):
                values[key] = json.loads(values[key] or "null") or ({} if key == "options" else None)
        for key in ("last_run_at", "created_at"):
            values[key] = _as_time(values.get(key))
        if "enabled" in values:
            values["enabled"] = bool(values["enabled"])
        feed = cls(**values)
        feed.validate()
        return feed

    def validate(self) -> None:
        if not str(self.name).strip():
            raise ValueError("a feed needs a name")
        if self.kind not in KINDS:
            raise ValueError(f"unknown feed kind {self.kind!r} (one of {', '.join(KINDS)})")
        if not str(self.url).startswith("https://"):
            raise ValueError("feed URLs must use https")
        if self.method not in ("GET", "POST"):
            raise ValueError("method must be GET or POST")
        if self.secret_env and not _ENV_NAME.match(self.secret_env):
            raise ValueError("secret_env must be an environment variable name (A-Z, 0-9, _)")
        if self.auth_header and not _HEADER.match(self.auth_header):
            raise ValueError("auth_header must be an HTTP header name")
        if bool(self.auth_header) != bool(self.secret_env):
            raise ValueError("auth_header and secret_env go together")
        self.interval_minutes = max(5, int(self.interval_minutes))
        self.confidence = max(0, min(100, int(self.confidence)))
        self.ttl_days = max(1, int(self.ttl_days))

    def to_row(self) -> Dict[str, Any]:
        row = asdict(self)
        row["body"] = json.dumps(self.body) if self.body is not None else ""
        row["options"] = json.dumps(self.options or {})
        row["enabled"] = 1 if self.enabled else 0
        return row

    def to_public(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("last_run_at", "created_at"):
            data[key] = data[key].isoformat() if data[key] else None
        data["secret_configured"] = bool(self.secret_env) and bool(os.getenv(self.secret_env))
        return data


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_IND_COLUMNS = ("tenant_id", "indicator_type", "value", "threat_type", "confidence", "source", "feed_id", "tags",
                "first_seen", "last_seen", "expires_at", "reference", "description", "updated_at", "deleted")
_FEED_COLUMNS = ("tenant_id", "id", "name", "kind", "url", "method", "body", "auth_header", "secret_env", "options",
                 "interval_minutes", "confidence", "ttl_days", "enabled", "last_run_at", "last_status", "last_error",
                 "last_count", "created_at", "deleted", "version")


def _row_to_indicator(row: Dict[str, Any]) -> Indicator:
    return Indicator(value=row["value"], indicator_type=row["indicator_type"],
                     threat_type=row.get("threat_type") or "malicious", confidence=int(row.get("confidence") or 0),
                     source=row.get("source") or "", tags=list(row.get("tags") or []),
                     first_seen=_as_time(row.get("first_seen")), last_seen=_as_time(row.get("last_seen")),
                     expires_at=_as_time(row.get("expires_at")), reference=row.get("reference") or "",
                     description=row.get("description") or "")


class ThreatIntelDAO:
    def __init__(self):
        from database_layer import DatabaseLayer

        self.db = DatabaseLayer("ThreatIntelDAO", os.getenv("THREAT_INTEL_SERVICE_KEY", "threat-intel-dao-service-key"))

    async def _insert(self, table: str, columns: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
        for start in range(0, len(rows), 1000):
            chunk = rows[start:start + 1000]
            params: Dict[str, Any] = {}
            tuples = []
            for i, row in enumerate(chunk):
                for column in columns:
                    params[f"{column}_{i}"] = row[column]
                tuples.append("(" + ", ".join(f"%({c}_{i})s" for c in columns) + ")")
            await self.db.execute_update(f"INSERT INTO {table} ({', '.join(columns)}) VALUES " + ", ".join(tuples),
                                         params)

    async def upsert_indicators(self, tenant_id: str, indicators: Iterable[Indicator], feed_id: str,
                                now: datetime) -> None:
        rows = [{"tenant_id": tenant_id, "indicator_type": i.indicator_type, "value": i.normalized(),
                 "threat_type": i.threat_type, "confidence": int(i.confidence), "source": i.source,
                 "feed_id": feed_id, "tags": list(i.tags), "first_seen": _ms(i.first_seen),
                 "last_seen": _ms(i.last_seen), "expires_at": _ms(i.expires_at), "reference": i.reference,
                 "description": i.description, "updated_at": _ms(now), "deleted": 0} for i in indicators]
        if rows:
            await self._insert("threat_indicators_mt", _IND_COLUMNS, rows)

    async def delete_indicator(self, tenant_id: str, indicator_type: str, value: str, now: datetime) -> None:
        await self._insert("threat_indicators_mt", _IND_COLUMNS, [{
            "tenant_id": tenant_id, "indicator_type": indicator_type, "value": normalize_indicator(value),
            "threat_type": "", "confidence": 0, "source": "", "feed_id": "", "tags": [], "first_seen": None,
            "last_seen": None, "expires_at": None, "reference": "", "description": "", "updated_at": _ms(now),
            "deleted": 1}])

    async def existing_keys(self, tenant_id: str, keys: Iterable[Key]) -> Set[Key]:
        keys = set(keys)
        found: Set[Key] = set()
        values = sorted({v for _, v in keys})
        for start in range(0, len(values), 5000):
            rows = await self.db.fetch_all(
                "SELECT indicator_type, value FROM threat_indicators_mt FINAL WHERE tenant_id = %(tenant_id)s "
                "AND deleted = 0 AND value IN %(values)s", {"tenant_id": tenant_id, "values": values[start:start + 5000]})
            found |= {(r["indicator_type"], r["value"]) for r in rows or []} & keys
        return found

    async def active_indicators(self, tenant_id: str, now: datetime) -> List[Indicator]:
        rows = await self.db.fetch_all(
            "SELECT * FROM threat_indicators_mt FINAL WHERE tenant_id = %(tenant_id)s AND deleted = 0 "
            "AND (expires_at IS NULL OR expires_at > %(now)s)", {"tenant_id": tenant_id, "now": _ms(now)})
        return [_row_to_indicator(r) for r in rows or []]

    async def search_indicators(self, tenant_id: str, q: str = "", indicator_type: Optional[str] = None,
                                limit: int = 100, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        where = ["tenant_id = %(tenant_id)s", "deleted = 0"]
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        if q:
            where.append("(positionCaseInsensitive(value, %(q)s) > 0 OR positionCaseInsensitive(source, %(q)s) > 0 "
                         "OR has(tags, %(q)s))")
            params["q"] = q
        if indicator_type:
            where.append("indicator_type = %(type)s")
            params["type"] = indicator_type
        clause = " AND ".join(where)
        rows = await self.db.fetch_all(
            f"SELECT * FROM threat_indicators_mt FINAL WHERE {clause} ORDER BY updated_at DESC "
            "LIMIT %(limit)s OFFSET %(offset)s", {**params, "limit": limit, "offset": offset})
        total = await self.db.fetch_all(f"SELECT count() AS total FROM threat_indicators_mt FINAL WHERE {clause}",
                                        params)
        return rows or [], int((total or [{}])[0].get("total", 0))

    # -- feeds -------------------------------------------------------------
    async def save_feed(self, tenant_id: str, feed: FeedConfig, deleted: bool = False) -> None:
        row = feed.to_row()
        row.update(tenant_id=tenant_id, deleted=1 if deleted else 0, version=_time.time_ns() // 1000,
                   last_run_at=_ms(feed.last_run_at), created_at=_ms(feed.created_at or datetime.now(timezone.utc)))
        await self._insert("threat_feeds_mt", _FEED_COLUMNS, [row])

    async def list_feeds(self, tenant_id: Optional[str] = None) -> List[Tuple[str, FeedConfig]]:
        """(tenant, feed) for one tenant, or for every tenant (the scheduler)."""
        where = "deleted = 0" + (" AND tenant_id = %(tenant_id)s" if tenant_id else "")
        rows = await self.db.fetch_all(f"SELECT * FROM threat_feeds_mt FINAL WHERE {where} ORDER BY name",
                                       {"tenant_id": tenant_id} if tenant_id else {})
        feeds = []
        for row in rows or []:
            try:
                feeds.append((row["tenant_id"], FeedConfig.from_dict(row)))
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid feed {row.get('id')}: {e}")
        return feeds

    async def record_run(self, tenant_id: str, feed: FeedConfig, now: datetime, status: str, count: int,
                         error: str) -> None:
        feed.last_run_at, feed.last_status, feed.last_count, feed.last_error = now, status, count, error[:2000]
        await self.save_feed(tenant_id, feed)


# ---------------------------------------------------------------------------
# In-memory index
# ---------------------------------------------------------------------------

Loader = Callable[[str, datetime], Awaitable[List[Indicator]]]


class IndicatorIndex:
    """Per-tenant indicator sets in memory, reloaded after `ttl_seconds`."""

    def __init__(self, loader: Optional[Loader] = None, ttl_seconds: int = 60):
        self._loader = loader
        self.ttl = timedelta(seconds=ttl_seconds)
        self._sets: Dict[str, Tuple[datetime, Dict[str, Dict[str, Indicator]]]] = {}

    async def _load(self, tenant_id: str, now: datetime) -> Dict[str, Dict[str, Indicator]]:
        cached = self._sets.get(tenant_id)
        if cached and now - cached[0] < self.ttl:
            return cached[1]
        loader = self._loader or (lambda t, n: ThreatIntelDAO().active_indicators(t, n))
        by_type: Dict[str, Dict[str, Indicator]] = {}
        for indicator in await loader(tenant_id, now):
            by_type.setdefault(indicator.indicator_type, {})[indicator.normalized()] = indicator
        self._sets[tenant_id] = (now, by_type)
        return by_type

    def invalidate(self, tenant_id: Optional[str] = None) -> None:
        if tenant_id is None:
            self._sets.clear()
        else:
            self._sets.pop(tenant_id, None)

    async def size(self, tenant_id: str, now: Optional[datetime] = None) -> int:
        return sum(len(v) for v in (await self._load(tenant_id, now or datetime.now(timezone.utc))).values())

    async def lookup(self, tenant_id: str, indicator_type: str, value: Any,
                     now: Optional[datetime] = None) -> Optional[Indicator]:
        now = now or datetime.now(timezone.utc)
        values = (await self._load(tenant_id, now)).get(indicator_type)
        if not values:
            return None
        text = normalize_indicator(value)
        candidates = [text]
        if indicator_type == "domain":
            labels = text.rstrip(".").split(".")
            candidates = [".".join(labels[i:]) for i in range(len(labels) - 1)]
        for candidate in candidates:
            hit = values.get(candidate)
            if hit is not None and (hit.expires_at is None or hit.expires_at > now):
                return hit
        return None


_index: Optional[IndicatorIndex] = None


def get_indicator_index() -> IndicatorIndex:
    global _index
    if _index is None:
        _index = IndicatorIndex(ttl_seconds=int(os.getenv("THREAT_INTEL_INDEX_TTL_SECONDS", "60")))
    return _index


# ---------------------------------------------------------------------------
# Feed runner
# ---------------------------------------------------------------------------

Fetch = Callable[[Dict[str, Any]], Awaitable[Tuple[int, str]]]


async def http_fetch(request: Dict[str, Any]) -> Tuple[int, str]:
    import httpx

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        async with client.stream(request["method"], request["url"], headers=request["headers"],
                                 json=request.get("json")) as response:
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_PAYLOAD_BYTES:
                    raise ValueError(f"feed payload exceeds {MAX_PAYLOAD_BYTES // (1024 * 1024)} MB")
                chunks.append(chunk)
            return response.status_code, b"".join(chunks).decode("utf-8", errors="replace")


async def run_feed(tenant_id: str, feed: FeedConfig, store, fetch: Optional[Fetch] = None,
                   now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    headers = {"Accept": "application/json, text/plain, */*", "User-Agent": "Logforge-threat-feeds"}
    try:
        if feed.secret_env:
            secret = os.getenv(feed.secret_env)
            if not secret:
                raise ValueError(f"{feed.secret_env} is not set (the feed's API key)")
            headers[feed.auth_header] = secret
        request = {"method": feed.method, "url": feed.url, "headers": headers, "json": feed.body}
        status, payload = await (fetch or http_fetch)(request)
        if status != 200:
            raise ValueError(f"HTTP {status} from the feed")
        indicators = parse_feed(feed.kind, payload, source=feed.name, confidence=feed.confidence,
                                options=feed.options)[:MAX_INDICATORS_PER_FEED]
        expiry = now + timedelta(days=feed.ttl_days)
        indicators = [Indicator(**{**i.__dict__, "expires_at": i.expires_at or expiry,
                                   "first_seen": i.first_seen or now, "last_seen": i.last_seen or now})
                      for i in indicators]
        keys = {(i.indicator_type, i.normalized()) for i in indicators}
        existing = await store.existing_keys(tenant_id, keys)
        await store.upsert_indicators(tenant_id, indicators, feed.id, now)
        await store.record_run(tenant_id, feed, now, "ok", len(indicators), "")
        return {"status": "ok", "count": len(indicators), "new": sorted(keys - existing), "error": ""}
    except (FeedParseError, ValueError) as e:
        error = str(e)
    except Exception as e:  # network errors and the like
        error = f"{type(e).__name__}: {e}"
    logger.warning(f"Threat feed {feed.name} failed: {error}")
    try:
        await store.record_run(tenant_id, feed, now, "error", 0, error)
    except Exception as e:
        logger.warning(f"Could not record the failed run of {feed.name}: {e}")
    return {"status": "error", "count": 0, "new": [], "error": error}


def due_feeds(feeds: Iterable[FeedConfig], now: datetime) -> List[FeedConfig]:
    return [f for f in feeds if f.enabled and (
        f.last_run_at is None or now - f.last_run_at >= timedelta(minutes=f.interval_minutes))]
