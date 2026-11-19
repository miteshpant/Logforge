"""
Empty model columns must not hide the caller's value in `attrs`.

Ingestion normalizes every event to the log model, so `user`, `hostname`,
`user_id`... are present as "" even when the caller sent them under `attrs`.
Field lookup returned the empty column, so (found live) a password spray of
five users counted as one distinct user, and grouping by hostname would have
merged every host into one group. A rule selecting `user: root` missed
attrs.user == "root" the same way.
"""

from correlation import field_value
from sigma_engine import SigmaConditionEvaluator

EVENT = {"user": "", "hostname": None, "src_ip": "203.0.113.9",
         "attrs": {"user": "bob", "hostname": "WS-042", "src_ip": "10.9.9.9"}}


def test_correlation_fields_fall_back_to_attrs_when_the_column_is_empty():
    assert field_value(EVENT, "user") == "bob"
    assert field_value(EVENT, "hostname") == "WS-042"
    assert field_value(EVENT, "src_ip") == "203.0.113.9"  # a filled column still wins


def test_rule_fields_fall_back_to_attrs_when_the_column_is_empty():
    evaluator = SigmaConditionEvaluator()
    assert evaluator._get_field_value(EVENT, "user") == "bob"
    assert evaluator.evaluate_selection(EVENT, {"user": "bob", "hostname": "WS-042"})[0]
    assert evaluator._get_field_value(EVENT, "src_ip") == "203.0.113.9"


def test_an_empty_value_is_still_returned_when_attrs_has_nothing():
    evaluator = SigmaConditionEvaluator()
    assert evaluator._get_field_value({"user": ""}, "user") == ""
    assert field_value({"user": ""}, "user") == ""
