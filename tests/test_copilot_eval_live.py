"""
The investigation copilot on the evaluation scenarios (Phase 10), against
ClickHouse: the root cause must be found (among the candidates) in at least
the recorded share of scenarios, and nothing it shows may be fabricated.
The roadmap's target is >= 80% found with no fabricated evidence.

Needs ClickHouse (LOGFORGE_TEST_CLICKHOUSE); skipped otherwise, unless
LOGFORGE_REQUIRE_CLICKHOUSE is set.
"""

import json
import os
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent / "eval" / "ai"
sys.path.insert(0, str(EVAL))

import copilot_eval as ce  # noqa: E402
from test_logql_pipeline_live import _client  # noqa: E402

BASELINE = json.loads((EVAL / "baseline_copilot.json").read_text())
RECORDING = EVAL / "recordings" / "copilot.jsonl"


@pytest.fixture(scope="module")
def seeded():
    client = _client()
    if client is None:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse is required but not reachable")
        pytest.skip("ClickHouse not reachable (set LOGFORGE_TEST_CLICKHOUSE)")
    store = ce.Seeded(client, ce.load())
    yield store
    store.drop()


def test_the_scenarios():
    scenarios = ce.load()
    assert len(scenarios) >= 20 and len({s["kind"] for s in scenarios}) >= 10
    for s in scenarios:
        assert sum(e["attrs"]["eid"] == s["root"] for e in s["events"]) == 1, s["id"]


def test_the_copilot_finds_the_root_cause_and_fabricates_nothing(seeded):
    result = ce.score(ce.load(), seeded)
    assert result["fabricated"] == 0, [p for p in result["per_scenario"] if p["fabricated"]]
    assert result["found"] >= max(0.8, BASELINE["template"]["found"]), result["per_scenario"]
    assert result["first"] >= BASELINE["template"]["first"]


@pytest.mark.skipif(not RECORDING.exists(), reason="no recorded model answers (see tests/eval/ai/README.md)")
def test_the_recorded_model(seeded):
    from ai.providers.recorded import RecordedProvider

    result = ce.score(ce.load(), seeded, ce.model_writer(RecordedProvider(RECORDING)))
    assert result["fabricated"] == 0
    floor = BASELINE.get("model") or {}
    if floor:
        assert result["found"] >= floor["found"]
