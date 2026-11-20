#!/usr/bin/env python3
"""
Record a model's answers to the natural-language -> LogforgeQL evaluation
sets (Phase 9) and score them by execution accuracy.

Needs ClickHouse (the seeded week of events gives the field catalogue the
prompt includes, and runs the queries) and a provider:

    LOGFORGE_TEST_CLICKHOUSE=localhost:8124 ANTHROPIC_API_KEY=... \\
      python tests/eval/ai/record_nl2query_exec.py --provider anthropic:claude-opus-5-5 [--update-baseline]

Writes recordings/nl2query_exec_<schema>.jsonl (replayed by
tests/test_nl2query_eval_live.py in CI) and prints the score per schema.
Calls the model once per question (~660 questions; more for repairs).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for extra in (REPO / "apps" / "api", REPO / "tests", HERE):
    sys.path.insert(0, str(extra))

import nl2query_exec as ne  # noqa: E402
from ai.nl2query import translate  # noqa: E402
from ai.providers.recorded import RecordedProvider  # noqa: E402
from run_ai_eval import live_provider  # noqa: E402
from test_analyst_questions_live import END, START, make_events  # noqa: E402
from test_logql_pipeline_live import _client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--schema", choices=ne.SCHEMAS, action="append")
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()
    client = _client()
    if client is None:
        raise SystemExit("ClickHouse is not reachable (set LOGFORGE_TEST_CLICKHOUSE)")
    seeded = ne.Seeded(client, make_events(), START, END)
    baseline_path = HERE / "baseline_nl2query_exec.json"
    baseline = json.loads(baseline_path.read_text())
    try:
        catalogue = seeded.catalogue()
        for schema in args.schema or ne.SCHEMAS:
            path = HERE / "recordings" / f"nl2query_exec_{schema}.jsonl"
            path.unlink(missing_ok=True)
            provider = RecordedProvider(path, inner=live_provider(args.provider), record=True)
            result = ne.score(seeded, ne.load(schema), lambda item: asyncio.run(
                translate(item["question"], provider, catalogue=catalogue)).query)
            print(f"{schema}: {result['score']:.3f} over {result['items']} items")
            if args.update_baseline:
                baseline.setdefault("model", {})[schema] = result["score"]
    finally:
        seeded.drop()
    if args.update_baseline:
        baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
