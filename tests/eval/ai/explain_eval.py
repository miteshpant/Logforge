"""
Scoring "explain this event" (Phase 9) on the content packs' sample events:
each pack's samples, parsed by its own pipelines (pack CI), are explained.

* uncited: sentences without a valid citation (must be 0);
* identified: events the explanation says what they are (a reference
  entry: event ID, message pattern, HTTP status, OCSF class) rather than
  "an event from <service>";
* rule recall: a pack sample lists the rules its events must fire; the
  share of those the explanation of at least one of its events names.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[3]
PACKS = REPO / "packages" / "packs"


def load() -> list[dict[str, Any]]:
    from pack_ci import check_pack
    from source_packs import load_pack

    items = []
    for root in sorted(p for p in PACKS.iterdir() if (p / "pack.yml").exists() and not p.name.startswith("_")):
        pack = load_pack(root)
        report = check_pack(pack)
        for sample in pack.samples:
            items.append({"id": f"{pack.id}/{sample.file}", "events": report.events.get(sample.file, []),
                          "rules": list(sample.rules)})
    return items


def score(items: list[dict[str, Any]], explainer: Callable[[dict[str, Any]], tuple[Any, dict[str, Any]]]):
    from ai.citations import check_citations

    events = identified = uncited = rules_found = rules_wanted = 0
    per_item = []
    for item in items:
        named: set[str] = set()
        for event in item["events"]:
            bundle, out = explainer(event)
            text = "\n".join(s for section in out["sections"] for s in section["sentences"])
            check = check_citations(text, {e.cid: e for e in bundle.evidence})
            uncited += len(check["uncited"]) + len(check["unknown"])
            events += 1
            identified += bool(bundle.kinds)
            named |= {str(e.data.get("id")) for e in bundle.evidence if e.kind == "rule"}
        found = [r for r in item["rules"] if any(n == r or n.endswith(f".{r}") or n.endswith(f"/{r}")
                                                 for n in named)]
        rules_found += len(found)
        rules_wanted += len(item["rules"])
        per_item.append({"id": item["id"], "events": len(item["events"]),
                         "missing_rules": [r for r in item["rules"] if r not in found]})
    return {"events": events, "uncited": uncited, "identified": round(identified / events, 4) if events else 0.0,
            "rule_recall": round(rules_found / rules_wanted, 4) if rules_wanted else 1.0, "rules": rules_wanted,
            "per_item": per_item}


def template_explainer(event: dict[str, Any]):
    from ai.explain import gather, template
    from ai.tools import ToolContext

    bundle = asyncio.run(gather(event, ToolContext(tenant_id="eval", user_id="eval", roles=[])))
    return bundle, template(bundle)


def model_explainer(provider):
    from ai.explain import gather, write
    from ai.redaction import Redactor
    from ai.tools import ToolContext

    def explain(event):
        bundle = asyncio.run(gather(event, ToolContext(tenant_id="eval", user_id="eval", roles=[])))
        return bundle, asyncio.run(write(bundle, provider, redactor=Redactor([])))
    return explain
