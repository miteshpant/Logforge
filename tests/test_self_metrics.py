"""
Tests for ENH-019 -- self-observability.

An observability platform that cannot observe itself is both an operational gap
and a credibility problem. There was no `/metrics` endpoint anywhere, and the
counters that existed (`EventMetrics`, `BufferStats`) were kept in memory and
never exported -- leaving on-call engineers with only logs: no ingest lag, queue
depth, error rate or latency percentiles.

The highest-stakes property here is **bounded label cardinality**. Emitting a
raw path such as `/v1/tenants/abc-123` would create one time series per tenant
id, which is exactly the cardinality explosion this product exists to help
customers avoid.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from self_metrics import (
    MetricsMiddleware,
    MetricsRegistry,
    get_registry,
    reset_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_registry()
    yield
    reset_registry()


# ---------------------------------------------------------------------------
# Registry primitives
# ---------------------------------------------------------------------------


def test_counter_accumulates():
    registry = MetricsRegistry()
    registry.inc("things_total", 1)
    registry.inc("things_total", 2)

    assert registry.snapshot()["counters"]["things_total"][()] == 3


def test_counters_are_separated_by_labels():
    registry = MetricsRegistry()
    registry.inc("things_total", 1, {"kind": "a"})
    registry.inc("things_total", 5, {"kind": "b"})

    counters = registry.snapshot()["counters"]["things_total"]
    assert counters[(("kind", "a"),)] == 1
    assert counters[(("kind", "b"),)] == 5


def test_gauge_replaces_rather_than_accumulates():
    registry = MetricsRegistry()
    registry.set_gauge("depth", 10)
    registry.set_gauge("depth", 3)

    assert registry.snapshot()["gauges"]["depth"][()] == 3


def test_histogram_records_sum_and_count():
    registry = MetricsRegistry()
    registry.observe("latency", 0.1)
    registry.observe("latency", 0.3)

    slot = registry.snapshot()["histograms"]["latency"][()]
    assert slot[-1] == 2                      # count
    assert slot[-2] == pytest.approx(0.4)     # sum


def test_histogram_buckets_are_cumulative():
    registry = MetricsRegistry(buckets=(0.1, 1.0))
    registry.observe("latency", 0.05)

    rendered = registry.render()
    assert 'latency_bucket{le="0.1"} 1' in rendered
    assert 'latency_bucket{le="1.0"} 1' in rendered


# ---------------------------------------------------------------------------
# Exposition format
# ---------------------------------------------------------------------------


def test_render_includes_type_declarations():
    registry = MetricsRegistry()
    registry.inc("requests_total", 1)
    registry.set_gauge("in_flight", 2)

    rendered = registry.render()
    assert "# TYPE requests_total counter" in rendered
    assert "# TYPE in_flight gauge" in rendered


def test_render_includes_help_when_described():
    registry = MetricsRegistry()
    registry.describe("requests_total", "Total requests.")
    registry.inc("requests_total", 1)

    assert "# HELP requests_total Total requests." in registry.render()


def test_label_values_are_escaped():
    """An unescaped quote or newline would corrupt the exposition output."""
    registry = MetricsRegistry()
    registry.inc("thing_total", 1, {"label": 'has"quote'})

    assert 'has\\"quote' in registry.render()


def test_histogram_emits_inf_bucket():
    registry = MetricsRegistry(buckets=(0.1,))
    registry.observe("latency", 99.0)

    assert 'latency_bucket{le="+Inf"} 1' in registry.render()


# ---------------------------------------------------------------------------
# Cardinality safety -- the important one
# ---------------------------------------------------------------------------


def test_path_label_uses_route_template_not_raw_path():
    """
    A raw path emits one series per tenant/resource id. That is an unbounded
    cardinality explosion -- the exact failure this product helps customers
    avoid, so shipping it ourselves would be indefensible.
    """
    app = FastAPI()

    @app.get("/v1/tenants/{tenant_id}")
    async def get_tenant(tenant_id: str):
        return {"id": tenant_id}

    app.add_middleware(MetricsMiddleware)
    client = TestClient(app)

    for tenant in ["abc-123", "def-456", "ghi-789"]:
        client.get(f"/v1/tenants/{tenant}")

    rendered = get_registry().render()

    assert "/v1/tenants/{tenant_id}" in rendered
    for tenant in ["abc-123", "def-456", "ghi-789"]:
        assert tenant not in rendered, (
            f"Raw id {tenant} leaked into a metric label -- unbounded cardinality."
        )


def test_status_is_reduced_to_a_class():
    """`2xx`/`5xx` keeps cardinality at ~5 instead of one series per code."""
    app = FastAPI()

    @app.get("/thing")
    async def thing():
        return {}

    app.add_middleware(MetricsMiddleware)
    TestClient(app).get("/thing")

    assert 'status="2xx"' in get_registry().render()


# ---------------------------------------------------------------------------
# Request instrumentation
# ---------------------------------------------------------------------------


def test_requests_are_counted():
    app = FastAPI()

    @app.get("/thing")
    async def thing():
        return {}

    app.add_middleware(MetricsMiddleware)
    client = TestClient(app)
    client.get("/thing")
    client.get("/thing")

    rendered = get_registry().render()
    assert "logforge_http_requests_total" in rendered
    assert "logforge_http_request_duration_seconds_count" in rendered


def test_errors_are_recorded_with_their_status_class():
    app = FastAPI()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    app.add_middleware(MetricsMiddleware)
    client = TestClient(app, raise_server_exceptions=False)
    client.get("/boom")

    assert 'status="5xx"' in get_registry().render(), (
        "A failing request must still be recorded -- errors are the E in RED."
    )


def test_in_flight_returns_to_zero_after_requests_complete():
    app = FastAPI()

    @app.get("/thing")
    async def thing():
        return {}

    app.add_middleware(MetricsMiddleware)
    TestClient(app).get("/thing")

    gauge = get_registry().snapshot()["gauges"][
        "logforge_http_requests_in_flight"
    ]
    assert sum(gauge.values()) == 0, "in-flight gauge leaked"
    # it goes up and down: a gauge, so Prometheus doesn't read the decrements as resets
    assert "# TYPE logforge_http_requests_in_flight gauge" in get_registry().render()


# ---------------------------------------------------------------------------
# Endpoint wiring
# ---------------------------------------------------------------------------


def test_metrics_endpoint_is_public_and_unthrottled():
    """
    Prometheus cannot present credentials, and throttling a scrape would blind
    us exactly when load is high.
    """
    from pathlib import Path

    api = Path(__file__).resolve().parent.parent / "apps" / "api"

    auth = (api / "authn_authz_middleware.py").read_text(encoding="utf-8")
    limits = (api / "request_limits.py").read_text(encoding="utf-8")

    assert '"/metrics"' in auth, "/metrics must be in the public endpoint list"
    assert '"/metrics"' in limits, "/metrics must be exempt from rate limiting"


def test_metrics_middleware_registered_last_so_it_runs_first():
    """
    Starlette reverses registration order. Registering the metrics middleware
    last makes it run first, so it observes requests that auth or rate limiting
    reject -- which are precisely the ones on-call needs to see.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "apps" / "api" / "main.py"
    ).read_text(encoding="utf-8")

    assert source.index("setup_request_limits(app)") < source.index(
        "app.add_middleware(MetricsMiddleware)"
    )


def test_pipeline_gauge_collection_never_raises():
    """
    The metrics endpoint must not fail because a subsystem is unavailable --
    that would blind us at precisely the wrong moment.
    """
    from self_metrics import collect_pipeline_gauges

    collect_pipeline_gauges()  # must not raise with no infra running
