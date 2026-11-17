"""
Detection-as-code (Phase 1): a tenant's rules live in git as Sigma YAML.

* `rules_to_yaml` exports rules (fixtures included) so they re-import as-is.
* `plan_sync` takes the rule set from a git checkout (multi-document YAML),
  puts every rule through the same fixture gate as the shipped library
  (correlations included), optionally backtests each one and rejects rules
  that would alert more than `max_alerts_per_day`, and diffs the result with
  the tenant's synced rules: create / update / unchanged / retire (prune).
  If any rule is rejected nothing is applied.
* `apply_sync` writes the plan (inserts, in-place updates, disables retired
  rules); rule ids are kept as written, scoped to the tenant.
"""

import asyncio
import json

import pytest
import yaml

from detection_as_code import DetectionAsCodeError, apply_sync, plan_sync, rule_row_to_dict, rules_to_yaml

FAILED = {"event_type": "authentication", "result": "failed", "src_ip": "203.0.113.9", "user": "root"}

BASE = {"title": "Failed login", "id": "acme-auth-failed", "name": "acme_auth_failed", "generate": False,
        "level": "low", "description": "building block", "tags": ["attack.t1110"],
        "detection": {"selection": {"event_type": "authentication", "result": "failed"}, "condition": "selection"},
        "fixtures": {"true_positive": FAILED, "true_negative": dict(FAILED, result="success")}}
SPRAY = {"title": "Spray", "id": "acme-spray", "level": "high", "description": "spray",
         "tags": ["attack.credential_access", "attack.t1110.003"],
         "correlation": {"type": "value_count", "rules": ["acme_auth_failed"], "group-by": ["src_ip"],
                         "timespan": "10m", "condition": {"field": "user", "gte": 3}},
         "fixtures": {"true_positive_batch": [dict(FAILED, user=f"u{i}") for i in range(3)],
                      "true_negative_batch": [{"repeat": 5, "event": FAILED}]}}
WEBSHELL = {"title": "Web shell", "id": "acme-webshell", "level": "critical", "description": "w3wp spawns cmd",
            "tags": ["attack.persistence", "attack.t1505.003"],
            "detection": {"selection": {"parent_process_name|endswith": "\\w3wp.exe",
                                        "process_name|endswith": "\\cmd.exe"}, "condition": "selection"},
            "fixtures": {"true_positive": {"parent_process_name": "c:\\w\\w3wp.exe", "process_name": "c:\\cmd.exe"},
                         "true_negative": {"parent_process_name": "c:\\explorer.exe", "process_name": "c:\\cmd.exe"}}}


def text(*rules):
    return yaml.safe_dump_all(list(rules), sort_keys=False)


def plan(*rules, existing=(), **kwargs):
    return asyncio.run(plan_sync("acme", text(*rules), list(existing), **kwargs))


def test_new_rules_pass_the_gate_and_are_planned_for_creation():
    result = plan(BASE, SPRAY, WEBSHELL)
    assert result["rejected"] == []
    assert sorted(r["id"] for r in result["create"]) == ["acme-auth-failed", "acme-spray", "acme-webshell"]
    row = next(r for r in result["create"] if r["id"] == "acme-spray")
    assert row["customer_id"] == "acme" and row["created_by"] == "git-sync"
    assert json.loads(row["rule_content"])["correlation"]["rules"] == ["acme_auth_failed"]


def test_rules_failing_the_gate_reject_the_whole_sync():
    broken = dict(WEBSHELL, fixtures={"true_positive": {"process_name": "notepad.exe"},
                                      "true_negative": WEBSHELL["fixtures"]["true_negative"]})
    result = plan(BASE, broken)
    assert result["status"] == "rejected"
    assert result["rejected"] == [{"rule": "acme-webshell", "reason": "true_positive fixture does not match"}]


def test_diff_against_the_tenants_synced_rules():
    first = plan(BASE, SPRAY, WEBSHELL)["create"]
    existing = [dict(r) for r in first]
    changed = dict(WEBSHELL, level="high")
    result = plan(BASE, changed, existing=existing, prune=True)
    assert [r["id"] for r in result["update"]] == ["acme-webshell"]
    assert [r["id"] for r in result["unchanged"]] == ["acme-auth-failed"]
    assert result["retire"] == ["acme-spray"]
    assert plan(BASE, changed, existing=existing)["retire"] == []  # only with prune


@pytest.mark.parametrize("bad, message", [
    ("title: [unclosed", "invalid YAML"),
    (text(dict(WEBSHELL, id="bad id; drop")), "invalid rule id"),
    (text(WEBSHELL, WEBSHELL), "duplicate rule id acme-webshell"),
    ("- just\n- a list\n", "not a rule"),
])
def test_malformed_input_is_an_error(bad, message):
    with pytest.raises(DetectionAsCodeError, match=message):
        asyncio.run(plan_sync("acme", bad, []))


def test_noisy_rules_are_rejected_by_the_backtest():
    async def backtest(rule_id, rules):
        return {"alerts_total": 700 if rule_id == "acme-webshell" else 0, "events_scanned": 1000}

    result = plan(BASE, SPRAY, WEBSHELL, backtest=backtest, backtest_days=7, max_alerts_per_day=50)
    assert result["status"] == "rejected"
    assert result["rejected"] == [{"rule": "acme-webshell",
                                   "reason": "backtest: 700 alerts in 7 days (100.0/day > 50/day)"}]
    assert result["backtest"]["acme-spray"]["alerts_total"] == 0
    assert "acme-auth-failed" not in result["backtest"]  # building blocks don't alert


def test_export_round_trips_unchanged():
    created = plan(BASE, SPRAY, WEBSHELL)["create"]
    exported = rules_to_yaml([rule_row_to_dict(r) for r in created])
    result = asyncio.run(plan_sync("acme", exported, created))
    assert result["rejected"] == [] and result["create"] == [] and result["update"] == []
    assert len(result["unchanged"]) == 3


def test_apply_writes_inserts_updates_and_disables():
    class DB:
        def __init__(self):
            self.statements = []

        async def execute_update(self, sql, params=None):
            self.statements.append((" ".join(sql.split()), params))
            return True

    first = plan(BASE, SPRAY, WEBSHELL)["create"]
    result = plan(BASE, dict(WEBSHELL, level="high"), existing=first, prune=True)
    db = DB()
    counts = asyncio.run(apply_sync(db, "acme", result))
    assert counts == {"created": 0, "updated": 1, "retired": 1}
    kinds = [sql.split(" (")[0].split(" WHERE")[0][:40] for sql, _ in db.statements]
    assert kinds[0].startswith("ALTER TABLE sigma_rules_mt UPDATE")
    assert db.statements[0][1]["customer_id"] == "acme"
    assert "is_enabled = 0" in db.statements[1][0] and db.statements[1][1]["ids"] == ["acme-spray"]


def test_a_rejected_plan_cannot_be_applied():
    broken = dict(WEBSHELL, level="nonsense")
    result = plan(broken)
    with pytest.raises(DetectionAsCodeError, match="rejected"):
        asyncio.run(apply_sync(object(), "acme", result))


def test_an_empty_rule_set_is_an_error():
    """With prune, an empty rule set (wrong directory, failed checkout) would
    disable every synced rule; it must fail loudly instead."""
    with pytest.raises(DetectionAsCodeError, match="the rule set is empty"):
        asyncio.run(plan_sync("acme", "\n---\n", [], prune=True))
