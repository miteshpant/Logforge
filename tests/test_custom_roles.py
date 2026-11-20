"""
Custom roles and data scopes (Phase 14): roles a tenant defines, with extra
permissions and/or a data scope (the services whose logs they may read),
enforced by the middleware and by ClickHouse for every query the request
makes.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import custom_roles  # noqa: E402
import data_scope  # noqa: E402


# -- the ClickHouse filter -------------------------------------------------------------

def test_no_scope_no_filter():
    assert data_scope.settings_for(None) == {}


def test_services_and_prefixes():
    s = data_scope.settings_for(data_scope.DataScope(services=("auth", "payments-*")))
    assert s == {"additional_table_filters":
                 "{'logs_raw_mt': 'service IN (\\'auth\\') OR service LIKE \\'payments-%\\''}"}


def test_an_empty_scope_sees_nothing():
    assert data_scope.filter_sql(()) == "0"


def test_names_cannot_break_out_of_the_filter():
    sql = data_scope.filter_sql(("x') OR 1=1 --", "a\\b", "100%_*"))
    assert sql == "service IN ('x\\') OR 1=1 --', 'a\\\\b') OR service LIKE '100\\\\%\\\\_%'"


def test_the_scope_applies_only_inside_its_context():
    seen = []

    class Client:
        def _validate_settings(self, settings):
            seen.append(dict(settings or {}))
            return dict(settings or {})

    data_scope.install(Client)
    client = Client()
    client._validate_settings({"max_threads": 2})
    with data_scope.scoped(data_scope.DataScope(services=("auth",))):
        client._validate_settings({"max_threads": 2})
    client._validate_settings(None)
    assert "additional_table_filters" not in seen[0]
    assert seen[1]["max_threads"] == 2 and "auth" in seen[1]["additional_table_filters"]
    assert seen[2] == {}
    data_scope.install(Client)  # idempotent
    with data_scope.scoped(data_scope.DataScope(services=("auth",))):
        assert client._validate_settings({}).get("additional_table_filters").count("auth") == 1


# -- roles ----------------------------------------------------------------------------

def test_permissions_must_be_tenant_permissions():
    custom_roles.validate_permissions(["logs:read:tenant", "dashboards:read,write:tenant", "security:*:tenant"])
    for bad in (["*:*:*"], ["billing:*:platform"], ["logs:read"], ["nothing:read:tenant"], ["logs:read:own:extra"]):
        with pytest.raises(ValueError):
            custom_roles.validate_permissions(bad)
    assert custom_roles.normalise(["logs:read", "dashboards:read:tenant"]) == ["logs:read:tenant", "dashboards:read:tenant"]


@pytest.mark.parametrize("perms, required, ok", [
    (["logs:read,search:tenant"], "logs:search:tenant", True),
    (["logs:read:tenant"], "logs:write:tenant", False),
    (["security:*:tenant"], "security:write:tenant", True),
    (["dashboards:read:tenant"], "settings:read:tenant", False),
])
def test_grants(perms, required, ok):
    assert custom_roles.grants(perms, required) is ok


def test_effective_access_unions_roles_and_scopes():
    roles = [custom_roles.CustomRole(id="r1", tenant_id="acme", name="Payments read", permissions=["dashboards:read:tenant"],
                                     services=["payments-*"]),
             custom_roles.CustomRole(id="r2", tenant_id="acme", name="Auth logs", permissions=[], services=["auth"]),
             custom_roles.CustomRole(id="r3", tenant_id="acme", name="Reports", permissions=["reports:read:tenant"],
                                     services=None)]
    perms, scope = custom_roles.effective(roles)
    assert perms == ["dashboards:read:tenant", "reports:read:tenant"]
    assert scope == data_scope.DataScope(services=("auth", "payments-*"))
    assert custom_roles.effective([roles[2]]) == (["reports:read:tenant"], None)
    assert custom_roles.effective([]) == ([], None)


def test_the_middleware_decision():
    built_in = [{"tenant_id": "acme", "role": "viewer"}]
    analyst = custom_roles.CustomRole(id="r1", tenant_id="acme", name="x", permissions=["security:read:tenant"])
    assert not custom_roles.allowed(built_in, [], "security:read:tenant", "acme")
    assert custom_roles.allowed(built_in, [analyst], "security:read:tenant", "acme")
    assert custom_roles.allowed(built_in, [], "logs:read:tenant", "acme")  # the built-in role still counts


def test_caches_never_share_results_across_scopes():
    from services.query_service import QueryService
    from utils.api_cache import cache_key

    service = QueryService.__new__(QueryService)
    query = {"query": "| stats count() by service"}
    unscoped = service._generate_cache_key(query, "acme")
    plain = cache_key("acme", "x")
    with data_scope.scoped(data_scope.DataScope(services=("auth",))):
        scoped = service._generate_cache_key(query, "acme")
        scoped_plain = cache_key("acme", "x")
    with data_scope.scoped(data_scope.DataScope(services=("billing",))):
        other = service._generate_cache_key(query, "acme")
    assert len({unscoped, scoped, other}) == 3 and plain != scoped_plain


def test_archive_search_is_refused_under_a_scope():
    import asyncio

    from fastapi import HTTPException

    from routers.query import run_archive_query

    with data_scope.scoped(data_scope.DataScope(services=("auth",))):
        with pytest.raises(HTTPException) as e:
            asyncio.run(run_archive_query("| stats count()", {}, "acme"))
    assert e.value.status_code == 403
