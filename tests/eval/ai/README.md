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

## Status

This is the Phase 0 skeleton: scorers, small seed datasets (8 / 5 / 5 items)
and tests (`tests/test_ai_eval_harness.py`) proving that a perfect system
scores 1.0 and a null system 0. Next:

- grow each dataset (Phase 9 targets ≥ 200 `nl2query` items per schema);
- execution accuracy for `nl2query` against a seeded stack, alongside the
  offline equivalence check;
- score the current rule-based NLQ (`apps/api/services/nlq_processor.py`) as
  the no-AI baseline once it can emit LogforgeQL.
