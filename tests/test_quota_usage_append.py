"""Quota usage is counted by appending to quota_usage_events_mt, never by an
ALTER TABLE ... UPDATE per request, and quotas are read with the counted usage."""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from dao.tenant_dao import TenantDAO  # noqa: E402

RESET = datetime(2026, 11, 1, tzinfo=timezone.utc)


class FakeDB:
    def __init__(self, quotas=None):
        self.queries = []
        self.quotas = quotas or []

    async def execute_query(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))
        if query.lstrip().upper().startswith("SELECT"):
            return self.quotas
        return []


def dao_with(db):
    dao = TenantDAO.__new__(TenantDAO)
    dao.db = db
    return dao


def test_add_quota_usage_appends_and_never_mutates():
    db = FakeDB()
    asyncio.run(dao_with(db).add_quota_usage("t1", "api_calls", RESET, 3))
    (sql, params), = db.queries
    assert sql.startswith("INSERT INTO quota_usage_events_mt")
    assert params == {"tenant_id": "t1", "quota_type": "api_calls", "reset_epoch": RESET, "amount": 3}
    assert "ALTER" not in sql.upper()


def test_quotas_are_read_with_counted_usage():
    db = FakeDB()
    asyncio.run(dao_with(db).get_tenant_quotas("t1"))
    assert "FROM tenant_quotas_v" in db.queries[0][0]


def test_usage_processor_counts_by_appending():
    from events.management.processors.usage_processor import update_tenant_quota_only

    db = FakeDB(quotas=[{"quota_type": "api_calls", "current_usage": 10, "last_reset": RESET}])

    class Service:
        tenant_dao = dao_with(db)

    asyncio.run(update_tenant_quota_only(Service(), "t1", "api_calls", 1))
    sqls = [q for q, _ in db.queries]
    assert any(q.startswith("INSERT INTO quota_usage_events_mt") for q in sqls)
    assert not any("ALTER TABLE" in q.upper() for q in sqls)
