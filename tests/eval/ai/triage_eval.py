"""
Scoring triage summaries (Phase 9) on datasets/triage.jsonl.

For each item the bundle is built from the stored evidence (no database),
the summary is written, and we count:

* uncited: sentences in the summary that cite nothing or cite an id that
  wasn't issued. The target is zero; the product drops such sentences, so
  this is zero by construction and the test fails if it ever isn't.
* dropped: sentences the model wrote that were removed for that reason
  (always 0 for the template). Reported as the model's raw uncited rate.
* fact coverage: the share of the item's required facts (title, entities,
  ATT&CK techniques, intel sources) the summary states.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
DATASET = HERE / "datasets" / "triage.jsonl"


def load() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def bundle_for(item: dict[str, Any]):
    from ai.triage import build_bundle

    return build_bundle(item["kind"], item["subject_id"], alert=item.get("alert"), case=item.get("case"),
                        activity=item.get("activity"), intel=item.get("intel"))


def score(items: list[dict[str, Any]], writer: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
    from ai.citations import check_citations

    per_item, sentences, uncited, dropped, facts_hit, facts_all = [], 0, 0, 0, 0, 0
    for item in items:
        bundle = bundle_for(item)
        out = writer(bundle)
        lines = [s for section in out["sections"] for s in section["sentences"]]
        text = "\n".join(lines)
        check = check_citations(text, {e.cid: e for e in bundle.evidence})
        bad = len(check["uncited"]) + len(check["unknown"])
        hits = [f for f in item["required_facts"] if str(f).lower() in text.lower()]
        sentences += len(lines)
        uncited += bad
        dropped += len(out.get("dropped") or [])
        facts_hit += len(hits)
        facts_all += len(item["required_facts"])
        per_item.append({"id": item["id"], "mode": out["mode"], "sentences": len(lines), "uncited": bad,
                         "dropped": out.get("dropped") or [],
                         "missing_facts": [f for f in item["required_facts"] if f not in hits]})
    written = sentences + dropped
    return {"items": len(items), "sentences": sentences, "uncited": uncited, "dropped": dropped,
            "raw_uncited_rate": round(dropped / written, 4) if written else 0.0,
            "fact_coverage": round(facts_hit / facts_all, 4) if facts_all else 1.0, "per_item": per_item}


def template_writer(bundle):
    from ai.triage import template

    return template(bundle)


def model_writer(provider) -> Callable[[Any], dict[str, Any]]:
    from ai.redaction import Redactor
    from ai.triage import write

    return lambda bundle: asyncio.run(write(bundle, provider, redactor=Redactor([])))
