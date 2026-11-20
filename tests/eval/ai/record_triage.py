#!/usr/bin/env python3
"""
Record a model's triage summaries for datasets/triage.jsonl (Phase 9) and
score them: uncited sentences (must be 0), the model's raw uncited rate
(sentences dropped for not citing) and fact coverage.

    ANTHROPIC_API_KEY=... python tests/eval/ai/record_triage.py \\
        --provider anthropic:claude-opus-5-5 [--update-baseline]

Writes recordings/triage.jsonl (replacing it), replayed by
tests/test_ai_triage_eval.py in CI. One model call per item (20).
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for extra in (HERE.parents[2] / "apps" / "api", HERE):
    sys.path.insert(0, str(extra))

import triage_eval as te  # noqa: E402
from ai.providers.recorded import RecordedProvider  # noqa: E402
from run_ai_eval import live_provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()
    path = HERE / "recordings" / "triage.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text("")  # a fresh recording
    provider = RecordedProvider(path, inner=live_provider(args.provider), record=True)
    result = te.score(te.load(), te.model_writer(provider))
    print(json.dumps({k: v for k, v in result.items() if k != "per_item"}, indent=2))
    if args.update_baseline:
        baseline_path = HERE / "baseline_triage.json"
        baseline = json.loads(baseline_path.read_text())
        baseline["model"] = {"fact_coverage": result["fact_coverage"],
                             "raw_uncited_rate": result["raw_uncited_rate"]}
        baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    return 0 if result["uncited"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
