"""
SSO providers against ClickHouse (Phase 14): the real store, with the
client secret sealed at rest. Needs migration 032 (LOGFORGE_TEST_CLICKHOUSE);
skipped otherwise, unless LOGFORGE_REQUIRE_CLICKHOUSE is set.
"""

import os
import uuid

import pytest
from test_logql_pipeline_live import _client


@pytest.fixture(scope="module")
def client():
    client = _client()
    if client is None or not client.query("EXISTS TABLE sso_providers_mt").result_rows[0][0]:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse with migration 032 is required")
        pytest.skip("ClickHouse with migration 032 not reachable")
    return client


def test_providers_round_trip_with_the_secret_sealed(client):
    from sso.oidc import Provider
    from sso.store import ProviderStore

    tenant, domain = f"sso-live-{uuid.uuid4().hex[:8]}", f"{uuid.uuid4().hex[:8]}.example"
    store = ProviderStore(client)  # the real constructor, keys from the environment
    saved = store.save(Provider(id="", tenant_id=tenant, name="Okta\tprod", issuer="https://idp.example",
                                client_id="c1", client_secret="s3cret-value", role_mapping={"secops": "security_analyst"},
                                default_role=None, allowed_domains=[domain.upper()]), "admin")
    raw = client.query("SELECT client_secret FROM sso_providers_mt WHERE id = {id:String}",
                       parameters={"id": saved.id}).result_rows[0][0]
    assert raw and "s3cret-value" not in raw
    got = store.get(saved.id)
    assert got.client_secret == "s3cret-value" and got.name == "Okta\tprod" and got.allowed_domains == [domain]
    assert got.role_mapping == {"secops": "security_analyst"} and got.default_role is None
    assert [p.id for p in store.for_domain(domain)] == [saved.id]
    assert store.get(saved.id, "another-tenant") is None
    store.save(got, "admin", deleted=True)
    assert store.get(saved.id) is None and store.list(tenant) == []
