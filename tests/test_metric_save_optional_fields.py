"""
Regression test: a metric that follows the public MetricRequest schema must be
stored.

`MetricRequest` declares only metric_name / metric_type / timestamp / value,
but `ObservabilityDAO.save_metric` indexed metric_data["labels"],
["service_name"] and ["resource"] directly. Every metric sent through
POST /v1/observability/metrics/ingest without those undocumented keys raised
KeyError inside the DAO, was counted as failed, and the endpoint still
answered 202 -- so no metric was ever stored. Found during a live QA run.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_save_metric_accepts_schema_minimal_metric():
    with patch("dao.observability_dao.DatabaseLayer"):
        from dao.observability_dao import ObservabilityDAO

        dao = ObservabilityDAO()
    dao.db.execute_query = AsyncMock()

    metric = {
        "metric_name": "cpu.utilization",
        "metric_type": "gauge",
        "value": 42.5,
        "timestamp": "2026-11-16T01:00:00Z",
        "customer_id": "tenant-1",
    }
    metric_id = await dao.save_metric(dict(metric))

    assert metric_id
    dao.db.execute_query.assert_awaited_once()
    params = dao.db.execute_query.await_args.args[1]
    assert json.loads(params["labels"]) == {}
    assert json.loads(params["resource"]) == {}
    assert params["service_name"] == ""
    assert params["value"] == 42.5


@pytest.mark.asyncio
async def test_save_metric_keeps_supplied_optional_fields():
    with patch("dao.observability_dao.DatabaseLayer"):
        from dao.observability_dao import ObservabilityDAO

        dao = ObservabilityDAO()
    dao.db.execute_query = AsyncMock()

    await dao.save_metric({
        "metric_name": "http.requests", "metric_type": "counter", "value": 3,
        "timestamp": "2026-11-16T01:00:00Z", "customer_id": "t",
        "labels": {"route": "/x"}, "resource": {"host": "a"}, "service_name": "api",
    })
    params = dao.db.execute_query.await_args.args[1]
    assert json.loads(params["labels"]) == {"route": "/x"}
    assert json.loads(params["resource"]) == {"host": "a"}
    assert params["service_name"] == "api"
