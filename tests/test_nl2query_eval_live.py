"""
Natural language -> LogforgeQL, execution accuracy (Phase 9) on the three
evaluation sets (tests/eval/ai/datasets/nl2query_{auth,http,dns}.jsonl, 200+
pairs each) against the Phase 6 seeded week of events in ClickHouse.

* every expected query runs and scores 1.0 against itself;
* the rule-based fallback (AI off) is scored per schema and must not drop
  below its baseline in tests/eval/ai/baseline_nl2query_exec.json;
* the model-backed feature is scored from recordings when they exist
  (tests/eval/ai/recordings/nl2query_exec_<schema>.jsonl, made by
  tests/eval/ai/record_nl2query_exec.py) and must reach its baseline.

Runs where ClickHouse is reachable (the live-stack CI job).
"""

import json
from pathlib import Path

import pytest

import nl2query_exec as ne
from ai.nl2query import rule_based
from test_analyst_questions_live import END, START, make_events
from test_logql_pipeline_live import MIGRATION, _client

BASELINE = json.loads((Path(ne.HERE) / "baseline_nl2query_exec.json").read_text())
RESULTS = Path(ne.HERE) / "results"


@pytest.fixture(scope="module")
def seeded():
    client = _client()
    if client is None:
        import os

        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE") == "1":
            pytest.fail("ClickHouse is not reachable and LOGFORGE_REQUIRE_CLICKHOUSE=1")
        pytest.skip("ClickHouse is not reachable")
    sql = "\n".join(l for l in open(MIGRATION).read().splitlines() if not l.lstrip().startswith("--"))
    for statement in sql.split(";"):
        if "CREATE TABLE" in statement:
            client.command(statement)
    s = ne.Seeded(client, make_events(), START, END)
    yield s
    s.drop()


@pytest.mark.parametrize("schema", ne.SCHEMAS)
def test_each_set_has_200_pairs_and_every_expected_query_returns_rows(seeded, schema):
    items = ne.load(schema)
    assert len(items) >= 200
    result = ne.score(seeded, items, lambda item: item["expected_query"])
    assert result["score"] == 1.0
    empty = [q for q in {i["expected_query"] for i in items} if not seeded.rows(q)]
    assert empty == [], empty


@pytest.mark.parametrize("schema", ne.SCHEMAS)
def test_rule_based_fallback_keeps_its_score(seeded, schema):
    catalogue = seeded.catalogue()
    result = ne.score(seeded, ne.load(schema), lambda item: rule_based(item["question"], catalogue).query)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"nl2query_rule_based_{schema}.json").write_text(json.dumps(
        {k: result[k] for k in ("items", "score", "failures")}, indent=1, default=str) + "\n")
    floor = BASELINE.get("rule_based", {}).get(schema)
    print(f"rule-based {schema}: {result['score']} over {result['items']} items (baseline {floor})")
    if floor is None:
        pytest.skip(f"no baseline yet for the rule-based {schema} score ({result['score']})")
    assert result["score"] >= floor, result["failures"][:10]


@pytest.mark.parametrize("schema", ne.SCHEMAS)
def test_model_feature_from_recordings(seeded, schema):
    path = Path(ne.HERE) / "recordings" / f"nl2query_exec_{schema}.jsonl"
    floor = BASELINE.get("model", {}).get(schema)
    if not path.exists() or floor is None:
        pytest.skip(f"{schema}: no recorded model answers yet (see tests/eval/ai/README.md)")
    import asyncio

    from ai.nl2query import translate
    from ai.providers.recorded import RecordedProvider

    provider, catalogue = RecordedProvider(path), seeded.catalogue()
    result = ne.score(seeded, ne.load(schema), lambda item: asyncio.run(
        translate(item["question"], provider, catalogue=catalogue)).query)
    assert result["score"] >= floor, result["failures"][:10]
