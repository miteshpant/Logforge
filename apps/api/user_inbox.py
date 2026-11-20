"""
Per-user notifications: a case comment that @mentions you, or a case
assigned to you. Shown under the bell in the UI (/v1/inbox) and, when SMTP
is configured, emailed.

@name matches the part of a tenant member's email before the @, ignoring
case (@dana for dana@acme.example). A name matching no member, or several,
notifies nobody; the author isn't notified of their own comment.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

TABLE = "user_inbox_mt"


def resolve(members: Sequence[Dict[str, str]], names: Sequence[str]) -> Dict[str, Dict[str, str]]:
    """{name: member} for the names that match exactly one member."""
    by_local: Dict[str, List[Dict[str, str]]] = {}
    for m in members:
        by_local.setdefault(m["email"].split("@", 1)[0].lower(), []).append(m)
    out = {}
    for name in names:
        found = by_local.get(name.lower(), [])
        if len(found) == 1:
            out[name] = found[0]
    return out


def mention_notices(case: Any, text: str, actor: str, members: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    from cases import mentions_in

    notices, seen = [], set()
    for name, member in resolve(members, mentions_in(text)).items():
        if member["email"].lower() == actor.lower() or member["id"] in seen:
            continue
        seen.add(member["id"])
        notices.append({"user_id": member["id"], "email": member["email"], "kind": "mention",
                        "title": f"{actor} mentioned you in case {case.title}",
                        "body": text[:500], "link": f"/security/cases/{case.id}", "actor": actor})
    return notices


def assignment_notice(case: Any, actor: str, members: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    assignee = (case.assignee or "").lower()
    if not assignee or assignee == actor.lower():
        return []
    member = next((m for m in members if m["email"].lower() == assignee or m["id"] == case.assignee), None)
    if member is None:
        return []
    return [{"user_id": member["id"], "email": member["email"], "kind": "assigned",
             "title": f"{actor} assigned you case {case.title}", "body": f"Severity {case.severity}.",
             "link": f"/security/cases/{case.id}", "actor": actor}]


class Inbox:
    def __init__(self, client: Any):
        self.client = client

    def members(self, tenant_id: str) -> List[Dict[str, str]]:
        result = self.client.query(
            "SELECT u.id, any(u.email) FROM users_mt AS u INNER JOIN user_tenant_roles_mt AS r ON r.user_id = u.id "
            "WHERE r.tenant_id = {t:String} AND r.status = 'active' AND NOT endsWith(u.email, '.system') "
            "GROUP BY u.id", parameters={"t": tenant_id})
        return [{"id": r[0], "email": r[1]} for r in result.result_rows]

    def add(self, tenant_id: str, notices: Sequence[Dict[str, Any]], now: Optional[datetime] = None) -> List[str]:
        now = now or datetime.now(timezone.utc)
        rows, ids = [], []
        for n in notices:
            nid = uuid.uuid4().hex
            ids.append(nid)
            rows.append([tenant_id, n["user_id"], nid, n["kind"], n["title"], n["body"], n["link"], n["actor"],
                         0, now, now])
        if rows:
            self.client.insert(TABLE, rows, column_names=["tenant_id", "user_id", "id", "kind", "title", "body",
                                                          "link", "actor", "read", "created_at", "updated_at"])
        return ids

    def list(self, tenant_id: str, user_id: str, limit: int = 50) -> Dict[str, Any]:
        result = self.client.query(
            f"SELECT id, kind, title, body, link, actor, read, created_at FROM {TABLE} FINAL "
            "WHERE tenant_id = {t:String} AND user_id = {u:String} ORDER BY created_at DESC LIMIT {n:UInt32}",
            parameters={"t": tenant_id, "u": user_id, "n": limit})
        items = [dict(zip(["id", "kind", "title", "body", "link", "actor", "read", "created_at"], r))
                 for r in result.result_rows]
        for item in items:
            item["read"] = bool(item["read"])
            item["created_at"] = item["created_at"].isoformat()
        unread = self.client.query(
            f"SELECT count() FROM {TABLE} FINAL WHERE tenant_id = {{t:String}} AND user_id = {{u:String}} AND read = 0",
            parameters={"t": tenant_id, "u": user_id}).result_rows[0][0]
        return {"items": items, "unread": int(unread)}

    def mark_read(self, tenant_id: str, user_id: str, ids: Optional[Sequence[str]] = None,
                  now: Optional[datetime] = None) -> int:
        """Mark the given notifications (all unread if `ids` is None) read."""
        now = now or datetime.now(timezone.utc)
        where = "AND id IN {ids:Array(String)}" if ids is not None else ""
        result = self.client.query(
            f"SELECT tenant_id, user_id, id, kind, title, body, link, actor, created_at FROM {TABLE} FINAL "
            f"WHERE tenant_id = {{t:String}} AND user_id = {{u:String}} AND read = 0 {where}",
            parameters={"t": tenant_id, "u": user_id, "ids": list(ids or [])})
        rows = [list(r[:8]) + [1, r[8], now] for r in result.result_rows]
        if rows:
            self.client.insert(TABLE, rows, column_names=["tenant_id", "user_id", "id", "kind", "title", "body",
                                                          "link", "actor", "read", "created_at", "updated_at"])
        return len(rows)


async def notify(client: Any, tenant_id: str, build) -> int:
    """Store the notices `build(members)` returns and email them; never
    fails the caller (a case action has already been saved)."""
    import asyncio

    try:
        inbox = Inbox(client)
        notices = build(await asyncio.to_thread(inbox.members, tenant_id))
        if not notices:
            return 0
        await asyncio.to_thread(inbox.add, tenant_id, notices)
        # Emails go out in the background: an SMTP server taking its time
        # shouldn't hold up the case action.
        asyncio.create_task(_email(notices))
        return len(notices)
    except Exception as e:
        logger.warning("Notifications for tenant %s not delivered: %s", tenant_id, e)
        return 0


async def _email(notices: Sequence[Dict[str, Any]]) -> None:
    import account_emails

    for n in notices:
        try:
            await account_emails.send({"to": [n["email"]], "subject": n["title"],
                                       "body": f"{n['body']}\n\n{account_emails.public_url()}{n['link']}"})
        except Exception as e:
            logger.warning("Notification email not sent: %s", e)
