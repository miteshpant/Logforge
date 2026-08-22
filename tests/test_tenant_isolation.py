"""
Tests for ENH-023 -- multi-tenant isolation.

Isolation is the platform's core guarantee, and until now nothing tested it. It
rests on two mechanisms, both of which had defects fixed earlier in this pass:

1. A `customer_id` predicate appended to every query (`routers/query.py`) --
   which ENH-002 showed could be neutralised by SQL injection in a filter value.
2. A header/tenant check in the auth middleware.

These tests assert the invariants at the layer where isolation is actually
enforced -- query construction -- without needing a live database. An
end-to-end suite against two seeded tenants is the natural follow-up once CI
provisions ClickHouse.
"""

from datetime import datetime, timedelta, timezone

import pytest

from query_engine import (
    AdvancedQueryEngine,
    AdvancedQueryRequest,
    QueryFilter,
    QueryOperator,
)
from routers.query import build_query_request

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(hours=1)

VICTIM = "tenant-victim"
ATTACKER = "tenant-attacker"


def _sql_and_params(request):
    engine = AdvancedQueryEngine(clickhouse_client=None)
    table = engine._select_optimal_table(request)
    params = {}
    sql = engine._build_sql_query(request, table, params)
    return sql, params


# ---------------------------------------------------------------------------
# The predicate is always present
# ---------------------------------------------------------------------------


def test_every_query_carries_a_tenant_predicate():
    request = build_query_request(
        {"start_time": START, "end_time": END}, ATTACKER
    )
    sql, params = _sql_and_params(request)

    assert "customer_id" in sql
    assert ATTACKER in params.values()


def test_tenant_predicate_is_bound_not_interpolated():
    """
    If the tenant id were interpolated, a crafted id could terminate the
    predicate -- the ENH-002 failure mode.
    """
    request = build_query_request(
        {"start_time": START, "end_time": END}, ATTACKER
    )
    sql, _ = _sql_and_params(request)

    assert f"'{ATTACKER}'" not in sql, "Tenant id was interpolated into SQL"
    assert "customer_id = %(" in sql


def test_tenant_predicate_survives_an_empty_filter_list():
    request = build_query_request(
        {"start_time": START, "end_time": END, "filters": []}, ATTACKER
    )
    _, params = _sql_and_params(request)
    assert ATTACKER in params.values()


# ---------------------------------------------------------------------------
# A caller cannot escape their tenant
# ---------------------------------------------------------------------------


def test_caller_cannot_substitute_another_tenant_id():
    """
    Supplying a victim's customer_id must not replace the enforced predicate --
    both are ANDed, so the query matches nothing rather than the victim's rows.
    """
    request = build_query_request(
        {
            "start_time": START,
            "end_time": END,
            "filters": [
                {"field": "customer_id", "operator": "eq", "value": VICTIM}
            ],
        },
        ATTACKER,
    )
    sql, params = _sql_and_params(request)

    assert ATTACKER in params.values(), "Enforced tenant filter is missing"
    assert request.filters[-1].value == ATTACKER, (
        "The enforced filter must be appended last."
    )
    assert sql.count("customer_id") >= 2, (
        "Both predicates must be present and ANDed."
    )
    assert " OR " not in sql.upper()


@pytest.mark.parametrize(
    "payload",
    [
        "x' OR customer_id != '",
        "'; DROP TABLE logs_raw_mt; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM logs_raw_mt WHERE customer_id != '",
        "%' OR customer_id LIKE '%",
    ],
)
def test_injection_in_a_filter_cannot_disable_isolation(payload):
    """The core cross-tenant attack: break out of a value to widen the query."""
    request = build_query_request(
        {
            "start_time": START,
            "end_time": END,
            "filters": [
                {"field": "service", "operator": "eq", "value": payload}
            ],
        },
        ATTACKER,
    )
    sql, params = _sql_and_params(request)

    assert payload not in sql, f"Payload reached SQL text: {sql}"
    assert " OR " not in sql.upper()
    assert "UNION" not in sql.upper()
    assert "DROP" not in sql.upper()
    assert ATTACKER in params.values()


@pytest.mark.parametrize(
    "payload",
    ["x' OR customer_id != '", "%' OR 1=1 --"],
)
def test_injection_in_text_search_cannot_disable_isolation(payload):
    request = build_query_request(
        {"start_time": START, "end_time": END, "text_search": payload},
        ATTACKER,
    )
    sql, params = _sql_and_params(request)

    assert payload not in sql
    assert ATTACKER in params.values()


def test_injection_via_a_json_key_cannot_disable_isolation():
    request = build_query_request(
        {
            "start_time": START,
            "end_time": END,
            "filters": [
                {
                    "field": "attrs.x') OR customer_id != ('",
                    "operator": "eq",
                    "value": "v",
                }
            ],
        },
        ATTACKER,
    )
    sql, params = _sql_and_params(request)

    assert " OR " not in sql.upper()
    assert ATTACKER in params.values()


def test_injection_via_an_identifier_is_rejected_outright():
    from query_engine import QueryFieldError

    with pytest.raises((QueryFieldError, Exception)):
        request = build_query_request(
            {
                "start_time": START,
                "end_time": END,
                "sort_field": "ts; SELECT * FROM logs_raw_mt",
            },
            ATTACKER,
        )
        _sql_and_params(request)


# ---------------------------------------------------------------------------
# Two tenants never share a query
# ---------------------------------------------------------------------------


def test_two_tenants_produce_different_bound_parameters():
    a = build_query_request({"start_time": START, "end_time": END}, VICTIM)
    b = build_query_request({"start_time": START, "end_time": END}, ATTACKER)

    _, params_a = _sql_and_params(a)
    _, params_b = _sql_and_params(b)

    assert VICTIM in params_a.values()
    assert VICTIM not in params_b.values()
    assert ATTACKER in params_b.values()
    assert ATTACKER not in params_a.values()


def test_direct_engine_use_still_requires_an_explicit_tenant_filter():
    """
    Building an AdvancedQueryRequest directly (bypassing the router helper)
    carries NO implicit tenant scoping. This documents that the predicate is a
    router-layer responsibility -- worth knowing before adding a new caller.
    """
    request = AdvancedQueryRequest(start_time=START, end_time=END)
    sql, _ = _sql_and_params(request)

    assert "customer_id" not in sql, (
        "If this ever changes, the isolation model has moved and these tests "
        "must be revisited."
    )


def test_router_helper_is_the_isolation_choke_point():
    """
    Every endpoint taking a raw payload must route through
    `build_query_request`, which is where the tenant filter is applied.
    """
    import inspect

    from routers import query as query_router

    for name in ("aggregate_logs", "timeseries_query", "export_query_results"):
        source = inspect.getsource(getattr(query_router, name))
        assert "build_query_request" in source, (
            f"{name} bypasses the tenant-isolation choke point."
        )


# ---------------------------------------------------------------------------
# Auth-layer isolation
# ---------------------------------------------------------------------------


def test_middleware_requires_a_tenant_header():
    import inspect

    from authn_authz_middleware import UnifiedAuthMiddleware

    source = inspect.getsource(UnifiedAuthMiddleware.dispatch)
    assert "X-Customer-ID" in source
    assert "No access to tenant" in source, (
        "The middleware must reject a user with no role in the requested tenant."
    )


def test_permission_check_requires_a_matching_tenant():
    """A role granted in tenant A must not authorise access to tenant B."""
    from authn_authz_middleware import check_permission

    roles = [{"tenant_id": VICTIM, "role": "tenant_admin"}]

    assert check_permission(roles, "logs:read:tenant", VICTIM) is True
    assert check_permission(roles, "logs:read:tenant", ATTACKER) is False


def test_platform_role_does_not_leak_from_a_tenant_role():
    from authn_authz_middleware import check_permission

    roles = [{"tenant_id": VICTIM, "role": "tenant_admin"}]
    assert check_permission(roles, "platform:admin:platform", VICTIM) is False
