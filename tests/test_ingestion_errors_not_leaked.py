"""
Ingestion 500s must not leak exception text (LF-020 rule, applied to ingestion).

routers/ingestion.py answered internal failures with
`HTTPException(500, detail=f"... failed: {str(e)}")`, sending raw exception
text -- database names, hosts, driver internals -- to any caller. They now use
error_handling.internal_error: generic body + correlation ID, full detail in
the server log. Malformed bulk entries are a 400 (caller error), not a 500.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

SECRET = "Code: 516. DB::Exception: logforge@clickhouse:9000 Authentication failed"


@pytest.mark.asyncio
async def test_bulk_internal_failure_is_generic(monkeypatch):
    from routers import ingestion

    monkeypatch.setattr(ingestion, "check_ingest_capacity", lambda: None)
    tasks = MagicMock()
    tasks.add_task.side_effect = RuntimeError(SECRET)

    with pytest.raises(HTTPException) as exc:
        await ingestion.ingest_logs_bulk(
            {"logs": [{"service": "s", "msg": "m"}]}, tasks, customer_id="t1")

    assert exc.value.status_code == 500
    assert SECRET not in str(exc.value.detail)
    assert exc.value.detail["error"] == "Internal server error"
    assert exc.value.detail["correlation_id"]


@pytest.mark.asyncio
async def test_bulk_malformed_entry_is_400(monkeypatch):
    from routers import ingestion

    monkeypatch.setattr(ingestion, "check_ingest_capacity", lambda: None)
    with pytest.raises(HTTPException) as exc:
        await ingestion.ingest_logs_bulk({"logs": [{"msg": "missing service"}]}, MagicMock(), customer_id="t1")
    assert exc.value.status_code == 400


def test_no_ingestion_handler_echoes_exception_text_in_a_500():
    import inspect

    from routers import ingestion

    src = inspect.getsource(ingestion)
    assert "status_code=500, detail=f" not in src
