#!/usr/bin/env python3
"""
Record a model's pipeline drafts for the content packs' sample files
(Phase 9) and score parse rate and value recall.

    ANTHROPIC_API_KEY=... python tests/eval/ai/record_pipeline_draft.py \\
        --provider anthropic:claude-opus-5-5 [--update-baseline]

Writes recordings/pipeline_draft.jsonl (replacing it), replayed by
tests/test_ai_pipeline_draft_eval.py in CI. One or two model calls per file.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for extra in (HERE.parents[2] / "apps" / "api", HERE):
    sys.path.insert(0, str(extra))

import pipeline_draft_eval as pe  # noqa: E402
from ai.providers.recorded import RecordedProvider  # noqa: E402
from run_ai_eval import live_provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()
    path = HERE / "recordings" / "pipeline_draft.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text("")  # a fresh recording
    provider = RecordedProvider(path, inner=live_provider(args.provider), record=True)
    result = pe.score(pe.load(), pe.model_drafter(provider))
    print(json.dumps({k: v for k, v in result.items() if k != "per_item"}, indent=2))
    if args.update_baseline:
        baseline_path = HERE / "baseline_pipeline_draft.json"
        baseline = json.loads(baseline_path.read_text())
        baseline["model"] = {"parse_rate": result["parse_rate"], "value_recall": result["value_recall"]}
        baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
