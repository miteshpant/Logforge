"""
Saved and scheduled searches (Phase 6).

A saved search is a named LogforgeQL query. With `every` it runs on a
schedule over the last `window`; each run is recorded, and it can

* alert: when the result meets a condition (the row count, or a numeric
  field in any row) it writes an alert instance and delivers it to
  notification channels, at most once per `throttle_minutes`;
* report: send the result (rows and a CSV) to notification channels, on
  every run or only when it alerts.

A run that fails is recorded as an error. It is never treated as "no
results": that would fire absence alerts on every database hiccup.

Storage (migration 022): saved_searches_mt keeps every version of a
definition; saved_search_runs_mt keeps the run history.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_EVERY_SECONDS = 5 * 60
MAX_EVERY_SECONDS = 7 * 86400
MAX_WINDOW_SECONDS = 31 * 86400
DEFAULT_WINDOW = "24h"
MAX_RUNS_PER_TENANT_PER_CYCLE = int(os.getenv("LOGFORGE_SEARCH_RUNS_PER_TENANT", "25"))
MAX_REPORT_ROWS = 1000
MAX_ALERT_SAMPLE = 20
_DURATION_RE = re.compile(r"^(\d+)\s*(m|h|d|w)$")
_UNIT = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
_OPS = {"gt": lambda a, b: a > b, "gte": lambda a, b: a >= b, "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b, "eq": lambda a, b: a == b, "ne": lambda a, b: a != b}
SEVERITIES = ("low", "medium", "high", "critical")


class SearchValidationError(ValueError):
    """A saved search that cannot be stored. The message is shown to the user."""


def duration_seconds(text: Any, what: str) -> int:
    match = _DURATION_RE.match(str(text or "").strip().lower())
    if not match or int(match.group(1)) <= 0:
        raise SearchValidationError(f"{what} must be a duration like 15m, 1h, 1d or 1w, got {text!r}")
    return int(match.group(1)) * _UNIT[match.group(2)]


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:64]


@dataclass
class Condition:
    kind: str                     # rows | field
    op: str
    value: float
    field: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Condition":
        if not isinstance(data, dict):
            raise SearchValidationError("alert.condition must be an object")
        kind = data.get("kind", "rows")
        if kind not in ("rows", "field"):
            raise SearchValidationError("alert.condition.kind must be rows or field")
        op = data.get("op", "gt")
        if op not in _OPS:
            raise SearchValidationError(f"alert.condition.op must be one of {', '.join(_OPS)}")
        value = data.get("value", 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SearchValidationError("alert.condition.value must be a number")
        name = data.get("field")
        if kind == "field" and (not isinstance(name, str) or not name):
            raise SearchValidationError("alert.condition needs a field when kind is field")
        return cls(kind=kind, op=op, value=value, field=name if kind == "field" else None)


@dataclass
class AlertAction:
    condition: Condition
    severity: str = "medium"
    channels: List[str] = field(default_factory=list)
    throttle_minutes: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertAction":
        if not isinstance(data, dict):
            raise SearchValidationError("alert must be an object")
        severity = data.get("severity", "medium")
        if severity not in SEVERITIES:
            raise SearchValidationError(f"alert.severity must be one of {', '.join(SEVERITIES)}")
        channels = _channels(data.get("channels", []), "alert", required=False)
        throttle = data.get("throttle_minutes", 0)
        if isinstance(throttle, bool) or not isinstance(throttle, int) or not 0 <= throttle <= 7 * 1440:
            raise SearchValidationError("alert.throttle_minutes must be a whole number of minutes (up to 7 days)")
        return cls(condition=Condition.from_dict(data.get("condition", {})), severity=severity,
                   channels=channels, throttle_minutes=throttle)


@dataclass
class ReportAction:
    channels: List[str]
    when: str = "always"          # always | alert

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportAction":
        if not isinstance(data, dict):
            raise SearchValidationError("report must be an object")
        when = data.get("when", "always")
        if when not in ("always", "alert"):
            raise SearchValidationError("report.when must be always or alert")
        return cls(channels=_channels(data.get("channels", []), "report", required=True), when=when)


def _channels(value: Any, where: str, required: bool) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(c, str) and c for c in value) or len(value) > 20:
        raise SearchValidationError(f"{where}.channels must be a list of notification channel ids")
    if required and not value:
        raise SearchValidationError(f"{where} needs at least one channel")
    return list(dict.fromkeys(value))


@dataclass
class SavedSearch:
    id: str
    name: str
    query: str
    description: str = ""
    every: Optional[str] = None
    window: str = DEFAULT_WINDOW
    enabled: bool = True
    alert: Optional[AlertAction] = None
    report: Optional[ReportAction] = None
    version: int = 0
    updated_at: Optional[datetime] = None
    updated_by: str = ""

    @property
    def every_seconds(self) -> Optional[int]:
        return duration_seconds(self.every, "every") if self.every else None

    @property
    def window_seconds(self) -> int:
        return duration_seconds(self.window, "window")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SavedSearch":
        if not isinstance(data, dict):
            raise SearchValidationError("A saved search must be an object")
        name = str(data.get("name") or "").strip()
        if not name or len(name) > 200:
            raise SearchValidationError("A saved search needs a name (up to 200 characters)")
        query = data.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 20_000:
            raise SearchValidationError("A saved search needs a query (up to 20,000 characters)")
        search_id = data.get("id") or slug(name)
        if not re.match(r"^[a-z0-9][a-z0-9_]{0,63}$", str(search_id)):
            raise SearchValidationError("id must be lowercase letters, digits and _")
        every = data.get("every")
        if every:
            seconds = duration_seconds(every, "every")
            if seconds < MIN_EVERY_SECONDS:
                raise SearchValidationError("every must be at least 5m")
            if seconds > MAX_EVERY_SECONDS:
                raise SearchValidationError("every can be at most 7d")
        window = data.get("window") or (every if every else DEFAULT_WINDOW)
        if duration_seconds(window, "window") > MAX_WINDOW_SECONDS:
            raise SearchValidationError("window can be at most 31d")
        return cls(id=str(search_id), name=name, query=query, description=str(data.get("description") or "")[:1000],
                   every=str(every) if every else None, window=str(window), enabled=bool(data.get("enabled", True)),
                   alert=AlertAction.from_dict(data["alert"]) if data.get("alert") else None,
                   report=ReportAction.from_dict(data["report"]) if data.get("report") else None,
                   version=int(data.get("version") or 0), updated_at=data.get("updated_at"),
                   updated_by=str(data.get("updated_by") or ""))

    def definition(self) -> Dict[str, Any]:
        return {"query": self.query, "every": self.every, "window": self.window,
                "alert": asdict(self.alert) if self.alert else None,
                "report": asdict(self.report) if self.report else None}

    def to_public(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": self.description, "enabled": self.enabled,
                **self.definition(), "version": self.version,
                "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else
                self.updated_at, "updated_by": self.updated_by}


@dataclass
class Run:
    search_id: str
    run_at: datetime
    window_start: datetime
    window_end: datetime
    trigger: str = "schedule"     # schedule | manual
    status: str = "ok"            # ok | error
    rows: int = 0
    fired: bool = False           # the alert condition held
    alerted: bool = False         # an alert was written
    throttled: bool = False
    value: Optional[float] = None
    duration_ms: float = 0.0
    error: str = ""
    alert_id: str = ""

    def to_public(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("run_at", "window_start", "window_end"):
            data[key] = data[key].isoformat() if isinstance(data[key], datetime) else data[key]
        return data


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN is not a value


def evaluate(condition: Condition, rows: List[Dict[str, Any]]) -> Tuple[bool, Optional[float]]:
    """(condition met, the value it was judged on). For a field condition the
    value is the best candidate: the first row that meets it, otherwise the
    largest (gt/gte) or smallest (lt/lte) value seen."""
    test = _OPS[condition.op]
    if condition.kind == "rows":
        count = len(rows)
        return test(count, condition.value), count
    values = [v for v in (_number(r.get(condition.field)) for r in rows) if v is not None]
    for v in values:
        if test(v, condition.value):
            return True, _plain(v)
    if not values:
        return False, None
    best = min(values) if condition.op in ("lt", "lte") else max(values)
    return False, _plain(best)


def _plain(value: float) -> float:
    return int(value) if float(value).is_integer() else value


def is_due(search: SavedSearch, last_run_at: Optional[datetime], now: datetime) -> bool:
    if not search.enabled or not search.every:
        return False
    if last_run_at is None:
        return True
    return (now - last_run_at).total_seconds() >= search.every_seconds - 1


def to_csv(columns: List[str], rows: List[Dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if row.get(c) is None else _cell(row.get(c)) for c in columns])
    return out.getvalue()


def _cell(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    text = str(value)
    # A CSV opened in a spreadsheet must not execute what a log line put there.
    return "'" + text if text[:1] in ("=", "+", "-", "@") and not _number(text) else text


Execute = Callable[[str, str, datetime, datetime], Awaitable[Dict[str, Any]]]
AlertSink = Callable[[str, SavedSearch, Run, Dict[str, Any]], Awaitable[str]]
Send = Callable[[str, str, Dict[str, Any], str], Awaitable[Any]]


class Runner:
    def __init__(self, store, execute: Execute, alert: Callable[..., Awaitable[str]], send: Send):
        self.store, self.execute, self.alert, self.send = store, execute, alert, send

    async def run_due(self, now: Optional[datetime] = None) -> List[Run]:
        now = now or datetime.now(timezone.utc)
        runs: List[Run] = []
        per_tenant: Dict[str, int] = {}
        for tenant_id, search in await self.store.scheduled():
            last = await self.store.last_runs(tenant_id, search.id, limit=1)
            if not is_due(search, last[0].run_at if last else None, now):
                continue
            if per_tenant.get(tenant_id, 0) >= MAX_RUNS_PER_TENANT_PER_CYCLE:
                logger.warning(f"Tenant {tenant_id} has more due searches than the per-cycle cap; "
                               f"{search.id} waits for the next cycle")
                continue
            per_tenant[tenant_id] = per_tenant.get(tenant_id, 0) + 1
            run, _ = await self.run(tenant_id, search, now)
            runs.append(run)
        return runs

    async def run(self, tenant_id: str, search: SavedSearch, now: Optional[datetime] = None,
                  trigger: str = "schedule", dry_run: bool = False) -> Tuple[Run, Optional[Dict[str, Any]]]:
        now = now or datetime.now(timezone.utc)
        start = now - timedelta(seconds=search.window_seconds)
        run = Run(search_id=search.id, run_at=now, window_start=start, window_end=now, trigger=trigger)
        began = asyncio.get_event_loop().time()
        result: Optional[Dict[str, Any]] = None
        try:
            result = await self.execute(search.query, tenant_id, start, now)
        except Exception as e:
            logger.error(f"Saved search {search.id} for tenant {tenant_id} failed: {e}")
            run.status = "error"
            run.error = getattr(e, "detail", None) if isinstance(getattr(e, "detail", None), str) else \
                "The search failed; see the API logs"
        run.duration_ms = round((asyncio.get_event_loop().time() - began) * 1000, 2)
        if result is not None:
            rows = result.get("rows") or []
            run.rows = len(rows)
            if search.alert:
                run.fired, run.value = evaluate(search.alert.condition, rows)
        if dry_run:
            return run, result
        if run.fired and search.alert:
            last = await self.store.last_fired(tenant_id, search.id)
            throttle = timedelta(minutes=search.alert.throttle_minutes)
            if last is not None and throttle and now - last < throttle:
                run.throttled = True
            else:
                await self._alert(tenant_id, search, run, result or {})
        if search.report and result is not None and (search.report.when == "always" or run.alerted):
            await self._report(tenant_id, search, run, result)
        await self.store.record_run(tenant_id, run)
        return run, result

    def _window(self, run: Run) -> Dict[str, str]:
        return {"start": run.window_start.isoformat(), "end": run.window_end.isoformat()}

    async def _alert(self, tenant_id: str, search: SavedSearch, run: Run, result: Dict[str, Any]) -> None:
        try:
            run.alert_id = await self.alert(tenant_id, search, run, result) or ""
            run.alerted = True
        except Exception as e:
            logger.error(f"Saved search {search.id}: could not write the alert: {e}")
            return
        condition = search.alert.condition
        subject = "rows" if condition.kind == "rows" else condition.field
        payload = {"title": f"Search alert: {search.name}", "severity": search.alert.severity,
                   "message": f"{search.name}: {subject} {condition.op} {condition.value} "
                              f"(value: {run.value}, {run.rows} rows)",
                   "search": {"id": search.id, "name": search.name, "query": search.query},
                   "window": self._window(run), "alert_id": run.alert_id,
                   "rows": (result.get("rows") or [])[:MAX_ALERT_SAMPLE]}
        payload["description"] = payload["message"]
        for channel in search.alert.channels:
            await self._send(tenant_id, channel, payload, "search.alert")

    async def _report(self, tenant_id: str, search: SavedSearch, run: Run, result: Dict[str, Any]) -> None:
        rows = (result.get("rows") or [])[:MAX_REPORT_ROWS]
        columns = result.get("columns") or (list(rows[0]) if rows else [])
        payload = {"title": f"Search report: {search.name}",
                   "message": f"{search.name}: {run.rows} rows from {run.window_start:%Y-%m-%d %H:%M} to "
                              f"{run.window_end:%Y-%m-%d %H:%M} UTC",
                   "search": {"id": search.id, "name": search.name, "query": search.query},
                   "window": self._window(run), "columns": columns, "rows": rows,
                   "truncated": bool(result.get("truncated")) or run.rows > MAX_REPORT_ROWS,
                   "csv": to_csv(columns, rows)}
        payload["description"] = payload["message"]
        for channel in search.report.channels:
            await self._send(tenant_id, channel, payload, "search.report")

    async def _send(self, tenant_id: str, channel: str, payload: Dict[str, Any], event_type: str) -> None:
        try:
            await self.send(tenant_id, channel, payload, event_type)
        except Exception as e:  # one channel failing must not stop the others
            logger.error(f"Delivery of {event_type} to channel {channel} failed: {e}")


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_SEARCH_COLUMNS = ["tenant_id", "search_id", "version", "name", "description", "definition", "enabled", "deleted",
                   "updated_at", "updated_by"]
_RUN_COLUMNS = ["tenant_id", "search_id", "run_at", "window_start", "window_end", "trigger", "status", "rows",
                "fired", "alerted", "throttled", "value", "duration_ms", "error", "alert_id"]


class SearchStore:
    def __init__(self, db=None):
        if db is None:
            from database_layer import DatabaseLayer

            db = DatabaseLayer("SavedSearchDAO", os.getenv("SAVED_SEARCH_SERVICE_KEY", "saved-search-service-key"))
        self.db = db

    @staticmethod
    def _search(row: Dict[str, Any]) -> Optional[SavedSearch]:
        try:
            definition = json.loads(row["definition"])
            return SavedSearch.from_dict({**definition, "id": row["search_id"], "name": row["name"],
                                          "description": row.get("description", ""),
                                          "enabled": bool(row["enabled"]), "version": row["version"],
                                          "updated_at": row.get("updated_at"),
                                          "updated_by": row.get("updated_by", "")})
        except (SearchValidationError, ValueError, KeyError, TypeError) as e:
            logger.warning(f"Skipping invalid stored saved search {row.get('search_id')}: {e}")
            return None

    async def _latest(self, tenant_id: Optional[str] = None, search_id: Optional[str] = None):
        where, params = [], {}
        if tenant_id is not None:
            where.append("tenant_id = %(tenant_id)s")
            params["tenant_id"] = tenant_id
        if search_id is not None:
            where.append("search_id = %(search_id)s")
            params["search_id"] = search_id
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return await self.db.fetch_all(
            f"SELECT * FROM saved_searches_mt {clause} ORDER BY tenant_id, search_id, version DESC "
            "LIMIT 1 BY tenant_id, search_id", params) or []

    async def list(self, tenant_id: str) -> List[SavedSearch]:
        found = [self._search(r) for r in await self._latest(tenant_id) if not r.get("deleted")]
        return [s for s in found if s is not None]

    async def get(self, tenant_id: str, search_id: str) -> Optional[SavedSearch]:
        rows = await self._latest(tenant_id, search_id)
        if not rows or rows[0].get("deleted"):
            return None
        return self._search(rows[0])

    async def _write(self, tenant_id: str, search: SavedSearch, actor: str, deleted: bool) -> None:
        await self.db.insert_rows("saved_searches_mt", [[
            tenant_id, search.id, search.version, search.name, search.description,
            json.dumps(search.definition()), int(search.enabled), int(deleted), datetime.now(timezone.utc), actor]],
            _SEARCH_COLUMNS)

    async def save(self, tenant_id: str, search: SavedSearch, actor: str) -> SavedSearch:
        rows = await self._latest(tenant_id, search.id)
        search.version = int(rows[0]["version"]) + 1 if rows else 1
        search.updated_by, search.updated_at = actor, datetime.now(timezone.utc)
        await self._write(tenant_id, search, actor, deleted=False)
        return search

    async def delete(self, tenant_id: str, search_id: str, actor: str) -> None:
        current = await self.get(tenant_id, search_id)
        if current is None:
            return
        current.version += 1
        await self._write(tenant_id, current, actor, deleted=True)

    async def scheduled(self) -> List[Tuple[str, SavedSearch]]:
        found = []
        for row in await self._latest():
            if row.get("deleted") or not row.get("enabled"):
                continue
            search = self._search(row)
            if search is not None and search.every:
                found.append((row["tenant_id"], search))
        return found

    async def record_run(self, tenant_id: str, run: Run) -> None:
        data = asdict(run)
        data["value"] = float(run.value) if run.value is not None else None
        await self.db.insert_rows("saved_search_runs_mt",
                                  [[tenant_id] + [data[c] for c in _RUN_COLUMNS[1:]]], _RUN_COLUMNS)

    @staticmethod
    def _run(row: Dict[str, Any]) -> Run:
        return Run(**{c: row[c] for c in _RUN_COLUMNS[1:]})

    async def last_runs(self, tenant_id: str, search_id: Optional[str] = None, limit: int = 1) -> List[Run]:
        params: Dict[str, Any] = {"tenant_id": tenant_id, "limit": int(limit)}
        where = "tenant_id = %(tenant_id)s"
        if search_id:
            where += " AND search_id = %(search_id)s"
            params["search_id"] = search_id
        rows = await self.db.fetch_all(
            f"SELECT * FROM saved_search_runs_mt WHERE {where} ORDER BY run_at DESC LIMIT %(limit)s", params) or []
        return [self._run(r) for r in rows]

    async def last_fired(self, tenant_id: str, search_id: str) -> Optional[datetime]:
        row = await self.db.fetch_one(
            "SELECT max(run_at) AS at FROM saved_search_runs_mt WHERE tenant_id = %(tenant_id)s "
            "AND search_id = %(search_id)s AND alerted = 1", {"tenant_id": tenant_id, "search_id": search_id})
        at = row.get("at") if row else None
        if at is None or (isinstance(at, datetime) and at.year < 1971):
            return None
        return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at
