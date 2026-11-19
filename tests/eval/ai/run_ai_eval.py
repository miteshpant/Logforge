#!/usr/bin/env python3
"""
Run the AI features against their evaluation datasets (Phase 8).

    # score the features from their recordings (what CI does; no network)
    python tests/eval/ai/run_ai_eval.py

    # record a provider's answers (replaces the recordings), then score them
    python tests/eval/ai/run_ai_eval.py --record --provider claude

    # after recording: make the scores the CI baseline
    python tests/eval/ai/run_ai_eval.py --update-baseline

A provider is one of config/ai.yml's providers (by name), or one given in
full: --provider anthropic:claude-opus-5-5 (key from ANTHROPIC_API_KEY),
openai_compatible:<model>@<base_url> (key from LOGFORGE_EVAL_API_KEY, if
set) or ollama:<model>@<base_url>. Recording calls the model once per
dataset item.

Recordings: recordings/<feature>.jsonl. Baseline: baseline.json, the score
each recorded feature must keep (tests/test_ai_eval_gate.py fails below it).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for extra in (REPO / "apps" / "api", HERE):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import ai_eval
from ai.features import nl2query, summarise
from ai.providers import ProviderSettings, build_provider, load_ai_config
from ai.providers.recorded import RecordedProvider

RECORDINGS = HERE / "recordings"
BASELINE = HERE / "baseline.json"

# feature -> (dataset task, async (item, provider) -> output)
FEATURES: dict[str, tuple[str, Callable[[dict[str, Any], Any], Any]]] = {
    "nl2query": ("nl2query", lambda item, p: nl2query(item["question"], p)),
    "summaries": ("summaries", lambda item, p: summarise(item["task"], item["evidence"], p)),
}


def live_provider(spec: str):
    config = load_ai_config()
    if spec in config.providers:
        return build_provider(config.providers[spec])
    kind, _, rest = spec.partition(":")
    model, _, base_url = rest.partition("@")
    if kind == "anthropic":
        settings = ProviderSettings(name="eval", kind="anthropic", model=model or "claude-opus-5-5",
                                    api_key_env="ANTHROPIC_API_KEY")
    elif kind in ("openai_compatible", "ollama"):
        settings = ProviderSettings(name="eval", kind=kind, model=model, base_url=base_url,
                                    api_key_env="LOGFORGE_EVAL_API_KEY" if os.getenv("LOGFORGE_EVAL_API_KEY") else None)
    else:
        raise SystemExit(f"unknown provider {spec!r}")
    return build_provider(settings)


async def outputs(feature: str, provider) -> dict[str, Any]:
    task, run = FEATURES[feature]
    out = {}
    for item in ai_eval.load_dataset(task):
        out[item["id"]] = await run(item, provider)
    return out


def score(feature: str, provider) -> dict[str, Any]:
    task, _ = FEATURES[feature]
    answers = asyncio.run(outputs(feature, provider))
    return ai_eval.evaluate(task, lambda item: answers[item["id"]])


def load_baseline() -> dict[str, Any]:
    return json.loads(BASELINE.read_text()) if BASELINE.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--feature", choices=sorted(FEATURES), action="append")
    parser.add_argument("--record", action="store_true", help="call --provider and replace the recordings")
    parser.add_argument("--provider", help="the live provider to record from")
    parser.add_argument("--update-baseline", action="store_true", help="store the recorded scores as the baseline")
    args = parser.parse_args()
    features = args.feature or sorted(FEATURES)
    baseline = load_baseline()
    results = {}
    for feature in features:
        path = RECORDINGS / f"{feature}.jsonl"
        if args.record:
            if not args.provider:
                raise SystemExit("--record needs --provider")
            live = live_provider(args.provider)
            path.unlink(missing_ok=True)
            provider = RecordedProvider(path, inner=live, record=True)
        else:
            if not path.exists():
                print(f"{feature:10s} no recording ({path.relative_to(REPO)}); record one with --record")
                continue
            provider = RecordedProvider(path)
        result = score(feature, provider)
        results[feature] = {"score": result["score"], "items": result["items"], "model": provider.model}
        floor = baseline.get(feature, {}).get("min_score")
        note = f"(baseline {floor})" if floor is not None else "(no baseline)"
        print(f"{feature:10s} {result['score']:.3f} over {result['items']} items, model {provider.model} {note}")
        for item_id, value in result["per_item"].items():
            if value < 1:
                print(f"    {item_id}: {value}")
    if args.update_baseline:
        for feature, result in results.items():
            baseline[feature] = {"min_score": result["score"], "model": result["model"],
                                 "recorded_at": datetime.now(timezone.utc).date().isoformat()}
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
        print(f"baseline written to {BASELINE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
