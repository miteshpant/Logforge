# AI evaluation

Every AI feature must reach its target on these evaluations before it ships
([PLATFORM_ROADMAP.md](../../../docs/PLATFORM_ROADMAP.md), Phases 8–10). The
harness is provider-agnostic: a *system* is any function `item -> output`, so
a model-backed feature, a rule-based fallback, or the dataset's reference
answer are all scored the same way.

| Task | Input → output | Item score |
|---|---|---|
| `nl2query` | question → LogforgeQL | 1 if it compiles to the same request as the reference (filters, aggregations, grouping order-insensitive; relative windows compared by length), else 0 |
| `summaries` | evidence `{E1: ...}` → summary citing `[E1]` | required-fact coverage (0–1), but **0 if any sentence is uncited or cites evidence that doesn't exist** |
| `rule_drafting` | behaviour description → Sigma YAML with fixtures | 1 if the draft passes the platform's fixture gate, detects the item's attack events, and raises nothing on the benign corpus from `tests/eval/detection` |

```bash
python tests/eval/ai/ai_eval.py    # scores the reference answers (all 1.0)
```

```python
import ai_eval
result = ai_eval.evaluate("nl2query", my_feature)   # my_feature(item) -> str
print(result["score"], result["per_item"])
```

## Features and the CI gate (Phase 8)

`run_ai_eval.py` runs the AI features in `apps/api/ai/features.py` against
these datasets through any provider:

| Feature | Dataset | What it does |
|---|---|---|
| `nl2query` | `nl2query` | question → one LogforgeQL query; an answer that doesn't compile counts as none |
| `summaries` | `summaries` | evidence → a two-to-four sentence summary citing `[E#]` |

CI runs them from **recordings** of a real model (`recordings/<feature>.jsonl`,
replayed by `ai.providers.recorded.RecordedProvider`, so no network or cost),
and `tests/test_ai_eval_gate.py` fails if a feature scores below its entry in
`baseline.json`. A recording is keyed by a hash of the whole request (model,
prompt, messages, tools): change a prompt and the old answers no longer
match, so the gate fails until the feature is re-recorded.

```bash
# record (calls the model once per item) and look at the scores
ANTHROPIC_API_KEY=... python tests/eval/ai/run_ai_eval.py --record --provider anthropic:claude-opus-5-5
# make them the baseline CI holds the feature to
python tests/eval/ai/run_ai_eval.py --update-baseline
```

`--provider` also takes a provider name from `config/ai.yml`, or
`ollama:<model>@<url>` / `openai_compatible:<model>@<url>` for a local model.

**Not yet gated:** no recordings are committed yet (they need a model API
key), so both features are reported as skipped by the gate. The harness,
recorder and gate are tested end to end with a scripted stand-in.

## Status

This is the Phase 0 skeleton: scorers, small seed datasets (8 / 5 / 5 items)
and tests (`tests/test_ai_eval_harness.py`) proving that a perfect system
scores 1.0 and a null system 0. Next:

- grow each dataset (Phase 9 targets ≥ 200 `nl2query` items per schema);
- execution accuracy for `nl2query` against a seeded stack, alongside the
  offline equivalence check;
- score the current rule-based NLQ (`apps/api/services/nlq_processor.py`) as
  the no-AI baseline once it can emit LogforgeQL.
