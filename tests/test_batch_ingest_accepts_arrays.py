"""
POST /v1/ingest/logs/batch accepts a bare JSON array as well as {"logs": [...]}.

Vector's, Fluent Bit's and Fluentd's HTTP outputs send a JSON array per batch
and cannot wrap it in an object, so the shipper recipes could not use the batch
endpoint (and /v1/ingest/logs only takes a single object).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException


def _entries(n):
    from models import LogEntry

    return [LogEntry(service="svc", msg=f"m{i}") for i in range(n)]


@pytest.fixture
def ingestion():
    from routers import ingestion as module

    with patch.object(module, "check_ingest_capacity"), \
         patch.object(module, "process_logs_and_tracking_background", MagicMock()):
        yield module


@pytest.mark.asyncio
async def test_bare_array_is_accepted(ingestion):
    tasks = MagicMock()
    out = await ingestion.ingest_logs_batch(background_tasks=tasks, batch=_entries(3), customer_id="t1")

    assert out.processed_count == 3
    queued_logs = tasks.add_task.call_args.args[1]
    assert [log.customer_id for log in queued_logs] == ["t1"] * 3


@pytest.mark.asyncio
async def test_wrapped_form_still_works(ingestion):
    from models import BatchLogEntry

    out = await ingestion.ingest_logs_batch(
        background_tasks=MagicMock(), batch=BatchLogEntry(logs=_entries(2)), customer_id="t1")
    assert out.processed_count == 2


@pytest.mark.asyncio
async def test_array_over_the_limit_is_rejected(ingestion):
    with pytest.raises(HTTPException) as exc:
        await ingestion.ingest_logs_batch(background_tasks=MagicMock(), batch=_entries(1001), customer_id="t1")
    assert exc.value.status_code == 413


def test_request_body_schema_offers_both_forms(ingestion):
    app = FastAPI()
    app.include_router(ingestion.router)
    body = app.openapi()["paths"]["/v1/ingest/logs/batch"]["post"]["requestBody"]
    schema = body["content"]["application/json"]["schema"]
    variants = schema.get("anyOf") or schema.get("oneOf")
    assert variants and any(v.get("type") == "array" for v in variants)
