"""
SCIM tokens and externalId links against ClickHouse (Phase 14). Needs
migration 033 (LOGFORGE_TEST_CLICKHOUSE); skipped otherwise, unless
LOGFORGE_REQUIRE_CLICKHOUSE is set.
"""

import os
import uuid

import pytest
from test_logql_pipeline_live import _client


@pytest.fixture(scope="module")
def client():
    client = _client()
    if client is None or not client.query("EXISTS TABLE scim_tokens_mt").result_rows[0][0]:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse with migration 033 is required")
        pytest.skip("ClickHouse with migration 033 not reachable")
    return client


def test_tokens_resolve_to_their_tenant_until_revoked(client):
    from scim.tokens import TokenStore

    tenant = f"scim-live-{uuid.uuid4().hex[:8]}"
    store = TokenStore(client)
    created = store.create(tenant, "Okta", "admin")
    assert store.resolve(created["token"]) == tenant
    assert store.resolve(created["token"] + "x") is None and store.resolve("not-a-token") is None
    listed = store.list(tenant)
    assert [t["name"] for t in listed] == ["Okta"] and "token" not in listed[0] and "token_hash" not in listed[0]
    assert store.revoke(tenant, created["id"]) and store.resolve(created["token"]) is None
    assert store.list(tenant) == [] and not store.revoke("another-tenant", created["id"])


def test_external_ids_are_kept_per_tenant(client):
    from scim.tokens import LinkStore

    links = LinkStore(client)
    tenant, user = f"scim-live-{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    assert links.get(tenant, user) is None
    links.set(tenant, user, "00u1abcd")
    assert links.get(tenant, user) == "00u1abcd" and links.get("other", user) is None
