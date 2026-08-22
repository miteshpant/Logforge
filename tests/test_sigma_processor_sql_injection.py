"""
Regression tests for ENH-004 -- second-order SQL injection in the detection path.

Threat model
------------
`SigmaProcessor._create_security_event()` builds a security event whose
`artifact_data` and `matched_fields` fields are derived from INGESTED LOG
CONTENT. Before this fix those values were interpolated into an INSERT with an
f-string, so any actor able to ship a single log line into any tenant could
execute arbitrary ClickHouse statements as the detection service -- with no
platform credentials at all.

These tests assert the structural property that makes that class of attack
impossible: log-derived content is transported as bound DATA and never appears
inside SQL statement text.

No database is required. We capture what the code hands to the driver.
"""

import json
from datetime import datetime, timezone

import pytest

from events.management.processors.sigma_processor import (
    SigmaProcessor,
    _as_string_list,
)


# Payloads that would break out of a single-quoted SQL literal, terminate the
# statement, and append attacker-chosen SQL.
INJECTION_PAYLOADS = [
    "'); DROP TABLE security_events_mt; --",
    "' OR '1'='1",
    "x'); INSERT INTO users_mt (id) VALUES ('pwned'); --",
    "'; SELECT * FROM users_mt WHERE customer_id != '",
    "\\'; DROP TABLE logs_raw_mt; --",
]


class _SpyDatabaseLayer:
    """
    Stand-in for DatabaseLayer that records how the insert was invoked.

    This is test scaffolding to observe a call boundary -- it is not mock
    application data. Nothing it returns is presented as a real record.
    """

    instances = []

    def __init__(self, service_name, service_key):
        self.service_name = service_name
        self.service_key = service_key
        self.insert_calls = []
        self.update_calls = []
        _SpyDatabaseLayer.instances.append(self)

    async def execute_insert(self, table, data):
        self.insert_calls.append((table, data))
        return len(data)

    async def execute_update(self, query, params=None):
        # Reaching this from the detection write path means SQL text was built,
        # which is the vulnerable pattern this ticket removed.
        self.update_calls.append((query, params))
        return 1


class _Severity:
    value = "high"


class _Match:
    """A Sigma rule match carrying attacker-controlled log content."""

    def __init__(self, payload):
        self.rule_id = "rule-001"
        self.rule_title = "Test Rule"
        self.severity = _Severity()
        self.attack_techniques = ["T1059"]
        self.kill_chain_phases = ["execution"]
        self.timestamp = datetime.now(timezone.utc)
        # The hostile values: these come from the ingested log.
        self.log_entry = {"msg": payload, "host": payload}
        self.matched_fields = {"msg": {"log_value": payload}}


@pytest.fixture
def spy_db(monkeypatch):
    _SpyDatabaseLayer.instances = []
    import database_layer

    monkeypatch.setattr(database_layer, "DatabaseLayer", _SpyDatabaseLayer)
    return _SpyDatabaseLayer


@pytest.fixture
def processor(monkeypatch):
    """
    A SigmaProcessor with its cache/engine construction bypassed.

    Only `_create_security_event` / `_insert_security_event` are exercised.
    """
    proc = SigmaProcessor.__new__(SigmaProcessor)

    async def _no_publish(event_data):
        return True

    monkeypatch.setattr(proc, "_publish_security_event", _no_publish, raising=False)
    return proc


# ---------------------------------------------------------------------------
# Core security property
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
async def test_log_content_is_never_interpolated_into_sql(
    payload, processor, spy_db
):
    """
    The detection write must go through a bound insert, and no SQL statement
    text containing the payload may be produced.
    """
    match = _Match(payload)

    ok = await processor._create_security_event(match, "tenant-a")
    assert ok is True

    db = spy_db.instances[-1]

    # The write went through the parameter-binding insert path...
    assert len(db.insert_calls) == 1, (
        "Expected exactly one bound insert for the detection write."
    )
    table, rows = db.insert_calls[0]
    assert table == "security_events_mt"

    # ...and NOT through a hand-built SQL statement.
    assert db.update_calls == [], (
        "Detection write built raw SQL text (execute_update). This is the "
        "ENH-004 vulnerability: log content must never reach SQL as a literal."
    )

    # The hostile payload is present as DATA, unmodified.
    record = rows[0]
    assert payload in record["raw_log_data"], (
        "Log content must be stored verbatim as data, not escaped or stripped."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
async def test_payload_round_trips_as_json_without_statement_breakout(
    payload, processor, spy_db
):
    """
    `artifact_data` must remain valid JSON containing the exact payload, proving
    it was treated as an opaque value rather than parsed as SQL.
    """
    match = _Match(payload)
    await processor._create_security_event(match, "tenant-a")

    record = spy_db.instances[-1].insert_calls[0][1][0]

    decoded = json.loads(record["raw_log_data"])
    assert decoded["msg"] == payload, (
        "Payload was altered in transit; it must round-trip byte-for-byte."
    )


@pytest.mark.asyncio
async def test_tenant_id_is_bound_not_interpolated(processor, spy_db):
    """A hostile tenant id must not be able to alter the statement either."""
    hostile_tenant = "t'); DROP TABLE users_mt; --"
    match = _Match("benign message")

    await processor._create_security_event(match, hostile_tenant)

    record = spy_db.instances[-1].insert_calls[0][1][0]
    assert record["customer_id"] == hostile_tenant
    assert spy_db.instances[-1].update_calls == []


# ---------------------------------------------------------------------------
# Failure handling -- must be explicit, never silent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_failure_is_surfaced_not_swallowed(processor, monkeypatch):
    """
    A detection that cannot be persisted is a LOST DETECTION. The insert helper
    must raise so the caller can count it as a failure, rather than reporting
    success.
    """
    import database_layer

    class _FailingDatabaseLayer:
        def __init__(self, *args, **kwargs):
            pass

        async def execute_insert(self, table, data):
            raise RuntimeError("clickhouse unavailable")

    monkeypatch.setattr(database_layer, "DatabaseLayer", _FailingDatabaseLayer)

    with pytest.raises(RuntimeError):
        await processor._insert_security_event(
            {"id": "e1", "customer_id": "t1", "raw_log_data": "{}"}
        )


@pytest.mark.asyncio
async def test_create_security_event_reports_false_on_insert_failure(
    processor, monkeypatch
):
    """The caller converts the raised error into an explicit failure result."""
    import database_layer

    class _FailingDatabaseLayer:
        def __init__(self, *args, **kwargs):
            pass

        async def execute_insert(self, table, data):
            raise RuntimeError("clickhouse unavailable")

    monkeypatch.setattr(database_layer, "DatabaseLayer", _FailingDatabaseLayer)

    result = await processor._create_security_event(_Match("msg"), "tenant-a")
    assert result is False, (
        "A failed persist must be reported as failure, never as success."
    )


# ---------------------------------------------------------------------------
# Array(String) coercion
# ---------------------------------------------------------------------------


def test_as_string_list_handles_none():
    assert _as_string_list(None) == []


def test_as_string_list_wraps_scalar():
    assert _as_string_list("T1059") == ["T1059"]


def test_as_string_list_maps_enum_like_members():
    class _E:
        value = "execution"

    assert _as_string_list([_E(), "persistence"]) == ["execution", "persistence"]


def test_array_columns_are_lists_not_json_strings(processor, spy_db):
    """
    `mitre_techniques` / `artifacts` are Array(String) columns. Passing a
    json.dumps() string produced a driver type error, so detections silently
    failed to persist.
    """

    async def _run():
        await processor._create_security_event(_Match("msg"), "tenant-a")

    import asyncio

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_run())

    record = spy_db.instances[-1].insert_calls[0][1][0]
    assert isinstance(record["mitre_techniques"], list)
    assert isinstance(record["artifacts"], list)
