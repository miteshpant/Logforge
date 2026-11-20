"""
Behaviour baselines (Phase 11): what is normal for an entity, and what in
its last day isn't.

For a user, host or address, from its events of the last 30 days (the
baseline) against its last 24 hours:

* hours: activity at hours of the day that hold under 2% of its usual
  activity (needs 20+ events over 5+ days of history);
* countries: activity from a country it has never been seen in (from the
  GeoIP enrichment, attrs.geo.country);
* volume: today's event count against its daily counts, flagged above
  3 standard deviations, with the severity scale of
  services/anomaly_detector.py (the same 3-sigma rule);
* peers: its spread today against the other entities of its type (a user
  touching many hosts, a host reached by many users, an address reaching
  many hosts): flagged above 3x the peer median and the peer 95th
  percentile, and at least 5.

The detectors are pure functions; BaselineStore collects the counts with a
few aggregate queries. Anomalies feed entity risk (entity_risk).
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

BASELINE_DAYS = 30
RECENT = timedelta(hours=24)
MIN_EVENTS = 20
MIN_DAYS = 5
RARE_HOUR_SHARE = 0.02
Z_THRESHOLD = 3.0  # services/anomaly_detector.AnomalyDetector.z_score_threshold
PEER_FACTOR = 3.0
PEER_MIN = 5

# where an entity type lives in logs_raw_mt, and which other entity its peers are compared on
EXPRESSIONS = {
    "user": "if(user_id != '', user_id, JSONExtractString(attrs, 'user'))",
    "host": "if(toString(host) != '', toString(host), JSONExtractString(attrs, 'hostname'))",
    "ip": "if(src_ip != '', src_ip, JSONExtractString(attrs, 'src_ip'))",
}
SPREAD = {"user": ("host", "hosts"), "host": ("user", "users"), "ip": ("host", "hosts")}


@dataclass
class Anomaly:
    kind: str  # hour | country | volume | peers
    label: str
    severity: str  # low | medium | high
    ts: str
    value: Any = None
    baseline: Any = None

    def to_public(self) -> Dict[str, Any]:
        return asdict(self)


def _severity(z: float) -> str:
    from services.anomaly_detector import AnomalyDetector

    level = AnomalyDetector._calculate_severity(None, z)  # pure: the detector's z-score scale
    return {"critical": "high"}.get(level, level)


def hour_anomalies(baseline: Counter, recent: Counter, days: int, now: datetime) -> List[Anomaly]:
    total = sum(baseline.values())
    if total < MIN_EVENTS or days < MIN_DAYS:
        return []
    out = []
    for hour, count in sorted(recent.items()):
        share = baseline.get(hour, 0) / total
        if share < RARE_HOUR_SHARE:
            out.append(Anomaly("hour", f"{count} event(s) at {hour:02d}:00 UTC, an hour with "
                                       f"{share:.0%} of its usual activity", "medium" if count >= 3 else "low",
                               now.isoformat(), value=count, baseline=round(share, 4)))
    return out


def country_anomalies(baseline: Iterable[str], recent: Counter, baseline_events: int, now: datetime) -> List[Anomaly]:
    known = set(baseline)
    if baseline_events < MIN_EVENTS or not known:
        return []
    return [Anomaly("country", f"{count} event(s) from {country}, where it has not been seen in "
                               f"{BASELINE_DAYS} days (usually: {', '.join(sorted(known)[:5])})", "medium",
                    now.isoformat(), value=country, baseline=sorted(known)[:10])
            for country, count in sorted(recent.items()) if country not in known]


def volume_anomaly(daily: List[int], today: int, now: datetime) -> Optional[Anomaly]:
    if len(daily) < MIN_DAYS or sum(daily) < MIN_EVENTS:
        return None
    mean = statistics.fmean(daily)
    std = max(statistics.pstdev(daily), 1.0, mean * 0.1)
    z = (today - mean) / std
    if z <= Z_THRESHOLD:
        return None
    return Anomaly("volume", f"{today} events today against a usual {mean:.0f} a day ({z:.1f} standard deviations)",
                   _severity(z), now.isoformat(), value=today, baseline=round(mean, 1))


def peer_anomaly(etype: str, value: str, spreads: Dict[str, int], now: datetime) -> Optional[Anomaly]:
    mine = spreads.get(value, 0)
    others = [n for v, n in spreads.items() if v != value]
    if mine < PEER_MIN or len(others) < 5:
        return None
    median = statistics.median(others)
    p95 = sorted(others)[int(0.95 * (len(others) - 1))]
    if mine <= max(PEER_FACTOR * median, p95):
        return None
    _, noun = SPREAD[etype]
    return Anomaly("peers", f"{mine} distinct {noun} today; its peers ({len(others)} {etype}s) median {median:g}, "
                            f"95th percentile {p95}", "high" if mine > 3 * max(p95, 1) else "medium",
                   now.isoformat(), value=mine, baseline={"median": median, "p95": p95})


class BaselineStore:
    def __init__(self, db=None):
        if db is None:
            import os

            from database_layer import DatabaseLayer

            db = DatabaseLayer("EntityService", os.getenv("ENTITY_SERVICE_KEY", "entity-service-key"))
        self.db = db

    async def anomalies(self, tenant_id: str, etype: str, values: List[str],
                        now: Optional[datetime] = None) -> Dict[str, List[Anomaly]]:
        """Anomalies in the last 24 hours, per entity value (users, hosts or addresses)."""
        if etype not in EXPRESSIONS or not values:
            return {}
        now = now or datetime.now(timezone.utc)
        expr = EXPRESSIONS[etype]
        recent_start = now - RECENT
        params = {"tenant": tenant_id, "values": list(values)[:200], "start": (now - timedelta(days=BASELINE_DAYS)),
                  "recent": recent_start, "end": now}
        where = f"customer_id = %(tenant)s AND ts >= %(start)s AND ts < %(end)s AND {expr} IN %(values)s"
        hours = await self.db.fetch_all(
            f"SELECT {expr} AS v, toHour(ts) AS h, ts >= %(recent)s AS recent, count() AS c FROM logs_raw_mt "
            f"WHERE {where} GROUP BY v, h, recent", params)
        countries = await self.db.fetch_all(
            f"SELECT {expr} AS v, JSONExtractString(attrs, 'geo', 'country') AS country, ts >= %(recent)s AS recent, "
            f"count() AS c FROM logs_raw_mt WHERE {where} AND country != '' GROUP BY v, country, recent", params)
        daily = await self.db.fetch_all(
            f"SELECT {expr} AS v, toDate(ts) AS d, ts >= %(recent)s AS recent, count() AS c FROM logs_raw_mt "
            f"WHERE {where} GROUP BY v, d, recent", params)
        other, _ = SPREAD[etype]
        spreads = await self.db.fetch_all(
            f"SELECT {expr} AS v, uniqExact({EXPRESSIONS[other]}) AS n FROM logs_raw_mt "
            f"WHERE customer_id = %(tenant)s AND ts >= %(recent)s AND ts < %(end)s AND {expr} != '' "
            f"AND {EXPRESSIONS[other]} != '' GROUP BY v ORDER BY n DESC LIMIT 5000", params)
        return detect(etype, values, hours, countries, daily, spreads, now)


def detect(etype: str, values: Iterable[str], hours: List[Dict], countries: List[Dict], daily: List[Dict],
           spreads: List[Dict], now: datetime) -> Dict[str, List[Anomaly]]:
    base_hours: Dict[str, Counter] = defaultdict(Counter)
    new_hours: Dict[str, Counter] = defaultdict(Counter)
    for row in hours:
        (new_hours if row["recent"] else base_hours)[row["v"]][int(row["h"])] += int(row["c"])
    base_countries: Dict[str, set] = defaultdict(set)
    new_countries: Dict[str, Counter] = defaultdict(Counter)
    for row in countries:
        if row["recent"]:
            new_countries[row["v"]][row["country"]] += int(row["c"])
        else:
            base_countries[row["v"]].add(row["country"])
    days: Dict[str, Dict[Any, int]] = defaultdict(lambda: defaultdict(int))
    today: Dict[str, int] = defaultdict(int)
    for row in daily:
        if row["recent"]:
            today[row["v"]] += int(row["c"])
        else:
            days[row["v"]][row["d"]] += int(row["c"])
    spread = {row["v"]: int(row["n"]) for row in spreads}
    out: Dict[str, List[Anomaly]] = {}
    for value in values:
        found = hour_anomalies(base_hours[value], new_hours[value], len(days[value]), now)
        found += country_anomalies(base_countries[value], new_countries[value], sum(base_hours[value].values()), now)
        volume = volume_anomaly(list(days[value].values()), today[value], now)
        peers = peer_anomaly(etype, value, spread, now)
        found += [a for a in (volume, peers) if a]
        if found:
            out[value] = found
    return out
