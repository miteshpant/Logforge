"""
Common schema (Phase 5): OCSF for security events, with the OpenTelemetry
semantic-convention name of each field alongside.

config/schema/ocsf_mapping.yml publishes the mapping of today's Logforge
fields to OCSF. It is used three ways, so the published mapping and the
behaviour can't drift apart:

* rules and queries can name any mapped field as `ocsf.<path>`;
* it resolves at read time ("schema-on-read"): an explicit
  attrs.ocsf.<path> (set by a source-mapping pipeline) wins; otherwise the
  first non-empty source field from the mapping, converted where the mapping
  says so (severity_id, status_id, epoch-ms time);
* docs/schema.md's table is checked against it.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

import ocsf_schema
from ocsf_schema import MAPPING, resolve

ROOT = Path(__file__).resolve().parents[1]


def test_every_mapping_entry_is_complete():
    paths = [m["ocsf"] for m in MAPPING]
    assert len(paths) == len(set(paths)) and len(paths) >= 25
    for entry in MAPPING:
        assert entry["ocsf"] and entry["type"] and entry["description"], entry
        assert entry.get("from") or entry.get("set_by") == "source mapping", entry
        assert "otel" in entry  # may be null where OTel has no equivalent


def test_resolution_order_and_conversions():
    event = {"ts": datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc), "host": "web-01", "service": "sshd",
             "level": "error", "msg": "Failed password", "src_ip": "", "user_id": "",
             "attrs": {"source_ip": "203.0.113.9", "user": "root", "result": "FAILED", "dst_port": 22}}
    assert resolve(event, "src_endpoint.ip") == "203.0.113.9"  # empty column falls through to attrs
    assert resolve(event, "actor.user.name") == "root"
    assert resolve(event, "device.hostname") == "web-01"
    assert resolve(event, "severity_id") == 4 and resolve(event, "severity") == "error"
    assert resolve(event, "status_id") == 2 and resolve(event, "status") == "Failure"
    assert resolve(event, "time") == 1795078800000
    assert resolve(event, "dst_endpoint.port") == 22
    assert resolve(event, "class_uid") is None  # only a source mapping can say what class an event is

    explicit = {**event, "attrs": {**event["attrs"], "ocsf": {"actor": {"user": {"name": "administrator"}},
                                                              "class_uid": 3002}}}
    assert resolve(explicit, "actor.user.name") == "administrator" and resolve(explicit, "class_uid") == 3002


def test_unknown_paths_resolve_to_none_and_are_listed_as_unmapped():
    assert resolve({"attrs": {}}, "no.such.field") is None
    assert not ocsf_schema.is_mapped("no.such.field") and ocsf_schema.is_mapped("src_endpoint.ip")


def test_the_rule_engine_reads_schema_fields():
    from sigma_engine import SigmaConditionEvaluator

    engine = SigmaConditionEvaluator.__new__(SigmaConditionEvaluator)
    event = {"service": "sshd", "src_ip": "198.51.100.7", "attrs": {"user": "root"}}
    assert engine._get_field_value(event, "ocsf.src_endpoint.ip") == "198.51.100.7"
    assert engine._get_field_value(event, "ocsf.actor.user.name") == "root"
    event["attrs"]["ocsf"] = {"actor": {"user": {"name": "explicit"}}}
    assert engine._get_field_value(event, "ocsf.actor.user.name") == "explicit"


@pytest.mark.parametrize("path", ["src_endpoint.ip", "actor.user.name", "status_id", "http_response.code"])
def test_the_docs_table_lists_every_mapped_field(path):
    doc = (ROOT / "docs" / "schema.md").read_text()
    for entry in MAPPING:
        assert f"`{entry['ocsf']}`" in doc, f"docs/schema.md is missing {entry['ocsf']}"
    assert f"`{path}`" in doc


def test_a_zero_status_column_is_not_an_http_code():
    assert resolve({"status": 0, "attrs": {}}, "http_response.code") is None
    assert resolve({"status": 503, "attrs": {}}, "http_response.code") == 503
    from query_engine import QueryFilter, QueryOperator

    params = {}
    sql = QueryFilter(field="ocsf.http_response.code", operator=QueryOperator.EQ, value=503).to_clickhouse_condition(params, "p")
    assert "nullIf(toInt64OrNull(" in sql
