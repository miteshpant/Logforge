"""
Sigma detection -> ClickHouse prefilter (Phase 1 backtesting).

`compile_prefilter(detection)` turns a detection block into a WHERE clause
over logs_raw_mt that selects a SUPERSET of the events the engine would
match. The backtest then replays the selected events through the engine, so
the SQL never decides a match on its own; it only keeps the scan small.

Everything the SQL can't express exactly is widened, never narrowed:
negations (`not filter`) and regexes become "no restriction", and a rule that
can't be narrowed at all compiles to None (scan the time range).

Strings compare case-insensitively (lowerUTF8, like the engine's str.lower).
Field lookup mirrors the engine: a model column when it is non-empty,
otherwise the caller's value from the `attrs` JSON (`hostname` is the `host`
column, `message` is `msg`, `status_code` is `status`).
"""

import pytest

from sigma_sql import compile_prefilter, field_expression


def test_attr_field_equality_is_case_insensitive_and_parameterised():
    sql, params = compile_prefilter({"selection": {"event_type": "authentication"}, "condition": "selection"})
    assert sql == f"(lowerUTF8({field_expression('event_type')}) = lowerUTF8(%(p0)s))"
    assert params == {"p0": "authentication"}


def test_column_fields_fall_back_to_attrs_like_the_engine():
    expr = field_expression("hostname")
    assert expr.startswith("if(host != '', toString(host), ")
    assert "JSONExtractRaw(attrs, 'hostname')" in expr
    assert field_expression("src_ip").startswith("if(src_ip != '', toString(src_ip), ")


def test_lists_are_or_and_all_lists_are_and():
    sql, params = compile_prefilter({"selection": {"command_line|contains": ["a", "b"]}, "condition": "selection"})
    assert " OR " in sql and "positionCaseInsensitiveUTF8" in sql
    assert params == {"p0": "a", "p1": "b"}
    sql, _ = compile_prefilter({"selection": {"command_line|contains|all": ["a", "b"]}, "condition": "selection"})
    assert " AND " in sql and " OR " not in sql


def test_several_fields_in_a_selection_are_and():
    sql, _ = compile_prefilter({"selection": {"event_type": "authentication", "result": "failed"},
                                "condition": "selection"})
    assert sql.count(" AND ") == 1


def test_startswith_endswith_and_numeric_comparisons():
    sql, params = compile_prefilter({"selection": {"process_name|endswith": "\\net.exe",
                                                   "url|startswith": "/admin",
                                                   "bytes_out|gt": 1000},
                                     "condition": "selection"})
    assert "endsWith(lowerUTF8(" in sql and "startsWith(lowerUTF8(" in sql
    assert "toFloat64OrNull(" in sql and "> %(p2)s" in sql
    assert params["p2"] == 1000.0


def test_numeric_comparison_values_like_the_engine():
    sql, params = compile_prefilter({"selection": {"bytes_out": ">1000000"}, "condition": "selection"})
    assert "toFloat64OrNull(" in sql and ">" in sql and params == {"p0": 1000000.0}


def test_negations_and_regexes_only_widen():
    narrow, _ = compile_prefilter({"selection": {"event_type": "sudo"}, "condition": "selection"})
    widened, _ = compile_prefilter({"selection": {"event_type": "sudo"}, "filter": {"user": "root"},
                                    "condition": "selection and not filter"})
    assert widened == narrow
    assert compile_prefilter({"selection": {"command_line|re": "a.*b"}, "condition": "selection"}) == (None, {})


def test_quantifiers_and_boolean_structure():
    sql, _ = compile_prefilter({"selection_a": {"x": "1"}, "selection_b": {"y": "2"}, "condition": "1 of selection_*"})
    assert " OR " in sql
    sql, _ = compile_prefilter({"selection_a": {"x": "1"}, "selection_b": {"y": "2"}, "condition": "all of selection_*"})
    assert " AND " in sql
    or_any, _ = compile_prefilter({"a": {"x": "1"}, "b": {"command_line|re": "z"}, "condition": "a or b"})
    assert or_any is None  # one side unrestricted -> the OR is unrestricted


def test_count_rules_compile_their_selection():
    sql, params = compile_prefilter({"selection": {"event_type": "authentication"}, "timeframe": "5m",
                                     "condition": "count(selection) >= 10 by src_ip"})
    assert sql and params == {"p0": "authentication"}


def test_parameter_names_can_be_offset_to_combine_rules():
    sql, params = compile_prefilter({"selection": {"x": "1"}, "condition": "selection"}, start=5)
    assert params == {"p5": "1"} and "%(p5)s" in sql


def test_field_names_are_validated():
    with pytest.raises(ValueError):
        field_expression("x'); DROP TABLE logs_raw_mt; --")


def test_event_types_the_normalizer_can_guess_are_unrestricted():
    """The normalizer sets event_type=login_failed from a 'login failed'
    message when the caller sent none; the stored row doesn't have it."""
    assert compile_prefilter({"selection": {"event_type": "login_failed"}, "condition": "selection"}) == (None, {})
    sql, _ = compile_prefilter({"selection": {"event_type": "authentication"}, "condition": "selection"})
    assert sql
