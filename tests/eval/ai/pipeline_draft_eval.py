"""
Scoring pipeline drafts (Phase 9) on held-out formats: the sample files of
the content packs (packages/packs/*/samples). The drafter never sees the
packs' own pipelines; it gets the raw lines and the service name.

Per sample file:

* parse rate: the share of lines the draft parses in simulation (ran
  without failing and extracted fields);
* value recall: the pack's expectations name field values its own pipeline
  extracts (attrs.result: failed, user_id: deploy, ...). Those that appear
  literally in the raw line can be recovered by any parser, whatever it
  names the field; recall is the share of them found among the values the
  draft extracted from the same lines. Values a pack derives (an OCSF class
  id, a normalised word) aren't in the line and are not counted.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[3]
PACKS = REPO / "packages" / "packs"


def load() -> list[dict[str, Any]]:
    from source_packs import load_pack

    items = []
    for root in sorted(p for p in PACKS.iterdir() if (p / "pack.yml").exists() and not p.name.startswith("_")):
        pack = load_pack(root)
        for sample in pack.samples:
            items.append({"id": f"{pack.id}/{sample.file}", "service": sample.service, "lines": sample.lines,
                          "expect": sample.expect})
    return items


def _values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [v for x in value.values() for v in _values(x)]
    if isinstance(value, list):
        return [v for x in value for v in _values(x)]
    return [] if value is None else [str(value).lower()]


def recoverable(item: dict[str, Any]) -> list[tuple[str, str]]:
    """(contains, value) pairs: expected values present in a matching raw line."""
    out = []
    for expected in item["expect"]:
        lines = [line for line in item["lines"] if not expected.get("contains") or expected["contains"] in line]
        for value in (expected.get("fields") or {}).values():
            text = str(value)
            if len(text) >= 2 and any(text in line for line in lines):
                out.append((expected.get("contains") or "", text))
    return out


def score_item(item: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    from ai.pipeline_draft import _doc, validate
    from pipeline_processors import ProcessorContext
    from pipelines import Pipeline, simulate

    report = validate(definition, item["lines"], item["service"])
    wanted = recoverable(item)
    found = 0
    if report["valid"] and wanted:
        pipeline = Pipeline.from_dict({"name": "draft", **definition})
        results = simulate(pipeline, [_doc(line, item["service"]) for line in item["lines"]],
                           ProcessorContext(tenant_id="draft"))
        extracted = {}
        for line, result in zip(item["lines"], results):
            doc = dict(result.get("doc") or {})
            doc.pop("msg", None)
            extracted[line] = set(_values(doc))
        for contains, value in wanted:
            if any(value.lower() in extracted[line] for line in item["lines"] if contains in line):
                found += 1
    return {"id": item["id"], "parsed": report["parsed"], "total": report["total"],
            "parse_rate": report["parsed"] / report["total"] if report["total"] else 0.0,
            "recall_found": found, "recall_total": len(wanted)}


def score(items: list[dict[str, Any]], drafter: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    per_item = [score_item(item, drafter(item)) for item in items]
    parsed = sum(i["parsed"] for i in per_item)
    total = sum(i["total"] for i in per_item)
    found = sum(i["recall_found"] for i in per_item)
    wanted = sum(i["recall_total"] for i in per_item)
    return {"files": len(items), "lines": total, "parse_rate": round(parsed / total, 4) if total else 0.0,
            "value_recall": round(found / wanted, 4) if wanted else 0.0, "values": wanted, "per_item": per_item}


def heuristic_drafter(item: dict[str, Any]) -> dict[str, Any]:
    from ai.pipeline_draft import heuristic

    return heuristic(item["lines"], item["service"]).pipeline


def model_drafter(provider) -> Callable[[dict[str, Any]], dict[str, Any]]:
    from ai.pipeline_draft import draft
    from ai.redaction import Redactor

    return lambda item: asyncio.run(draft(item["lines"], provider, redactor=Redactor([]),
                                          service=item["service"])).pipeline
