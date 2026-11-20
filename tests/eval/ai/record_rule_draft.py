#!/usr/bin/env python3
"""
Record a model's detection drafts for datasets/rule_behaviours.jsonl
(Phase 10) and score them: passed within two attempts (target >= 70%),
first-attempt passes, held-out recall and quiet.

    ANTHROPIC_API_KEY=... python tests/eval/ai/record_rule_draft.py \\
        --provider anthropic:claude-opus-5-5 [--update-baseline]

Writes recordings/rule_draft.jsonl (replacing it), replayed by
tests/test_ai_rule_draft_eval.py in CI. One or two model calls per behaviour.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for extra in (HERE.parents[2] / "apps" / "api", HERE):
    sys.path.insert(0, str(extra))

import rule_draft_eval as rde  # noqa: E402
from ai.providers.recorded import RecordedProvider  # noqa: E402
from run_ai_eval import live_provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", required=True)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()
    path = HERE / "recordings" / "rule_draft.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text("")  # a fresh recording
    provider = RecordedProvider(path, inner=live_provider(args.provider), record=True)
    result = rde.score(rde.load(), rde.model_drafter(provider))
    print(json.dumps({k: v for k, v in result.items() if k != "per_behaviour"}, indent=2))
    if args.update_baseline:
        baseline_path = HERE / "baseline_rule_draft.json"
        baseline = json.loads(baseline_path.read_text())
        baseline["model"] = {k: result[k] for k in ("passed", "first", "held_out_recall", "held_out_quiet")}
        baseline_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
