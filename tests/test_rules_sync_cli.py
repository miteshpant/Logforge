"""
scripts/rules_sync.py: sync a detection repository with Logforge from CI.

It concatenates every *.yml / *.yaml under the rules directory (sorted, as
YAML documents), posts them to /v1/security/rules/sync, prints the plan and
exits 0 when the sync is accepted, 1 when rules are rejected, 2 on errors.
Dry run unless --apply.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rules_sync.py"
spec = importlib.util.spec_from_file_location("rules_sync", SCRIPT)
rules_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules_sync)


def test_collects_rule_files_recursively_in_order(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "two.yaml").write_text("id: two\n")
    (tmp_path / "a.yml").write_text("id: one\n---\nid: one-b\n")
    (tmp_path / "notes.md").write_text("ignored")
    text = rules_sync.collect_rule_set(tmp_path)
    assert text == "id: one\n---\nid: one-b\n\n---\nid: two\n"


def test_empty_directory_is_an_error(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        rules_sync.collect_rule_set(tmp_path)
    assert exit_info.value.code == 2


@pytest.mark.parametrize("status, plan, code", [
    (200, {"status": "ok", "create": ["r"], "update": [], "unchanged": [], "retire": [], "rejected": [],
           "applied": None, "backtest": {}}, 0),
    (200, {"status": "rejected", "create": [], "update": [], "unchanged": [], "retire": [],
           "rejected": [{"rule": "r", "reason": "true_positive fixture does not match"}], "applied": None,
           "backtest": {}}, 1),
    (400, {"detail": "invalid YAML"}, 2),
])
def test_exit_codes(tmp_path, capsys, status, plan, code):
    (tmp_path / "r.yml").write_text("id: r\n")
    sent = {}

    def post(url, body, headers):
        sent.update(url=url, body=body, headers=headers)
        return status, plan

    assert rules_sync.main(["--api", "http://lf:7080", "--tenant", "acme", "--token", "t", "--dir", str(tmp_path),
                            "--apply", "--backtest-days", "7"], post=post) == code
    assert sent["url"] == "http://lf:7080/v1/security/rules/sync"
    assert sent["body"]["dry_run"] is False and sent["body"]["backtest_days"] == 7
    assert sent["headers"]["X-Customer-ID"] == "acme" and sent["headers"]["Authorization"] == "Bearer t"
    out = capsys.readouterr().out
    assert ("rejected" in out) == (code == 1)
