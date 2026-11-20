"""
Support tickets: a tenant member asks the platform's support, platform admins
answer in the admin UI. A reply from support marks the ticket `answered` and
notifies the requester (bell and email, user_inbox); a reply from the
customer reopens it (`open`); either side can close it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

TABLE = "support_tickets_mt"
STATUSES = ("open", "answered", "closed")
PRIORITIES = ("low", "normal", "high", "urgent")
_COLUMNS = ["tenant_id", "id", "subject", "status", "priority", "created_by", "created_by_id", "messages",
            "created_at", "updated_at"]


class TicketError(ValueError):
    pass


@dataclass
class Ticket:
    tenant_id: str
    id: str
    subject: str
    status: str
    priority: str
    created_by: str
    created_by_id: str
    created_at: datetime
    updated_at: datetime
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def public(self) -> Dict[str, Any]:
        return {"id": self.id, "tenant_id": self.tenant_id, "subject": self.subject, "status": self.status,
                "priority": self.priority, "created_by": self.created_by,
                "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat(),
                "messages": self.messages}


def _text(text: str) -> str:
    text = (text or "").strip()
    if not text or len(text) > 10_000:
        raise TicketError("a message needs 1 to 10,000 characters")
    return text


def open_ticket(tenant_id: str, subject: str, text: str, priority: str, author: str, author_id: str,
                now: Optional[datetime] = None) -> Ticket:
    now = now or datetime.now(timezone.utc)
    subject = (subject or "").strip()
    if not 3 <= len(subject) <= 200:
        raise TicketError("the subject needs 3 to 200 characters")
    if priority not in PRIORITIES:
        raise TicketError(f"priority is one of {', '.join(PRIORITIES)}")
    return Ticket(tenant_id, uuid.uuid4().hex, subject, "open", priority, author, author_id, now, now,
                  [{"author": author, "from": "customer", "text": _text(text), "at": now.isoformat()}])


def reply(ticket: Ticket, text: str, author: str, from_support: bool, now: Optional[datetime] = None) -> Ticket:
    if ticket.status == "closed" and not from_support:
        raise TicketError("this ticket is closed; open a new one")
    now = now or datetime.now(timezone.utc)
    message = {"author": author, "from": "support" if from_support else "customer", "text": _text(text),
               "at": now.isoformat()}
    return Ticket(**{**ticket.__dict__, "messages": ticket.messages + [message],
                     "status": "answered" if from_support else "open", "updated_at": now})


def update(ticket: Ticket, status: Optional[str] = None, priority: Optional[str] = None,
           now: Optional[datetime] = None) -> Ticket:
    if status is not None and status not in STATUSES:
        raise TicketError(f"status is one of {', '.join(STATUSES)}")
    if priority is not None and priority not in PRIORITIES:
        raise TicketError(f"priority is one of {', '.join(PRIORITIES)}")
    return Ticket(**{**ticket.__dict__, "status": status or ticket.status, "priority": priority or ticket.priority,
                     "updated_at": now or datetime.now(timezone.utc)})


class TicketStore:
    def __init__(self, client: Any):
        self.client = client

    def save(self, t: Ticket) -> None:
        self.client.insert(TABLE, [[t.tenant_id, t.id, t.subject, t.status, t.priority, t.created_by,
                                    t.created_by_id, json.dumps(t.messages), t.created_at, t.updated_at]],
                           column_names=_COLUMNS)

    def _rows(self, where: str, params: Dict[str, Any], limit: int = 500) -> List[Ticket]:
        result = self.client.query(
            f"SELECT {', '.join(_COLUMNS)} FROM {TABLE} FINAL WHERE {where} ORDER BY updated_at DESC "
            f"LIMIT {int(limit)}", parameters=params)
        tickets = []
        for r in result.result_rows:
            row = dict(zip(_COLUMNS, r))
            row["messages"] = json.loads(row["messages"] or "[]")
            for k in ("created_at", "updated_at"):
                if row[k].tzinfo is None:
                    row[k] = row[k].replace(tzinfo=timezone.utc)
            tickets.append(Ticket(**row))
        return tickets

    def list(self, tenant_id: Optional[str] = None, status: Optional[str] = None, limit: int = 200) -> List[Ticket]:
        clauses, params = ["1"], {}
        if tenant_id is not None:
            clauses.append("tenant_id = {t:String}")
            params["t"] = tenant_id
        if status:
            clauses.append("status = {s:String}")
            params["s"] = status
        return self._rows(" AND ".join(clauses), params, limit)

    def get(self, ticket_id: str, tenant_id: Optional[str] = None) -> Optional[Ticket]:
        where, params = "id = {id:String}", {"id": ticket_id}
        if tenant_id is not None:
            where += " AND tenant_id = {t:String}"
            params["t"] = tenant_id
        found = self._rows(where, params, 1)
        return found[0] if found else None
