"""
Comparing a JSON field (attrs.x, raw_data.x) with a number.

Found by the Phase 4 onboarding spec: a pipeline that converts a field to an
integer (grok %{INT:order_id:int}) makes `| where attrs.order_id = 94598`
natural, but the JSON value is extracted as a String and ClickHouse refuses
to compare String with an integer parameter, so the query failed with 500.
Numeric comparisons on JSON fields now convert the extracted text
(toFloat64OrNull); string comparisons are unchanged.
"""

import pytest

from query_engine import QueryFilter, QueryOperator


def render(field, op, value):
    params = {}
    return QueryFilter(field=field, operator=op, value=value).to_clickhouse_condition(params, "p"), params


@pytest.mark.parametrize("op, symbol", [(QueryOperator.EQ, "="), (QueryOperator.GT, ">"), (QueryOperator.LTE, "<=")])
def test_numbers_compare_numerically_on_json_fields(op, symbol):
    sql, params = render("attrs.order_id", op, 94598)
    assert sql.startswith("toFloat64OrNull(if(JSONExtractString(attrs, %(p_jsonkey)s) != ''")
    assert sql.endswith(f") {symbol} %(p)s") and params["p"] == 94598
    sql, _ = render("raw_data.bytes", op, 1.5)
    assert sql == f"toFloat64OrNull(JSONExtractString(raw_data, %(p_jsonkey)s)) {symbol} %(p)s"


def test_strings_and_columns_are_unchanged():
    sql, _ = render("attrs.action", QueryOperator.EQ, "REFUNDED")
    assert sql.startswith("if(JSONExtractString(attrs") and "toFloat64OrNull" not in sql
    sql, _ = render("status", QueryOperator.GTE, 500)
    assert sql == "status >= %(p)s"
    sql, _ = render("attrs.flag", QueryOperator.EQ, True)  # booleans are not numbers here
    assert "toFloat64OrNull" not in sql
