"""
Detection-as-code (Phase 1): a tenant's rules live in git as Sigma YAML and
are synced through the same gate as the shipped library.

* `rules_to_yaml` exports rules, fixtures included, as multi-document YAML
  that re-imports unchanged.
* `plan_sync` parses a rule set (all files of a git checkout, concatenated
  as YAML documents), gates every rule (fixtures, benign corpus,
  correlation references), optionally backtests each alerting rule and
  rejects ones above `max_alerts_per_day`, and diffs the result with the
  tenant's git-synced rules. Any rejection rejects the whole sync, so a
  repository never half-applies.
* `apply_sync` writes an accepted plan.

Synced rules keep the ids written in the repository, scoped to the tenant,
and are marked created_by = 'git-sync'; rules created in the UI are never
touched. Correlations may reference rules in the same rule set.
"""

from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

import yaml

CREATED_BY = "git-sync"
MAX_RULES = 1000
_RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_COMPARED = ("name", "description", "rule_content", "severity")

BacktestFn = Callable[[str, List[Dict[str, Any]]], Awaitable[Dict[str, Any]]]


class DetectionAsCodeError(ValueError):
    """The rule set or plan can't be used, with the reason."""


# ---------------------------------------------------------------------------
# Rows <-> rules
# ---------------------------------------------------------------------------

def rule_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """A sigma_rules_mt row as the engine/backtest/export see a rule."""
    content = row.get("rule_content") or {}
    if isinstance(content, str):
        content = json.loads(content or "{}")
    return {
        "id": row["id"],
        "title": row.get("name"),
        "description": row.get("description", ""),
        "severity": row.get("severity"),
        "enabled": bool(row.get("is_enabled", True)),
        "attack_techniques": list(row.get("mitre_techniques") or []),
        "tags": content.get("tags", []),
        "kill_chain_phases": content.get("kill_chain_phases", []),
        "logsource": content.get("logsource", {}),
        "detection": content.get("detection") or {},
        "correlation": content.get("correlation"),
        "name": content.get("name"),
        "generate": content.get("generate", True),
        "references": content.get("references", []),
        "falsepositives": content.get("falsepositives", []),
        "author": content.get("author"),
        "date": content.get("date"),
        "fixtures": content.get("fixtures"),
    }


def rules_to_yaml(rules: Sequence[Dict[str, Any]], strip_prefix: str = "") -> str:
    """Rules (rule_row_to_dict shape) as Sigma YAML documents."""
    documents = []
    for rule in rules:
        rule_id = str(rule["id"])
        if strip_prefix and rule_id.startswith(strip_prefix):
            rule_id = rule_id[len(strip_prefix):]
        doc: Dict[str, Any] = {"title": rule.get("title"), "id": rule_id}
        if rule.get("name"):
            doc["name"] = rule["name"]
        if rule.get("generate") is False:
            doc["generate"] = False
        doc.update({
            "status": "stable",
            "description": rule.get("description", ""),
            "author": rule.get("author") or "",
            "date": rule.get("date") or "",
            "references": rule.get("references") or [],
            "tags": rule.get("tags") or [],
            "falsepositives": rule.get("falsepositives") or [],
            "logsource": rule.get("logsource") or {},
            "level": rule.get("severity"),
        })
        if rule.get("correlation"):
            doc["correlation"] = rule["correlation"]
        else:
            doc["detection"] = rule.get("detection") or {}
        if rule.get("fixtures"):
            doc["fixtures"] = rule["fixtures"]
        documents.append(doc)
    return yaml.safe_dump_all(documents, sort_keys=False, allow_unicode=True)


def _parse(text: str) -> List[Dict[str, Any]]:
    try:
        documents = [d for d in yaml.safe_load_all(text) if d is not None]
    except yaml.YAMLError as e:
        raise DetectionAsCodeError(f"invalid YAML: {e}")
    if not documents:
        raise DetectionAsCodeError("the rule set is empty")
    if len(documents) > MAX_RULES:
        raise DetectionAsCodeError(f"at most {MAX_RULES} rules per sync")
    seen = set()
    for document in documents:
        if not isinstance(document, dict):
            raise DetectionAsCodeError(f"not a rule (each YAML document must be a mapping): {str(document)[:80]}")
        rule_id = str(document.get("id") or "")
        if not _RULE_ID.match(rule_id):
            raise DetectionAsCodeError(f"invalid rule id {rule_id!r} (letters, digits, _ . : -)")
        if rule_id in seen:
            raise DetectionAsCodeError(f"duplicate rule id {rule_id}")
        seen.add(rule_id)
    return documents


def _gate(tenant_id: str, documents: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    from mitre_default_loader import MitreDefaultLoader

    loader = MitreDefaultLoader.__new__(MitreDefaultLoader)  # no database: gate only
    loader._condition_evaluator = None
    loader._gate_tenant = tenant_id
    loader._gate_id_prefix = ""
    loader._gate_origin = CREATED_BY
    rows, awaiting = loader._rows_from_candidates([(d, str(d["id"])) for d in documents])
    for row in rows:
        row["created_by"] = CREATED_BY
    rejected = []
    for entry in awaiting:
        rule, _, reason = entry.partition(": ")
        rejected.append({"rule": rule, "reason": reason})
    return rows, rejected


# ---------------------------------------------------------------------------
# Plan and apply
# ---------------------------------------------------------------------------

async def plan_sync(tenant_id: str, text: str, existing: Sequence[Dict[str, Any]], prune: bool = False,
                    backtest: Optional[BacktestFn] = None, backtest_days: int = 0,
                    max_alerts_per_day: Optional[float] = None,
                    reserved_ids: Sequence[str] = ()) -> Dict[str, Any]:
    """What syncing `text` would do. `existing`: the tenant's git-synced
    rows; `reserved_ids`: ids of the tenant's other rules, which a synced
    rule may not take over."""
    documents = _parse(text)
    rows, rejected = _gate(tenant_id, documents)

    reserved = set(reserved_ids)
    for row in rows:
        if row["id"] in reserved:
            rejected.append({"rule": row["id"], "reason": "id already used by a rule not managed by git sync"})

    backtests: Dict[str, Any] = {}
    if backtest is not None and backtest_days > 0 and not rejected:
        rule_dicts = [rule_row_to_dict(r) for r in rows]
        for rule in rule_dicts:
            if rule.get("generate") is False:
                continue
            result = await backtest(rule["id"], rule_dicts)
            backtests[rule["id"]] = result
            total = result.get("alerts_total", 0)
            per_day = total / backtest_days
            if max_alerts_per_day is not None and per_day > max_alerts_per_day:
                rejected.append({"rule": rule["id"], "reason": (
                    f"backtest: {total} alerts in {backtest_days} days "
                    f"({per_day:.1f}/day > {max_alerts_per_day:g}/day)")})

    current = {r["id"]: r for r in existing}
    create, update, unchanged = [], [], []
    for row in rows:
        before = current.get(row["id"])
        if before is None:
            create.append(row)
        elif any(str(before.get(k)) != str(row.get(k)) for k in _COMPARED) or not before.get("is_enabled", True):
            update.append(row)
        else:
            unchanged.append(row)
    planned = {row["id"] for row in rows}
    retire = sorted(rid for rid, row in current.items()
                    if prune and rid not in planned and row.get("is_enabled", True))

    return {
        "status": "rejected" if rejected else "ok",
        "rejected": rejected,
        "create": create,
        "update": update,
        "unchanged": unchanged,
        "retire": retire,
        "backtest": backtests,
    }


async def apply_sync(db, tenant_id: str, plan: Dict[str, Any]) -> Dict[str, int]:
    """Write an accepted plan: insert new rules, update changed ones in place,
    disable retired ones."""
    if plan.get("status") != "ok":
        raise DetectionAsCodeError("a rejected plan cannot be applied")
    from mitre_default_loader import MitreDefaultLoader

    writer = MitreDefaultLoader.__new__(MitreDefaultLoader)
    writer.database = db
    counts = {"created": 0, "updated": 0, "retired": 0}
    for row in plan["create"]:
        if await writer._insert_default_sigma_rule(row):
            counts["created"] += 1
    for row in plan["update"]:
        if await writer._update_default_sigma_rule(row):
            counts["updated"] += 1
    if plan["retire"]:
        await db.execute_update(
            "ALTER TABLE sigma_rules_mt UPDATE is_enabled = 0, updated_at = now64(3) "
            "WHERE customer_id = %(customer_id)s AND created_by = %(created_by)s AND id IN %(ids)s "
            "SETTINGS mutations_sync = 2",
            {"customer_id": tenant_id, "created_by": CREATED_BY, "ids": plan["retire"]})
        counts["retired"] = len(plan["retire"])
    return counts


def summarize(plan: Dict[str, Any]) -> Dict[str, Any]:
    """The plan for an API response: ids instead of full rows."""
    return {
        "status": plan["status"],
        "rejected": plan["rejected"],
        "create": [r["id"] for r in plan["create"]],
        "update": [r["id"] for r in plan["update"]],
        "unchanged": [r["id"] for r in plan["unchanged"]],
        "retire": plan["retire"],
        "backtest": {rid: {k: v for k, v in result.items() if k != "alerts"}
                     for rid, result in plan["backtest"].items()},
    }
