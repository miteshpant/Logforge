"""
Phase 6 acceptance benchmark harness (tests/bench/analytics_bench.py): the
question set, the seed statement and the timing logic, without a stack.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "bench"))

import analytics_bench as bench  # noqa: E402


def test_the_question_set_is_the_acceptance_set():
    questions = bench.load_questions()
    assert len(questions) == 30
    assert all(q["query"].startswith("|") and q["question"] for q in questions)


def test_seed_sql_is_one_bounded_insert_for_the_tenant():
    sql = bench.seed_sql("acme'; DROP TABLE x --", 1000, offset=5)
    assert sql.count("INSERT INTO logs_raw_mt") == 1 and "FROM numbers(1000)" in sql
    assert "'acme; DROP TABLE x --'" in sql  # quotes stripped from the tenant id
    assert "number + 5 AS n" in sql


class Client:
    def __init__(self, clock):
        self.clock, self.calls = clock, []

    def post(self, path, body):
        self.calls.append((path, body))
        self.clock.now += 0.5 if len(self.calls) == 1 else 0.1  # the first run is cold
        return {"total_count": 3, "query_info": {"estimated_rows": 1234, "hourly_counts": True}}


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_first_runs_are_reported_apart_from_warm_ones():
    clock = Clock()
    client = Client(clock)
    out = bench.run_questions(client, [{"id": "q", "question": "Q", "query": "| stats count()"}], repeats=5, clock=clock)
    r = out["q"]
    assert r["first_ms"] == 500.0 and r["count"] == 4 and abs(r["p95_ms"] - 100.0) < 1e-6
    assert r["estimated_rows_read"] == 1234 and r["hourly_counts"] is True and r["rows_returned"] == 3
    assert client.calls[0] == ("/v1/query/logql", {"query": "| stats count()", "since": "7d"})
