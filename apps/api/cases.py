"""
Cases (Phase 2): alerts become owned, tracked investigations.

Pure domain logic, no I/O. Every action returns the new case and the
timeline events it produced; the events are stored append-only and are both
the case timeline and its audit trail.

Status flow:

    new -> investigating -> contained -> resolved | false_positive
                 ^________________________________|   (reopen)

Closing (resolved / false_positive) needs a reason. The first move out of
`new`, or the first assignment, acknowledges the case (time to acknowledge);
closing sets resolved_at (time to resolve). Reopening clears the resolution
but keeps the acknowledgement.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

STATUSES = ("new", "investigating", "contained", "resolved", "false_positive")
CLOSED = ("resolved", "false_positive")
SEVERITIES = ("low", "medium", "high", "critical")
EVIDENCE_KINDS = ("search", "event", "trace", "log", "link", "file")
_MENTION = re.compile(r"(?<![\w.@])@([A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?)")

Event = Dict[str, Any]


class CaseError(ValueError):
    """An action that can't be applied to the case, with the reason."""


@dataclass
class Case:
    id: str
    tenant_id: str
    title: str
    severity: str = "medium"
    status: str = "new"
    assignee: Optional[str] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)
    alert_ids: List[str] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)
    group_key: str = ""
    created_by: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    contained_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    last_alert_at: Optional[datetime] = None
    close_reason: str = ""
    merged_into: str = ""

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED

    def to_row(self) -> Dict[str, Any]:
        row = asdict(self)
        row["entities"] = json.dumps(self.entities, sort_keys=True)
        return row

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Case":
        data = {k: row.get(k) for k in cls.__dataclass_fields__ if k in row}
        if isinstance(data.get("entities"), str):
            data["entities"] = json.loads(data["entities"] or "{}")
        for key in ("created_at", "updated_at", "acknowledged_at", "contained_at", "resolved_at", "last_alert_at"):
            data[key] = _as_time(data.get(key))
        for key in ("tags", "alert_ids"):
            data[key] = list(data.get(key) or [])
        data["assignee"] = data.get("assignee") or None
        for key in ("description", "group_key", "created_by", "close_reason", "merged_into"):
            data[key] = data.get(key) or ""
        return cls(**data)


def _as_time(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime):
        if value.year <= 1970:
            return None  # ClickHouse zero time stands for "not set"
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _event(case: Case, kind: str, actor: str, now: datetime, data: Optional[Dict[str, Any]] = None) -> Event:
    return {"id": str(uuid.uuid4()), "tenant_id": case.tenant_id, "case_id": case.id, "ts": now,
            "actor": actor, "kind": kind, "data": data or {}}


def _max_severity(*values: Optional[str]) -> str:
    known = [v for v in values if v in SEVERITIES]
    return max(known, key=SEVERITIES.index) if known else "medium"


def _merge_entities(base: Dict[str, List[str]], extra: Dict[str, Iterable[Any]]) -> Dict[str, List[str]]:
    merged = {k: list(v) for k, v in base.items()}
    for key, values in (extra or {}).items():
        values = [values] if isinstance(values, (str, int, float)) else list(values or [])
        bucket = merged.setdefault(str(key), [])
        for value in values:
            if value not in (None, "") and str(value) not in bucket:
                bucket.append(str(value))
        if not bucket:
            merged.pop(str(key))
    return merged


def mentions_in(text: str) -> List[str]:
    """@names in a comment, in order, without duplicates (emails excluded)."""
    seen: List[str] = []
    for name in _MENTION.findall(text or ""):
        if name not in seen:
            seen.append(name)
    return seen


def new_case(tenant_id: str, title: str, actor: str, now: datetime, severity: Optional[str] = None,
             description: str = "", tags: Sequence[str] = (), alerts: Sequence[Dict[str, Any]] = (),
             alert_ids: Sequence[str] = (), group_key: str = "", assignee: Optional[str] = None) -> Tuple[Case, List[Event]]:
    title = (title or "").strip()
    if not title:
        raise CaseError("a case needs a title")
    if severity is not None and severity not in SEVERITIES:
        raise CaseError(f"unknown severity {severity!r}")
    case = Case(id=str(uuid.uuid4()), tenant_id=tenant_id, title=title[:300], severity=severity or "low",
                description=description, tags=_unique(tags), alert_ids=_unique(alert_ids), group_key=group_key,
                created_by=actor, created_at=now, updated_at=now, assignee=assignee)
    events = [_event(case, "created", actor, now, {"title": case.title, "severity": severity or "low"})]
    if severity is None and not alerts:
        case.severity = "medium"
    for alert in alerts:
        case, attached = apply_action(case, "attach_alert", actor, now, alert=alert)
        events += attached
    return case, events


def _unique(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for value in values or []:
        value = str(value).strip()
        if value and value not in out:
            out.append(value)
    return out


def apply_action(case: Case, action: str, actor: str, now: datetime, **kwargs: Any) -> Tuple[Case, List[Event]]:
    handler = _ACTIONS.get(action)
    if handler is None:
        raise CaseError(f"unknown action {action!r}")
    updated, events = handler(case, actor, now, **kwargs)
    if events:
        updated = replace(updated, updated_at=now)
    return updated, events


def _attach_alert(case: Case, actor: str, now: datetime, alert: Dict[str, Any]) -> Tuple[Case, List[Event]]:
    alert_id = str(alert.get("id") or "")
    if not alert_id:
        raise CaseError("an alert needs an id")
    if alert_id in case.alert_ids:
        return case, []
    updated = replace(case, alert_ids=case.alert_ids + [alert_id],
                      severity=_max_severity(case.severity, alert.get("severity")),
                      entities=_merge_entities(case.entities, alert.get("entities") or {}),
                      last_alert_at=max(filter(None, [case.last_alert_at, now])))
    return updated, [_event(case, "alert_attached", actor, now, {
        "alert_id": alert_id, "rule_id": alert.get("rule_id"), "title": alert.get("title"),
        "severity": alert.get("severity")})]


def _set_status(case: Case, actor: str, now: datetime, status: str, reason: str = "") -> Tuple[Case, List[Event]]:
    if status not in STATUSES:
        raise CaseError(f"unknown status {status!r} (one of {', '.join(STATUSES)})")
    if status == case.status:
        raise CaseError(f"the case is already {status}")
    reason = (reason or "").strip()
    if status in CLOSED and not reason:
        raise CaseError("closing a case needs a reason")
    changes: Dict[str, Any] = {"status": status}
    if case.acknowledged_at is None and status != "new":
        changes["acknowledged_at"] = now
    if status == "contained" and case.contained_at is None:
        changes["contained_at"] = now
    if status in CLOSED:
        changes.update(resolved_at=now, close_reason=reason)
    elif case.status in CLOSED:
        changes.update(resolved_at=None, close_reason="", merged_into="")
    data: Dict[str, Any] = {"from": case.status, "to": status}
    if reason:
        data["reason"] = reason
    return replace(case, **changes), [_event(case, "status_changed", actor, now, data)]


def _assign(case: Case, actor: str, now: datetime, assignee: Optional[str]) -> Tuple[Case, List[Event]]:
    assignee = (assignee or "").strip() or None
    if assignee == case.assignee:
        return case, []
    changes: Dict[str, Any] = {"assignee": assignee}
    if assignee and case.acknowledged_at is None:
        changes["acknowledged_at"] = now
    return replace(case, **changes), [_event(case, "assigned", actor, now, {"from": case.assignee, "to": assignee})]


def _comment(case: Case, actor: str, now: datetime, text: str) -> Tuple[Case, List[Event]]:
    text = (text or "").strip()
    if not text:
        raise CaseError("a comment can't be empty")
    if len(text) > 10_000:
        raise CaseError("a comment is limited to 10,000 characters")
    return case, [_event(case, "comment", actor, now, {"text": text, "mentions": mentions_in(text)})]


def _tags(case: Case, actor: str, now: datetime, add: Sequence[str] = (), remove: Sequence[str] = ()) -> Tuple[Case, List[Event]]:
    removed = set(_unique(remove))
    tags = [t for t in _unique(list(case.tags) + _unique(add)) if t not in removed]
    if tags == case.tags:
        return case, []
    return replace(case, tags=tags), [_event(case, "tags_changed", actor, now, {"from": case.tags, "to": tags})]


def _pin_evidence(case: Case, actor: str, now: datetime, evidence: Dict[str, Any]) -> Tuple[Case, List[Event]]:
    kind = (evidence or {}).get("kind")
    if kind not in EVIDENCE_KINDS:
        raise CaseError(f"unknown evidence kind {kind!r} (one of {', '.join(EVIDENCE_KINDS)})")
    ref = str(evidence.get("ref") or "").strip()
    if not ref:
        raise CaseError("evidence needs a ref (query, event id, trace id or URL)")
    data = {"kind": kind, "ref": ref, "title": str(evidence.get("title") or ref)[:300]}
    if evidence.get("data") is not None:
        data["data"] = evidence["data"]
    return case, [_event(case, "evidence_pinned", actor, now, data)]


def _unpin_evidence(case: Case, actor: str, now: datetime, evidence_id: str) -> Tuple[Case, List[Event]]:
    """Take back a pin: the pin stays in the timeline, marked as taken back."""
    evidence_id = str(evidence_id or "").strip()
    if not evidence_id:
        raise CaseError("unpinning needs the evidence_id of the pin")
    return case, [_event(case, "evidence_unpinned", actor, now, {"evidence_id": evidence_id})]


def pinned_evidence(timeline: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The pins in a timeline that haven't been taken back, in order."""
    taken_back = {str((e.get("data") or {}).get("evidence_id")) for e in timeline if e.get("kind") == "evidence_unpinned"}
    return [e for e in timeline if e.get("kind") == "evidence_pinned" and str(e.get("id")) not in taken_back]


def _describe(case: Case, actor: str, now: datetime, title: Optional[str] = None,
              description: Optional[str] = None, severity: Optional[str] = None) -> Tuple[Case, List[Event]]:
    changes: Dict[str, Any] = {}
    if title is not None and title.strip() and title.strip() != case.title:
        changes["title"] = title.strip()[:300]
    if description is not None and description != case.description:
        changes["description"] = description
    if severity is not None and severity != case.severity:
        if severity not in SEVERITIES:
            raise CaseError(f"unknown severity {severity!r}")
        changes["severity"] = severity
    if not changes:
        return case, []
    return replace(case, **changes), [_event(case, "updated", actor, now, {
        k: {"from": getattr(case, k), "to": v} for k, v in changes.items()})]


_ACTIONS = {
    "attach_alert": _attach_alert,
    "set_status": _set_status,
    "assign": _assign,
    "comment": _comment,
    "tags": _tags,
    "pin_evidence": _pin_evidence,
    "unpin_evidence": _unpin_evidence,
    "update": _describe,
}


def merge_cases(target: Case, sources: Sequence[Case], actor: str, now: datetime) -> Tuple[Case, List[Case], List[Event]]:
    """Move the sources' alerts, entities and tags into `target`; the
    sources are closed as merged."""
    if not sources:
        raise CaseError("nothing to merge")
    for source in sources:
        if source.tenant_id != target.tenant_id:
            raise CaseError("cases from another tenant can't be merged")
        if source.id == target.id:
            raise CaseError("a case can't be merged into itself")
    merged = target
    events: List[Event] = []
    closed: List[Case] = []
    for source in sources:
        merged = replace(merged,
                         alert_ids=merged.alert_ids + [a for a in source.alert_ids if a not in merged.alert_ids],
                         entities=_merge_entities(merged.entities, source.entities),
                         severity=_max_severity(merged.severity, source.severity),
                         tags=_unique(merged.tags + source.tags),
                         last_alert_at=max(filter(None, [merged.last_alert_at, source.last_alert_at]), default=None))
        closed.append(replace(source, status="resolved", resolved_at=now, close_reason=f"merged into {target.id}",
                              merged_into=target.id, updated_at=now,
                              acknowledged_at=source.acknowledged_at or now))
        events.append(_event(source, "merged_into", actor, now, {"target": target.id}))
    merged = replace(merged, updated_at=now)
    events.append(_event(target, "merged", actor, now, {"sources": [s.id for s in sources],
                                                        "alerts": len(merged.alert_ids) - len(target.alert_ids)}))
    return merged, closed, events


def split_case(case: Case, alert_ids: Sequence[str], actor: str, now: datetime,
               title: Optional[str] = None) -> Tuple[Case, Case, List[Event]]:
    """Move some alerts into a new case."""
    moving = _unique(alert_ids)
    missing = [a for a in moving if a not in case.alert_ids]
    if missing:
        raise CaseError(f"alerts not in the case: {', '.join(missing)}")
    if not moving or len(moving) == len(case.alert_ids):
        raise CaseError("a split must move some alerts and leave at least one")
    created, created_events = new_case(case.tenant_id, title or f"Split from: {case.title}", actor, now,
                                       severity=case.severity, alert_ids=moving, tags=case.tags)
    created = replace(created, last_alert_at=case.last_alert_at)
    remaining = replace(case, alert_ids=[a for a in case.alert_ids if a not in moving], updated_at=now)
    events = [_event(case, "split", actor, now, {"alert_ids": moving, "new_case": created.id})]
    events += created_events
    events.append(_event(created, "split_from", actor, now, {"case_id": case.id, "alert_ids": moving}))
    return remaining, created, events
