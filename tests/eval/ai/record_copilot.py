#!/usr/bin/env python3
"""
Record a model's investigations of the copilot scenarios (Phase 10) and
score them: root cause found, first, and fabricated evidence (must be 0).

    LOGFORGE_TEST_CLICKHOUSE=localhost:8124 ANTHROPIC_API_KEY=... \\
      python tests/eval/ai/record_copilot.py --provider anthropic:claude-opus-5-5 [--update-baseline]

Writes recordings/copilot.jsonl (replacing it), replayed by
tests/test_copilot_eval_live.py in CI. One model call per scenario (20).
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for extra in (REPO / "apps" / "api", REPO / "tests", HERE):
    sys.path.insert(0, str(extra))

import copilot_eval as ce  # noqa: E402
from ai.providers.recorded import RecordedProvider  # noqa: E402
from run_ai_eval import live_provider  # noqa: E402
from test_logql_pipeline_live import _client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()
    client = _client()
    if client is None:
        raise SystemExit("ClickHouse is not reachable (set LOGFORGE_TEST_CLICKHOUSE)")
    path = HERE / "recordings" / "copilot.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text("")  # a fresh recording
    provider = RecordedProvider(path, inner=live_provider(args.provider), record=True)
    seeded = ce.Seeded(client, ce.load())
    try:
        result = ce.score(ce.load(), seeded, ce.model_writer(provider))
    finally:
        seeded.drop()
    print(json.dumps({k: v for k, v in result.items() if k != "per_scenario"}, indent=2))
    if args.update_baseline:
        baseline_path = HERE / "baseline_copilot.json"
        baseline = json.loads(baseline_path.read_text())
        baseline["model"] = {"found": result["found"], "first": result["first"]}
        baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    return 0 if result["fabricated"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
