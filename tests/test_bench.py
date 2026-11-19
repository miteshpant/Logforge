"""
Performance benchmark harness (Phase 0): statistics and runner logic.

The runner talks to a live stack; these tests drive it with a fake client and
a fake clock so the measurement logic itself is checked deterministically.
"""

import pytest

import perf_bench as bench


def test_percentiles_use_linear_interpolation():
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert bench.percentile(values, 50) == pytest.approx(55.0)
    assert bench.percentile(values, 95) == pytest.approx(95.5)
    assert bench.percentile([7], 95) == 7


def test_summarize_reports_ms_stats():
    summary = bench.summarize([0.010, 0.020, 0.030, 0.040])
    assert summary == {"count": 4, "p50_ms": 25.0, "p95_ms": 38.5, "max_ms": 40.0, "mean_ms": 25.0}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeClient:
    """Each call advances the fake clock by a fixed, per-path cost."""

    def __init__(self, clock, costs, visible_after=0):
        self.clock, self.costs, self.calls = clock, costs, []
        self.visible_after = visible_after

    def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        self.clock.now += self.costs.get(path, 0.001)
        return {"processed_count": len(json) if isinstance(json, list) else 1}

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        self.clock.now += self.costs.get(path, 0.001)
        if path == "/v1/logs":
            polls = sum(1 for c in self.calls if c[1] == "/v1/logs")
            return {"logs": [{}] if polls > self.visible_after else []}
        return {}


def test_query_bench_times_each_query_repeatedly():
    clock = FakeClock()
    client = FakeClient(clock, {"/v1/logs": 0.05, "/v1/query/logql": 0.2})
    queries = [
        {"name": "recent logs", "method": "GET", "path": "/v1/logs", "params": {"limit": 100}},
        {"name": "stats by service", "method": "POST", "path": "/v1/query/logql", "body": {"query": "x"}},
    ]
    results = bench.run_query_bench(client, queries, repeats=5, clock=clock)

    assert results["recent logs"]["count"] == 5
    assert results["recent logs"]["p50_ms"] == pytest.approx(50.0)
    assert results["stats by service"]["p95_ms"] == pytest.approx(200.0)


def test_ingest_bench_reports_events_per_second():
    clock = FakeClock()
    client = FakeClient(clock, {"/v1/ingest/logs/batch": 0.5})
    result = bench.run_ingest_bench(client, batch_size=1000, batches=4, clock=clock)

    assert result == {"events": 4000, "seconds": 2.0, "events_per_second": 2000.0, "batch_size": 1000}
    first_batch = client.calls[0][2]
    assert len(first_batch) == 1000 and {"service", "msg", "level"} <= set(first_batch[0])


def test_ingest_to_searchable_polls_until_the_marker_appears():
    clock = FakeClock()
    client = FakeClient(clock, {"/v1/ingest/logs/batch": 0.01, "/v1/logs": 0.01}, visible_after=3)
    seconds = bench.measure_ingest_to_searchable(client, clock=clock, poll_interval=0.25,
                                                 sleep=lambda s: setattr(clock, "now", clock.now + s))
    # 1 ingest + 4 polls (3 empty) at 0.01s each, plus 3 waits of 0.25s
    assert seconds == pytest.approx(0.01 + 4 * 0.01 + 3 * 0.25)


def test_seed_sql_targets_one_tenant_and_is_bounded():
    sql = bench.seed_sql(tenant_id="bench-tenant", rows=1_000_000, days=7)
    assert "INSERT INTO logs_raw_mt" in sql
    assert "'bench-tenant'" in sql and "numbers(1000000)" in sql
    assert "INTERVAL 7 DAY" in sql or "604800" in sql


def test_cached_endpoints_get_a_distinct_window_each_repeat():
    """/v1/query/advanced caches results by request body; identical repeats
    would measure the cache, not the query."""
    clock = FakeClock()
    client = FakeClient(clock, {})
    queries = [{"name": "count", "method": "POST", "path": "/v1/query/advanced", "vary_window": True,
                "body": {"start_time": "2026-11-16T00:00:00+00:00", "end_time": "2026-11-17T00:00:00+00:00"}}]
    bench.run_query_bench(client, queries, repeats=3, clock=clock)

    end_times = [c[2]["end_time"] for c in client.calls]
    assert len(set(end_times)) == 3
    assert all(c[2]["start_time"] == "2026-11-16T00:00:00+00:00" for c in client.calls)
