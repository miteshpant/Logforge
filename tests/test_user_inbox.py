"""
Per-user notifications: @mentions in case comments and case assignments
reach the person (inbox, and email when SMTP is configured).
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import user_inbox

MEMBERS = [{"id": "u1", "email": "dana@acme.example"}, {"id": "u2", "email": "sam@acme.example"},
           {"id": "u3", "email": "sam@other.example"}, {"id": "u4", "email": "Lee.Ward@acme.example"}]
CASE = SimpleNamespace(id="c1", title="Brute force on web-01", severity="high", assignee="dana@acme.example")


def test_mentions_resolve_to_one_member_by_the_email_name():
    notices = user_inbox.mention_notices(CASE, "@lee.ward and @DANA please look; @sam @nobody", "x@acme.example",
                                         MEMBERS)
    assert [n["user_id"] for n in notices] == ["u4", "u1"]  # @sam is ambiguous, @nobody unknown
    assert notices[0]["link"] == "/security/cases/c1" and "mentioned you" in notices[0]["title"]


def test_the_author_isnt_notified_of_their_own_mention():
    assert user_inbox.mention_notices(CASE, "@dana note to self", "dana@acme.example", MEMBERS) == []


def test_assignment_notifies_the_assignee_unless_self_assigned():
    [notice] = user_inbox.assignment_notice(CASE, "sam@acme.example", MEMBERS)
    assert notice["user_id"] == "u1" and notice["kind"] == "assigned"
    assert user_inbox.assignment_notice(CASE, "dana@acme.example", MEMBERS) == []
    assert user_inbox.assignment_notice(SimpleNamespace(**{**CASE.__dict__, "assignee": None}), "x", MEMBERS) == []


class FakeClient:
    def __init__(self):
        self.rows = []

    def insert(self, table, rows, column_names):
        self.rows += [dict(zip(column_names, r)) for r in rows]

    def query(self, sql, parameters):
        latest = {}
        for r in self.rows:
            key = (r["tenant_id"], r["user_id"], r["id"])
            if key not in latest or r["updated_at"] >= latest[key]["updated_at"]:
                latest[key] = r
        mine = [r for r in latest.values() if r["tenant_id"] == parameters["t"] and r["user_id"] == parameters["u"]]
        if sql.startswith("SELECT count()"):
            return SimpleNamespace(result_rows=[[sum(1 for r in mine if not r["read"])]])
        if "read = 0" in sql:
            mine = [r for r in mine if not r["read"] and (not parameters["ids"] or r["id"] in parameters["ids"])]
            return SimpleNamespace(result_rows=[[r[c] for c in ("tenant_id", "user_id", "id", "kind", "title", "body",
                                                                 "link", "actor", "created_at")] for r in mine])
        mine.sort(key=lambda r: r["created_at"], reverse=True)
        return SimpleNamespace(result_rows=[[r[c] for c in ("id", "kind", "title", "body", "link", "actor", "read",
                                                             "created_at")] for r in mine])


def test_inbox_lists_and_marks_read():
    inbox = user_inbox.Inbox(FakeClient())
    t0 = datetime(2026, 11, 20, tzinfo=timezone.utc)
    notices = user_inbox.mention_notices(CASE, "@dana @sam", "lee.ward@acme.example", MEMBERS[:2])
    ids = inbox.add("acme", notices + notices[:1], now=t0)
    listed = inbox.list("acme", "u1")
    assert listed["unread"] == 2 and len(listed["items"]) == 2
    assert inbox.mark_read("acme", "u1", [ids[0]]) == 1
    assert inbox.list("acme", "u1")["unread"] == 1
    assert inbox.mark_read("acme", "u1") == 1
    assert inbox.list("acme", "u1")["unread"] == 0 and inbox.list("acme", "u2")["unread"] == 1


def test_inbox_is_open_to_every_role():
    from authn_authz_middleware import UserRole, check_permission, get_endpoint_permission

    need = get_endpoint_permission("/v1/inbox", "GET")
    assert all(check_permission([{"tenant_id": "t", "role": r.value}], need, "t")
               for r in (UserRole.TENANT_ADMIN, UserRole.SECURITY_ANALYST, UserRole.DEVOPS_ENGINEER,
                         UserRole.COMPLIANCE_OFFICER, UserRole.VIEWER))
