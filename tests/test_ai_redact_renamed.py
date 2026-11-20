"""Field-name redaction can't catch a value the query renames (`| eval v =
attrs.password` returns a column called v), so the AI's query tool refuses
queries that name a redacted field: the tenant's redact_fields and the asker's
masked fields."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from ai import assistant, tools  # noqa: E402
import field_masking  # noqa: E402

CTX = tools.ToolContext(tenant_id="acme", user_id="u1", roles=[{"tenant_id": "acme", "role": "tenant_admin"}])


@pytest.fixture
def settings(monkeypatch):
    async def logql(body, tenant_id):
        return {"logs": [{"service": "auth", "count": 3}]}

    monkeypatch.setattr(tools, "_logql", logql)


def test_a_query_naming_a_redacted_field_is_refused(settings):
    with assistant.redacting(["password"]):  # what an AI session with redact_fields sets
        with pytest.raises(tools.ToolError, match="password"):
            asyncio.run(tools.run_query(CTX, {"query": "| eval v = attrs.password | stats count() by v"}))


def test_masked_fields_count_too(settings):
    token = field_masking.set_fields(frozenset({"email"}))
    try:
        with pytest.raises(tools.ToolError, match="email"):
            asyncio.run(tools.run_query(CTX, {"query": "| stats count() by attrs.email"}))
    finally:
        field_masking.reset(token)


def test_other_queries_run(settings):
    with assistant.redacting(["password"]):
        out = asyncio.run(tools.run_query(CTX, {"query": "| stats count() by service"}))
    assert out is not None
