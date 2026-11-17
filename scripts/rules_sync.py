#!/usr/bin/env python3
"""
Sync a detection repository with Logforge (detection-as-code).

Collects every *.yml / *.yaml under --dir (sorted, as YAML documents), posts
them to POST /v1/security/rules/sync, prints the plan and exits:

    0  the sync is accepted (and applied with --apply)
    1  rules were rejected by the fixture gate or the backtest; nothing applied
    2  the request failed

Typical CI use: a dry run on pull requests, --apply on the main branch.

    python scripts/rules_sync.py --api https://logforge.example.com \\
        --tenant $LOGFORGE_TENANT --dir rules/ [--apply] [--prune] \\
        [--backtest-days 7 --max-alerts-per-day 50]

The token comes from --token or LOGFORGE_TOKEN.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PostFn = Callable[[str, Dict[str, Any], Dict[str, str]], Tuple[int, Dict[str, Any]]]


def collect_rule_set(directory: Path) -> str:
    files = sorted(p for p in Path(directory).rglob("*") if p.suffix in (".yml", ".yaml") and p.is_file())
    if not files:
        print(f"no *.yml or *.yaml files under {directory}", file=sys.stderr)
        raise SystemExit(2)
    return "\n---\n".join(p.read_text(encoding="utf-8") for p in files)


def _post(url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {"detail": str(e)}


def _print_plan(plan: Dict[str, Any]) -> None:
    for key in ("create", "update", "retire"):
        for rule_id in plan.get(key, []):
            print(f"  {key:8} {rule_id}")
    print(f"  unchanged: {len(plan.get('unchanged', []))}")
    for rule_id, result in sorted(plan.get("backtest", {}).items()):
        print(f"  backtest {rule_id}: {result.get('alerts_total')} alerts "
              f"over {result.get('events_scanned')} events")
    for item in plan.get("rejected", []):
        print(f"  REJECTED {item['rule']}: {item['reason']}")


def main(argv: Optional[List[str]] = None, post: PostFn = _post) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--api", required=True, help="Logforge API base URL")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--token", default=os.getenv("LOGFORGE_TOKEN"))
    parser.add_argument("--dir", default="rules", type=Path)
    parser.add_argument("--apply", action="store_true", help="apply the plan (default: dry run)")
    parser.add_argument("--prune", action="store_true", help="disable synced rules no longer in the repository")
    parser.add_argument("--backtest-days", type=int, default=0)
    parser.add_argument("--max-alerts-per-day", type=float)
    args = parser.parse_args(argv)
    if not args.token:
        print("a token is required (--token or LOGFORGE_TOKEN)", file=sys.stderr)
        return 2

    body = {"yaml": collect_rule_set(args.dir), "dry_run": not args.apply, "prune": args.prune,
            "backtest_days": args.backtest_days, "max_alerts_per_day": args.max_alerts_per_day}
    status, plan = post(f"{args.api.rstrip('/')}/v1/security/rules/sync", body,
                        {"X-Customer-ID": args.tenant, "Authorization": f"Bearer {args.token}"})
    if status != 200:
        print(f"sync failed ({status}): {plan.get('detail', plan)}", file=sys.stderr)
        return 2
    mode = "applied" if plan.get("applied") else "dry run"
    print(f"rule sync {plan['status']} ({mode})")
    _print_plan(plan)
    if plan.get("applied"):
        print(f"  applied: {plan['applied']}")
    return 0 if plan["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
