"""
Entity risk scoring (Phase 11): a score per user, host, IP address, service
and cloud account, from the alerts that name it, threat intelligence hits
and behaviour anomalies, decaying over time, with the factors that make it.

For an entity, over the window (14 days by default):

* alerts: severity points (low 5, medium 15, high 35, critical 60), halved
  every HALF_LIFE of age. Repeats of the same rule add less each time
  (the k-th most recent counts 1/2^k), so one noisy rule firing 300 times
  weighs at most twice its first alert, while different rules add up;
* rarity: a rule that fires on many entities of the same type across the
  tenant (daily churn, a scanner sweeping hosts) says little about any one
  of them: its points are scaled by 1 / (1 + log2(n)), n being how many
  entities of that type it fired on in the window;
* tactic progression: an entity whose rare alerts (rarity >= 0.5) span
  several ATT&CK tactics within PROGRESSION_SPAN is further along an attack:
  15 points per extra tactic, and 20 more when the tactics reach from an
  early stage (initial access, execution, credential access) to a late one
  (lateral movement, collection, command and control, exfiltration, impact).
  Unrelated alerts spread over two weeks don't add up to an attack.
  Entities named together in a rare alert are linked (an attacker's
  address, the account it signed in as, the host): each gets the larger of
  its own progression and its linked group's, so the address behind a
  multi-stage intrusion ranks with the account and host it reached;
* intel: a hit on a known-bad indicator adds up to 30 points, by its
  confidence, decaying;
* anomalies: a deviation from the entity's baseline adds 5, 10 or 20 points
  (low, medium, high), decaying.

The raw sum maps to 0-100 (100 * (1 - e^(-raw/120))): rising quickly at
first, saturating for entities with many strong signals. `factors` lists
each contribution, so the score explains itself.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

SEVERITY_POINTS = {"low": 5.0, "medium": 15.0, "high": 35.0, "critical": 60.0}
ANOMALY_POINTS = {"low": 5.0, "medium": 10.0, "high": 20.0}
HALF_LIFE = timedelta(days=3)
WINDOW = timedelta(days=14)
PER_TACTIC = 15.0
SPAN_BONUS = 20.0
INTEL_POINTS = 30.0
SCALE = 120.0
PROGRESSION_SPAN = timedelta(hours=24)
RARE = 0.5
EARLY = {"initial-access", "execution", "credential-access"}
LATE = {"lateral-movement", "collection", "command-and-control", "exfiltration", "impact"}

EntityKey = Tuple[str, str]


@dataclass
class Factor:
    kind: str  # alert | progression | intel | anomaly
    label: str
    points: float
    at: Optional[str] = None
    ref: Optional[str] = None


@dataclass
class Risk:
    entity_type: str
    value: str
    score: int
    raw: float
    factors: List[Factor] = field(default_factory=list)
    alerts: int = 0
    tactics: List[str] = field(default_factory=list)
    last_alert: Optional[str] = None

    def to_public(self, top: int = 10) -> Dict[str, Any]:
        out = asdict(self)
        factors = sorted(self.factors, key=lambda f: -f.points)
        out["factors"] = [asdict(f) | {"points": round(f.points, 1)} for f in factors[:top]]
        out["raw"] = round(self.raw, 1)
        return out


def _time(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def decay(at: Optional[datetime], now: datetime) -> float:
    if at is None:
        return 0.5
    age = max((now - at).total_seconds(), 0.0)
    return 0.5 ** (age / HALF_LIFE.total_seconds())


def _tactic(technique: str) -> Optional[str]:
    from config.mitre_enterprise_complete import TACTIC_MAPPING

    tactic = TACTIC_MAPPING.get(str(technique).split(".")[0].upper())
    return getattr(tactic, "value", None)


def _rule(alert: Dict[str, Any]) -> str:
    return str(alert.get("rule_id") or alert.get("title") or "?")


def _progression(alerts: List[Tuple[datetime, List[str]]]) -> List[str]:
    """The most distinct tactics among alerts within any PROGRESSION_SPAN, in order of first appearance."""
    alerts = sorted(alerts, key=lambda a: a[0])
    best: List[str] = []
    for i, (start, _) in enumerate(alerts):
        seen: List[str] = []
        for at, tactics in alerts[i:]:
            if at - start > PROGRESSION_SPAN:
                break
            for tactic in tactics:
                if tactic not in seen:
                    seen.append(tactic)
        if len(seen) > len(best):
            best = seen
    return best


def score(entity: EntityKey, alerts: Iterable[Dict[str, Any]], now: datetime,
          intel: Iterable[Dict[str, Any]] = (), anomalies: Iterable[Dict[str, Any]] = (),
          window: timedelta = WINDOW, rarity: Optional[Dict[Tuple[str, str], float]] = None,
          linked_tactics: Optional[List[str]] = None, linked: Optional[List[EntityKey]] = None) -> Risk:
    """alerts: {id, rule_id, title, severity, ts, mitre_techniques}; intel: {value, confidence, source, ts};
    anomalies: {label, severity, ts}; rarity: (rule, entity type) -> weight in (0, 1] (default 1)."""
    factors: List[Factor] = []
    raw = 0.0
    rarity = rarity or {}
    in_window = [a for a in alerts if (_time(a.get("ts")) or now) >= now - window]
    by_rule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for alert in in_window:
        by_rule[_rule(alert)].append(alert)
    clustered: List[Tuple[datetime, List[str]]] = []
    for rule, group in by_rule.items():
        group.sort(key=lambda a: _time(a.get("ts")) or now, reverse=True)
        weight = rarity.get((rule, entity[0]), 1.0)
        points = 0.0
        for k, alert in enumerate(group):
            points += SEVERITY_POINTS.get(str(alert.get("severity")), 5.0) * decay(_time(alert.get("ts")), now) * 0.5 ** k
        points *= weight
        first = group[0]
        label = f"{first.get('title') or rule} ({first.get('severity')})" + (f", {len(group)} times" if len(group) > 1 else "")
        if weight < 1:
            label += f", common across the tenant (x{weight:.2f})"
        factors.append(Factor("alert", label, points, at=str(first.get("ts")), ref=str(first.get("id") or "")))
        raw += points
        if weight >= RARE:
            tactics_of = [t for t in (_tactic(x) for x in first.get("mitre_techniques") or []) if t]
            clustered += [(_time(a.get("ts")) or now, tactics_of) for a in group]
    tactics = _progression(clustered)
    via_link = bool(linked_tactics and len(linked_tactics) > len(tactics))
    if via_link:
        tactics = list(linked_tactics)
    if len(tactics) >= 2:
        bonus = PER_TACTIC * (len(tactics) - 1)
        reach = bool(EARLY & set(tactics)) and bool(LATE & set(tactics))
        if reach:
            bonus += SPAN_BONUS
        label = f"{len(tactics)} ATT&CK tactics: {', '.join(t.replace('-', ' ') for t in tactics)}" + \
            (" (from early to late stages)" if reach else "")
        if via_link:
            others = ", ".join(f"{t} {v}" for t, v in (linked or []) if (t, v) != entity)[:200]
            label += f", with linked entities ({others})"
        factors.append(Factor("progression", label, bonus))
        raw += bonus
    for hit in intel:
        points = INTEL_POINTS * min(max(float(hit.get("confidence") or 50), 0.0), 100.0) / 100 * decay(_time(hit.get("ts")), now)
        seen = f", on {hit['alerts']} alerts" if (hit.get("alerts") or 0) > 1 else ""
        factors.append(Factor("intel", f"in threat intelligence ({hit.get('source') or 'feed'}, confidence "
                                       f"{hit.get('confidence')}{seen})", points, at=str(hit.get("ts") or "")))
        raw += points
    for anomaly in anomalies:
        points = ANOMALY_POINTS.get(str(anomaly.get("severity")), 5.0) * decay(_time(anomaly.get("ts")), now)
        factors.append(Factor("anomaly", str(anomaly.get("label") or "unusual behaviour"), points,
                              at=str(anomaly.get("ts") or "")))
        raw += points
    last = max((str(a.get("ts")) for a in in_window), default=None)
    return Risk(entity_type=entity[0], value=entity[1], score=round(100 * (1 - math.exp(-raw / SCALE))), raw=raw,
                factors=factors, alerts=len(in_window), tactics=tactics, last_alert=last)


def attribute(alerts: Iterable[Dict[str, Any]]) -> Dict[EntityKey, List[Dict[str, Any]]]:
    """Alerts (as case_service.alert_summary gives them) per entity they name."""
    from entities import ALERT_TYPES

    out: Dict[EntityKey, List[Dict[str, Any]]] = defaultdict(list)
    for alert in alerts:
        seen = set()
        for field_name, values in (alert.get("entities") or {}).items():
            etype = ALERT_TYPES.get(field_name)
            for value in values or []:
                key = (etype, str(value))
                if etype and value and key not in seen:
                    seen.add(key)
                    out[key].append(alert)
    return out


def intel_hits(alerts: Iterable[Dict[str, Any]]) -> Dict[EntityKey, List[Dict[str, Any]]]:
    """Threat intelligence matched at ingest (alert_summary's `threat`), on the alert's addresses: one hit
    per address (its highest confidence, latest time, every source), however many alerts carried it."""
    merged: Dict[EntityKey, Dict[str, Any]] = {}
    for alert in alerts:
        threat = alert.get("threat") or {}
        if not threat:
            continue
        for value in (alert.get("entities") or {}).get("src_ip") or []:
            hit = merged.setdefault(("ip", str(value)), {"value": value, "confidence": 0, "sources": set(),
                                                         "ts": None, "alerts": 0})
            hit["confidence"] = max(hit["confidence"], float(threat.get("max_confidence") or 0))
            hit["sources"] |= set(threat.get("sources") or [])
            hit["alerts"] += 1
            if hit["ts"] is None or str(alert.get("ts")) > str(hit["ts"]):
                hit["ts"] = alert.get("ts")
    return {key: [{"value": h["value"], "confidence": round(h["confidence"]),
                   "source": ", ".join(sorted(h["sources"])) or None, "ts": h["ts"], "alerts": h["alerts"]}]
            for key, h in merged.items()}


def rarity_weights(by_entity: Dict[EntityKey, List[Dict[str, Any]]], now: datetime,
                   window: timedelta = WINDOW) -> Dict[Tuple[str, str], float]:
    """(rule, entity type) -> 1 / (1 + log2(entities of that type the rule fired on in the window))."""
    reach: Dict[Tuple[str, str], set] = defaultdict(set)
    for (etype, value), alerts in by_entity.items():
        for alert in alerts:
            if (_time(alert.get("ts")) or now) >= now - window:
                reach[(_rule(alert), etype)].add(value)
    return {key: 1.0 / (1.0 + math.log2(len(values))) for key, values in reach.items()}


def _keys(alert: Dict[str, Any]) -> List[EntityKey]:
    from entities import ALERT_TYPES

    out: List[EntityKey] = []
    for field_name, values in (alert.get("entities") or {}).items():
        etype = ALERT_TYPES.get(field_name)
        for value in values or []:
            if etype and value and (etype, str(value)) not in out:
                out.append((etype, str(value)))
    return out


def linked_groups(alerts: List[Dict[str, Any]], rarity: Dict[Tuple[str, str], float], now: datetime,
                  window: timedelta = WINDOW) -> Dict[EntityKey, Dict[str, Any]]:
    """Entities linked by rare alerts (rare for every entity type they name), and each group's progression."""
    parent: Dict[EntityKey, EntityKey] = {}

    def find(x: EntityKey) -> EntityKey:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    rare_alerts = []
    for alert in alerts:
        if (_time(alert.get("ts")) or now) < now - window:
            continue
        keys = _keys(alert)
        if keys and all(rarity.get((_rule(alert), t), 1.0) >= RARE for t, _ in keys):
            rare_alerts.append((alert, keys))
            for other in keys[1:]:
                parent[find(other)] = find(keys[0])
    members: Dict[EntityKey, List[EntityKey]] = defaultdict(list)
    clustered: Dict[EntityKey, List[Tuple[datetime, List[str]]]] = defaultdict(list)
    for alert, keys in rare_alerts:
        root = find(keys[0])
        for key in keys:
            if key not in members[root]:
                members[root].append(key)
        tactics = [t for t in (_tactic(x) for x in alert.get("mitre_techniques") or []) if t]
        clustered[root].append((_time(alert.get("ts")) or now, tactics))
    out: Dict[EntityKey, Dict[str, Any]] = {}
    for root, keys in members.items():
        if len(keys) < 2:
            continue
        group = {"entities": keys, "tactics": _progression(clustered[root])}
        for key in keys:
            out[key] = group
    return out


def rank(alerts: List[Dict[str, Any]], now: datetime, intel: Optional[Dict[EntityKey, List[Dict]]] = None,
         anomalies: Optional[Dict[EntityKey, List[Dict]]] = None, limit: int = 50,
         window: timedelta = WINDOW) -> List[Risk]:
    """Every entity named by an alert, an intel hit or an anomaly, highest risk first."""
    by_entity = attribute(alerts)
    intel = intel if intel is not None else intel_hits(alerts)
    anomalies = anomalies or {}
    rarity = rarity_weights(by_entity, now, window)
    groups = linked_groups(alerts, rarity, now, window)
    keys = set(by_entity) | set(intel) | set(anomalies)
    risks = []
    for k in keys:
        members = groups.get(k)
        risks.append(score(k, by_entity.get(k, []), now, intel.get(k, []), anomalies.get(k, []), window, rarity,
                           linked_tactics=members["tactics"] if members else None,
                           linked=members["entities"] if members else None))
    risks.sort(key=lambda r: (-r.raw, r.entity_type, r.value))
    return risks[:limit]
