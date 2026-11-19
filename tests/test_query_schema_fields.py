"""
Querying nested attrs and schema fields (Phase 5).

* attrs.a.b addresses nested JSON (pipelines and OCSF mappings write nested
  objects). A key that literally contains dots still matches first, so
  existing flat keys keep working. Every key is a bound parameter.
* ocsf.<path> is the common schema: the explicit attrs.ocsf.<path> first,
  then today's source fields from config/schema/ocsf_mapping.yml, as a
  coalesce. Unknown schema paths are refused.
"""

import pytest

import logql
from query_engine import QueryFieldError, QueryFilter, QueryOperator


def render(field, value="x", op=QueryOperator.EQ):
    params = {}
    sql = QueryFilter(field=field, operator=op, value=value).to_clickhouse_condition(params, "p")
    return sql, params


def test_nested_attrs_paths_bind_each_key():
    sql, params = render("attrs.ocsf.user.name")
    assert params["p_jsonkey"] == "ocsf.user.name"  # the flat key, tried first
    assert [params[f"p_k{i}"] for i in range(3)] == ["ocsf", "user", "name"]
    assert "JSONExtractString(attrs, %(p_k0)s, %(p_k1)s, %(p_k2)s)" in sql
    assert "ocsf" not in sql.replace("%(p_", "")  # no key text in the statement


def test_flat_attrs_keys_are_unchanged():
    sql, params = render("attrs.user")
    assert "p_k0" not in params and sql.startswith("if(JSONHas(attrs, %(p_jsonkey)s)")


def test_schema_fields_coalesce_explicit_and_mapped_sources():
    sql, params = render("ocsf.src_endpoint.ip", "203.0.113.9")
    assert sql.startswith("coalesce(")
    assert "src_ip" in sql and "nullIf(" in sql
    assert params["p"] == "203.0.113.9"
    keys = {v for k, v in params.items() if k.startswith("p_")}
    assert {"ocsf", "src_endpoint", "ip", "source_ip"} <= keys


def test_schema_conversions_in_sql():
    sql, _ = render("ocsf.status_id", 2)
    assert "multiIf" in sql and sql.endswith("= %(p)s")
    sql, _ = render("ocsf.severity_id", 4, QueryOperator.GTE)
    assert "multiIf" in sql


def test_unknown_schema_fields_are_refused():
    with pytest.raises(QueryFieldError, match="not in the common schema"):
        render("ocsf.no.such")


def test_logforgeql_accepts_schema_fields_in_where_stats_and_sort():
    payload = logql.compile_to_request_payload(
        "| where ocsf.status_id = 2 | stats count() by ocsf.actor.user.name | sort ocsf.actor.user.name")
    assert payload["filters"][0]["field"] == "ocsf.status_id"
    assert payload["group_by"] == ["ocsf.actor.user.name"]
