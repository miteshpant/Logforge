"""
Tests for ENH-033 -- routers must build validated query requests.

`/query/aggregate`, `/query/timeseries` and `/export` passed raw dicts to
`query_engine.execute_query()`, which expects an `AdvancedQueryRequest`. Every
call raised `AttributeError: 'dict' object has no attribute 'filters'`.

The failure was invisible because `execute_query` caught every exception and
returned an empty result set, so clients received a valid-looking "no data"
response instead of an error. Removing that handler (ENH-002) exposed it.

These tests pin: a validated request is built, the tenant filter is always
applied, and invalid input yields 400 rather than a 500 or a silent empty result.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from query_engine import AdvancedQueryRequest, QueryOperator
from routers.query import build_query_request

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(hours=1)
BASE = {"start_time": START.isoformat(), "end_time": END.isoformat()}


# ---------------------------------------------------------------------------
# A real request object is produced
# ---------------------------------------------------------------------------


def test_builds_an_advanced_query_request():
    request = build_query_request(dict(BASE), "tenant-a")
    assert isinstance(request, AdvancedQueryRequest)


def test_result_has_filters_attribute():
    """
    The exact regression: the engine calls `query.filters`, which a dict does
    not have.
    """
    request = build_query_request(dict(BASE), "tenant-a")
    assert hasattr(request, "filters")
    assert hasattr(request, "aggregations")


def test_engine_can_consume_the_built_request():
    """End-to-end: the built request must survive SQL generation."""
    from query_engine import AdvancedQueryEngine

    request = build_query_request(dict(BASE), "tenant-a")
    engine = AdvancedQueryEngine(clickhouse_client=None)

    params = {}
    sql = engine._build_sql_query(request, "logs_raw_mt", params)

    assert "SELECT" in sql
    assert "tenant-a" in params.values()


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_tenant_filter_is_always_appended():
    request = build_query_request(dict(BASE), "tenant-a")

    tenant_filters = [f for f in request.filters if f.field == "customer_id"]
    assert len(tenant_filters) == 1
    assert tenant_filters[0].value == "tenant-a"


def test_tenant_filter_survives_caller_supplied_filters():
    payload = dict(BASE)
    payload["filters"] = [
        {"field": "service", "operator": "eq", "value": "api"}
    ]

    request = build_query_request(payload, "tenant-a")

    assert any(
        f.field == "customer_id" and f.value == "tenant-a" for f in request.filters
    )


def test_caller_cannot_override_the_tenant_filter():
    """
    A caller supplying their own customer_id filter must not be able to escape
    their tenant: ours is appended last and ANDed, so both must hold.
    """
    payload = dict(BASE)
    payload["filters"] = [
        {"field": "customer_id", "operator": "eq", "value": "victim-tenant"}
    ]

    request = build_query_request(payload, "tenant-a")

    tenant_values = [f.value for f in request.filters if f.field == "customer_id"]
    assert "tenant-a" in tenant_values
    assert request.filters[-1].value == "tenant-a", (
        "The enforced tenant filter must be appended last."
    )


def test_empty_payload_still_gets_tenant_filter():
    request = build_query_request(
        {"start_time": START, "end_time": END}, "tenant-a"
    )
    assert request.filters[-1].field == "customer_id"


# ---------------------------------------------------------------------------
# Invalid input -> 400, never 500 and never a silent empty result
# ---------------------------------------------------------------------------


def test_malformed_filter_raises_400():
    payload = dict(BASE)
    payload["filters"] = [{"field": "service"}]  # missing operator/value

    with pytest.raises(HTTPException) as err:
        build_query_request(payload, "tenant-a")

    assert err.value.status_code == 400


def test_unknown_operator_raises_400():
    payload = dict(BASE)
    payload["filters"] = [
        {"field": "service", "operator": "not_a_real_operator", "value": "x"}
    ]

    with pytest.raises(HTTPException) as err:
        build_query_request(payload, "tenant-a")

    assert err.value.status_code == 400


def test_missing_time_range_raises_400():
    with pytest.raises(HTTPException) as err:
        build_query_request({}, "tenant-a")

    assert err.value.status_code == 400


def test_inverted_time_range_raises_400():
    payload = {"start_time": END.isoformat(), "end_time": START.isoformat()}

    with pytest.raises(HTTPException) as err:
        build_query_request(payload, "tenant-a")

    assert err.value.status_code == 400


def test_malformed_aggregation_raises_400():
    payload = dict(BASE)
    payload["aggregations"] = [{"type": "not_an_aggregation", "field": "*"}]

    with pytest.raises(HTTPException) as err:
        build_query_request(payload, "tenant-a")

    assert err.value.status_code == 400


def test_over_limit_raises_400():
    """`limit` is bounded 1..10000 by the model; violations are client errors."""
    payload = dict(BASE)
    payload["limit"] = 999_999

    with pytest.raises(HTTPException) as err:
        build_query_request(payload, "tenant-a")

    assert err.value.status_code == 400


# ---------------------------------------------------------------------------
# Valid shapes still build
# ---------------------------------------------------------------------------


def test_aggregation_payload_builds():
    payload = dict(BASE)
    payload["aggregations"] = [{"type": "count", "field": "*"}]
    payload["group_by"] = ["service"]

    request = build_query_request(payload, "tenant-a")

    assert len(request.aggregations) == 1
    assert request.group_by == ["service"]


def test_text_search_is_carried_through():
    """
    Export previously put the search term under a `search` key the engine never
    read, so exports silently ignored it.
    """
    payload = dict(BASE)
    payload["text_search"] = "timeout"

    request = build_query_request(payload, "tenant-a")

    assert request.text_search == "timeout"


def test_in_operator_list_value_builds():
    payload = dict(BASE)
    payload["filters"] = [
        {"field": "level", "operator": "in", "value": ["error", "warn"]}
    ]

    request = build_query_request(payload, "tenant-a")

    level_filter = next(f for f in request.filters if f.field == "level")
    assert level_filter.operator == QueryOperator.IN
    assert level_filter.value == ["error", "warn"]


def test_export_maps_search_string_to_text_search():
    """The `/export` string-query path must populate `text_search`."""
    import inspect

    from routers import query as query_router

    source = inspect.getsource(query_router.export_query_results)
    assert '"text_search": raw_query' in source, (
        "Export must map the free-text term to `text_search`, the field the "
        "engine actually reads."
    )
