"""
Case service (Phase 2): case actions over storage and the tenant's alerts.

Loads alerts (stored security detections) to enrich cases, saves a new case
version and appends timeline events for every action, and turns a case's
close reason into its alerts' verdicts: false_positive feeds the Phase 1
tuning suggestions, resolved resolves them.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

import structlog

from cases import CLOSED, Case, CaseError, apply_action, merge_cases, new_case, split_case

logger = structlog.get_logger(__name__)

#: Event fields that identify the entities an alert is about.
ENTITY_FIELDS = ("src_ip", "dst_ip", "user", "hostname")
BULK_ACTIONS = ("assign", "set_status", "tags")


class CaseNotFound(LookupError):
    pass


def _field(event: Dict[str, Any], name: str) -> Any:
    value = event.get(name)
    if value in (None, "") and isinstance(event.get("attrs"), dict):
        value = event["attrs"].get(name)
    if value in (None, "") and name == "hostname":
        value = event.get("host")
    return value


def alert_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """A stored security detection as a case alert: id, rule, severity, time
    and the entities (source/destination IP, user, host) from its event."""
    raw = row.get("raw_log_data") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except ValueError:
            raw = {}
    event = raw.get("normalized_log") if isinstance(raw.get("normalized_log"), dict) else raw
    entities = {}
    for name in ENTITY_FIELDS:
        value = _field(event if isinstance(event, dict) else {}, name)
        if value not in (None, ""):
            entities[name] = [str(value)]
    created = row.get("created_at")
    extra: Dict[str, Any] = {}
    attrs = event.get("attrs") if isinstance(event, dict) and isinstance(event.get("attrs"), dict) else {}
    threat = attrs.get("threat")
    if isinstance(threat, dict) and threat.get("matched"):
        extra["threat"] = {"max_confidence": threat.get("max_confidence"),
                           "threat_types": list(threat.get("threat_types") or []),
                           "sources": sorted({i.get("source") for i in threat.get("indicators") or [] if i.get("source")})}
    if isinstance(attrs.get("geo"), dict):
        extra["geo"] = attrs["geo"]
    return extra | {
        "id": str(row.get("id")),
        "rule_id": row.get("rule_id"),
        "title": row.get("title") or row.get("rule_title"),
        "severity": row.get("severity"),
        "status": row.get("status"),
        "ts": created.isoformat() if isinstance(created, datetime) else created,
        "mitre_techniques": list(row.get("mitre_techniques") or []),
        "entities": entities,
    }


def case_to_dict(case: Case) -> Dict[str, Any]:
    data = asdict(case)
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def _serialise_event(event: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(event)
    if isinstance(out.get("ts"), datetime):
        out["ts"] = out["ts"].isoformat()
    out.pop("tenant_id", None)
    return out


class SecurityAlerts:
    """Alerts backed by security_events_mt (SecurityService)."""

    def __init__(self):
        from services.security_service import SecurityService

        self.security = SecurityService()

    async def get(self, tenant_id: str, alert_id: str) -> Optional[Dict[str, Any]]:
        return await self.security.get_security_event_details(alert_id, tenant_id)

    async def set_verdict(self, tenant_id: str, alert_id: str, verdict: str, actor: str, notes: str) -> None:
        if verdict == "false_positive":
            await self.security.mark_false_positive(alert_id, tenant_id, actor, notes)
        else:
            await self.security.resolve_security_event(alert_id, tenant_id, actor, notes)


class CaseService:
    def __init__(self, dao=None, alerts=None, clock: Callable[[], datetime] = None):
        if dao is None:
            from dao.case_dao import CaseDAO

            dao = CaseDAO()
        self.dao = dao
        self._alerts = alerts
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def alerts(self):
        if self._alerts is None:
            self._alerts = SecurityAlerts()
        return self._alerts

    # -- helpers -----------------------------------------------------------
    async def _load(self, tenant_id: str, case_id: str) -> Case:
        case = await self.dao.get(tenant_id, case_id)
        if case is None:
            raise CaseNotFound(case_id)
        return case

    async def _alert(self, tenant_id: str, alert_id: str) -> Dict[str, Any]:
        row = await self.alerts.get(tenant_id, alert_id)
        if not row:
            raise CaseError(f"unknown alert {alert_id}")
        return alert_summary(row)

    async def _store(self, cases: Sequence[Case], events: List[Dict[str, Any]]) -> None:
        await self.dao.save_all(list(cases))
        await self.dao.append_events(events)

    async def _apply_verdicts(self, before: Case, after: Case, actor: str) -> None:
        """Closing a case decides its alerts: false positive or resolved."""
        if after.status not in CLOSED or before.status == after.status or after.merged_into:
            return
        for alert_id in after.alert_ids:
            try:
                await self.alerts.set_verdict(after.tenant_id, alert_id, after.status, actor, after.close_reason)
            except Exception as e:  # a verdict failure must not undo the case change
                logger.warning(f"Could not set verdict {after.status} on alert {alert_id}: {e}")

    # -- operations --------------------------------------------------------
    async def create(self, tenant_id: str, actor: str, title: str, severity: Optional[str] = None,
                     description: str = "", tags: Sequence[str] = (), alert_ids: Sequence[str] = (),
                     evidence: Sequence[Dict[str, Any]] = (), assignee: Optional[str] = None,
                     group_key: str = "") -> Case:
        alerts = [await self._alert(tenant_id, a) for a in dict.fromkeys(alert_ids)]
        now = self.clock()
        case, events = new_case(tenant_id, title, actor, now, severity=severity, description=description,
                                tags=tags, alerts=alerts, group_key=group_key)
        if assignee:
            case, more = apply_action(case, "assign", actor, now, assignee=assignee)
            events += more
        for item in evidence:
            case, more = apply_action(case, "pin_evidence", actor, now, evidence=item)
            events += more
        await self._store([case], events)
        return case

    async def get(self, tenant_id: str, case_id: str) -> Optional[Case]:
        return await self.dao.get(tenant_id, case_id)

    async def act(self, tenant_id: str, case_id: str, action: str, actor: str, **kwargs: Any) -> Case:
        before = await self._load(tenant_id, case_id)
        after, events = apply_action(before, action, actor, self.clock(), **kwargs)
        if events:
            await self._store([after], events)
            await self._apply_verdicts(before, after, actor)
        return after

    async def attach_alerts(self, tenant_id: str, case_id: str, alert_ids: Sequence[str], actor: str) -> Case:
        case = await self._load(tenant_id, case_id)
        events: List[Dict[str, Any]] = []
        now = self.clock()
        for alert_id in dict.fromkeys(alert_ids):
            case, more = apply_action(case, "attach_alert", actor, now, alert=await self._alert(tenant_id, alert_id))
            events += more
        if events:
            await self._store([case], events)
        return case

    async def merge(self, tenant_id: str, target_id: str, source_ids: Sequence[str], actor: str) -> Case:
        target = await self._load(tenant_id, target_id)
        sources = [await self._load(tenant_id, s) for s in dict.fromkeys(source_ids)]
        merged, closed, events = merge_cases(target, sources, actor, self.clock())
        await self._store([merged] + closed, events)
        return merged

    async def split(self, tenant_id: str, case_id: str, alert_ids: Sequence[str], actor: str,
                    title: Optional[str] = None) -> Tuple[Case, Case]:
        case = await self._load(tenant_id, case_id)
        remaining, created, events = split_case(case, alert_ids, actor, self.clock(), title=title)
        await self._store([remaining, created], events)
        return remaining, created

    async def bulk(self, tenant_id: str, case_ids: Sequence[str], action: str, actor: str,
                   **kwargs: Any) -> Dict[str, Any]:
        if action not in BULK_ACTIONS:
            raise CaseError(f"bulk supports {', '.join(BULK_ACTIONS)}, not {action!r}")
        updated, errors = [], {}
        for case_id in dict.fromkeys(case_ids):
            try:
                await self.act(tenant_id, case_id, action, actor, **kwargs)
                updated.append(case_id)
            except CaseNotFound:
                errors[case_id] = "case not found"
            except CaseError as e:
                errors[case_id] = str(e)
        return {"updated": updated, "errors": errors}

    async def details(self, tenant_id: str, case_id: str,
                      timeline: Optional[Callable[[str], Awaitable[List[Dict[str, Any]]]]] = None) -> Dict[str, Any]:
        case = await self._load(tenant_id, case_id)
        events = await (timeline(case_id) if timeline else self.dao.events(tenant_id, case_id))
        alerts = []
        for alert_id in case.alert_ids:
            try:
                row = await self.alerts.get(tenant_id, alert_id)
            except Exception:
                row = None
            alerts.append(alert_summary(row) if row else {"id": alert_id, "missing": True})
        from cases import pinned_evidence

        timeline = [_serialise_event(e) for e in events]
        return {"case": case_to_dict(case), "alerts": alerts, "timeline": timeline,
                "evidence": pinned_evidence(timeline)}

    async def list(self, tenant_id: str, **filters: Any) -> Tuple[List[Case], int]:
        return await self.dao.list(tenant_id, **filters)

    async def route_alert(self, tenant_id: str, row: Dict[str, Any],
                          correlation_group: Optional[Dict[str, Any]] = None, policy=None) -> Optional[Case]:
        """Attach a new alert to the open case for its entity, or open one
        (see case_grouping). Returns the case, or None if skipped."""
        from case_grouping import GroupingPolicy, group_key, plan

        policy = policy or GroupingPolicy.from_env()
        if not policy.enabled:
            return None
        alert = alert_summary(row)
        key = group_key(alert, correlation_group)
        async with _lock_for(tenant_id, key):
            now = self.clock()
            existing = await self.dao.find_open_by_group_key(tenant_id, key, now - policy.window) if key else None
            decision = plan(alert, existing, now, policy)
            if decision == "skip":
                return None
            if decision == "attach":
                case, events = apply_action(existing, "attach_alert", "system", now, alert=alert)
                if events:
                    await self._store([case], events)
                return case
            title = (alert.get("title") or "Security alert").removeprefix("Security Detection: ").strip() or "Security alert"
            case, events = new_case(tenant_id, f"{title}: {key}" if key else title, "system", now,
                                    alerts=[alert], group_key=key)
            await self._store([case], events)
            return case


    async def metrics(self, tenant_id: str, days: int) -> Dict[str, Any]:
        """SLA metrics and SOC overview (case_metrics) for cases created in
        the last `days` plus every case still open, against the tenant's targets."""
        from datetime import timedelta

        from case_metrics import case_metrics, sla_targets

        now = self.clock()
        targets = sla_targets(await self.sla_overrides(tenant_id))
        report = case_metrics(await self.dao.for_metrics(tenant_id, now - timedelta(days=days)), now, targets)
        report["window_days"] = days
        return report

    # -- SLA targets (per tenant) ------------------------------------------------------

    async def sla_overrides(self, tenant_id: str) -> Dict[str, Dict[str, int]]:
        import json

        if not hasattr(self.dao, "sla_overrides"):  # a DAO without SLA storage: the defaults
            return {}
        return json.loads(await self.dao.sla_overrides(tenant_id) or "{}")

    async def set_sla_overrides(self, tenant_id: str, overrides: Dict[str, Dict[str, int]], actor: str):
        import json

        from case_metrics import validate_sla_overrides

        try:
            clean = validate_sla_overrides(overrides or {})
        except ValueError as e:
            raise CaseError(str(e))
        await self.dao.save_sla_overrides(tenant_id, json.dumps(clean), actor)
        return clean

    async def audit(self, tenant_id: str, start: datetime, end: datetime, limit: int) -> List[Dict[str, Any]]:
        """Every case change in [start, end): the audit trail."""
        return [_serialise_event(e) for e in await self.dao.events_between(tenant_id, start, end, limit=limit)]

_locks: Dict[Tuple[str, str], Any] = {}

_RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


class GroupLock:
    """The lock grouping holds per (tenant, entity key) while it looks for an open
    case and creates one: a local asyncio lock, plus a Redis lock so several API
    replicas don't open duplicate cases for one entity. The Redis lock expires
    (ttl) so a crashed holder can't block grouping for long, and only its holder
    releases it. Without Redis, the local lock alone applies."""

    def __init__(self, tenant_id: str, key: str, redis=None, local=None, ttl_ms: int = 15_000,
                 wait_s: float = 15.0):
        self.tenant_id, self.group_key = tenant_id, key
        self.key = f"case:group:{tenant_id}:{key}"
        self._redis, self._local_table = redis, _locks if local is None else local
        self.ttl_ms, self.wait_s = ttl_ms, wait_s
        self._token = None
        self._local = None
        self._shared = None

    def _local_lock(self):
        import asyncio

        table = self._local_table
        if not self.group_key:
            return asyncio.Lock()
        if len(table) > 10_000:
            for k in [k for k, lock in table.items() if not lock.locked()][:5_000]:
                table.pop(k, None)
        return table.setdefault((self.tenant_id, self.group_key), asyncio.Lock())

    async def _client(self):
        if self._redis is not None:
            return self._redis
        try:
            from events.management.cache.redis_manager import get_raw_client

            return await get_raw_client()
        except Exception:
            return None

    async def __aenter__(self):
        import asyncio
        import secrets
        import time

        self._local = self._local_lock()
        await self._local.acquire()
        if not self.group_key:
            return self
        try:
            client = await self._client()
            if client is None:
                return self
            token, deadline = secrets.token_hex(16), time.monotonic() + self.wait_s
            while not await client.set(self.key, token, nx=True, px=self.ttl_ms):
                if time.monotonic() > deadline:
                    raise TimeoutError(f"case grouping lock {self.key} is held")
                await asyncio.sleep(0.05)
            self._shared, self._token = client, token
        except TimeoutError:
            self._local.release()
            raise
        except Exception as e:  # Redis down: the local lock still serialises this process
            logger.warning("Case grouping lock unavailable in Redis; using the local lock", error=str(e))
        return self

    async def __aexit__(self, *exc):
        try:
            if self._shared is not None:
                await self._shared.eval(_RELEASE, 1, self.key, self._token)
        except Exception as e:
            logger.warning("Could not release the case grouping lock (it expires)", error=str(e))
        finally:
            self._local.release()
        return False


def _lock_for(tenant_id: str, key: str):
    """One lock per (tenant, entity key) so concurrent alerts for one entity open a
    single case, in this process and across API replicas."""
    return GroupLock(tenant_id, key)
