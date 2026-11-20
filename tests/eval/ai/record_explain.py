#!/usr/bin/env python3
"""
Record a model's explanations of the content packs' sample events (Phase 9)
and score them: uncited sentences (must be 0), events identified, expected
rules named.

    ANTHROPIC_API_KEY=... python tests/eval/ai/record_explain.py \\
        --provider anthropic:claude-opus-5-5

Writes recordings/explain.jsonl (replacing it), replayed by
tests/test_ai_explain_eval.py in CI. One model call per event (83).
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for extra in (HERE.parents[2] / "apps" / "api", HERE):
    sys.path.insert(0, str(extra))

import explain_eval as ee  # noqa: E402
from ai.providers.recorded import RecordedProvider  # noqa: E402
from run_ai_eval import live_provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", required=True)
    args = parser.parse_args()
    path = HERE / "recordings" / "explain.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text("")  # a fresh recording
    provider = RecordedProvider(path, inner=live_provider(args.provider), record=True)
    result = ee.score(ee.load(), ee.model_explainer(provider))
    print(json.dumps({k: v for k, v in result.items() if k != "per_item"}, indent=2))
    return 0 if result["uncited"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
