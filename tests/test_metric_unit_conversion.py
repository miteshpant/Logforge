"""OpenTelemetry aliases often differ in unit from the canonical metric:
system.cpu.utilization is a 0-1 ratio while cpu_usage is a percentage, and
http.server.request.duration is in seconds while response_time is in ms.
Normalization converts the value, from the unit the metric was sent with,
or from a per-alias factor when it came without one."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from services.metric_normalizer import MetricNameNormalizer  # noqa: E402


@pytest.fixture(scope="module")
def norm():
    return MetricNameNormalizer()


def test_a_ratio_becomes_a_percentage(norm):
    out = norm.normalize_metric_data({"metric_name": "system.cpu.utilization", "value": 0.42, "unit": "1"})
    assert out["metric_name"] == "cpu_usage" and out["value"] == pytest.approx(42.0) and out["unit"] == "%"
    assert out["original_value"] == 0.42 and out["original_unit"] == "1"


def test_without_a_unit_the_alias_factor_applies(norm):
    out = norm.normalize_metric_data({"metric_name": "system.memory.utilization", "value": 0.5})
    assert out["metric_name"] == "memory_usage" and out["value"] == pytest.approx(50.0)


def test_seconds_become_milliseconds(norm):
    out = norm.normalize_metric_data({"metric_name": "http.server.request.duration", "value": 0.25, "unit": "s"})
    assert out["metric_name"] == "response_time" and out["value"] == pytest.approx(250.0) and out["unit"] == "ms"
    out = norm.normalize_metric_data({"metric_name": "latency", "value": 1500, "unit": "us"})
    assert out["value"] == pytest.approx(1.5)


def test_values_already_in_the_canonical_unit_are_kept(norm):
    out = norm.normalize_metric_data({"metric_name": "cpu_percent", "value": 42.0, "unit": "%"})
    assert out["value"] == 42.0 and "original_value" not in out
    out = norm.normalize_metric_data({"metric_name": "cpu_usage", "value": 42.0})
    assert out["value"] == 42.0


def test_unknown_units_are_left_alone(norm):
    out = norm.normalize_metric_data({"metric_name": "cpu_usage", "value": 3, "unit": "furlongs"})
    assert out["value"] == 3 and "original_value" not in out
