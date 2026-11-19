"""
Shippers can name a pipeline with the X-Logforge-Pipeline header on
/v1/ingest/logs and /v1/ingest/logs/batch (Phase 4). Every accepted log is
stamped `logforge_pipeline`; an unknown or disabled pipeline is refused
with 400 before anything is accepted.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from pipeline_store import PipelineRecord, PipelineRegistry


class DAO:
    async def list(self, tenant_id):
        return [PipelineRecord.from_dict({"name": "edge", "processors": [{"drop": {}}]}),
                PipelineRecord.from_dict({"name": "off", "enabled": False, "processors": [{"drop": {}}]})]


@pytest.fixture
def ingestion(monkeypatch):
    from routers import ingestion as module
    import pipeline_store

    monkeypatch.setattr(pipeline_store, "_registry", PipelineRegistry(dao=DAO(), builtins={}))
    service = MagicMock()
    service.validate_log_entry.return_value = True
    service.prepare_logs_for_storage.side_effect = lambda logs, customer_id: logs
    with patch.object(module, "check_ingest_capacity"), \
            patch.object(module, "get_ingestion_service", lambda: service), \
            patch.object(module, "process_logs_and_tracking_background", MagicMock()):
        yield module


def entries(n):
    from models import LogEntry

    return [LogEntry(service="svc", msg=f"m{i}") for i in range(n)]


def test_batch_logs_are_stamped_with_the_named_pipeline(ingestion):
    tasks = MagicMock()
    asyncio.run(ingestion.ingest_logs_batch(background_tasks=tasks, batch=entries(2), customer_id="t1",
                                            pipeline="edge"))
    logs = tasks.add_task.call_args.args[1]
    assert [log.model_dump()["logforge_pipeline"] for log in logs] == ["edge", "edge"]


def test_single_log_is_stamped(ingestion):
    tasks = MagicMock()
    asyncio.run(ingestion.ingest_logs(log_entry=entries(1)[0], background_tasks=tasks, customer_id="t1",
                                      pipeline="edge"))
    assert tasks.add_task.call_args.args[1][0].model_dump()["logforge_pipeline"] == "edge"


@pytest.mark.parametrize("name", ["nope", "off"])
def test_unknown_or_disabled_pipelines_are_refused(ingestion, name):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ingestion.ingest_logs_batch(background_tasks=MagicMock(), batch=entries(1), customer_id="t1",
                                                pipeline=name))
    assert exc.value.status_code == 400 and name in exc.value.detail


def test_without_the_header_nothing_is_stamped(ingestion):
    tasks = MagicMock()
    asyncio.run(ingestion.ingest_logs_batch(background_tasks=tasks, batch=entries(1), customer_id="t1", pipeline=None))
    assert "logforge_pipeline" not in tasks.add_task.call_args.args[1][0].model_dump()
