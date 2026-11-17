"""
Startup reconciles the default rule library with what ships, not just inserts.

The loader only inserted rules whose id was missing, so a fixed or retuned
packaged rule never reached an existing install (the stored copy won
forever), and a rule removed from the package, or one that no longer passes
the fixture gate, stayed enabled.

Now: missing rules are inserted, rules whose content changed are updated in
place, and system rules that are no longer shipped are disabled.
"""

import asyncio

import pytest

from mitre_default_loader import MitreDefaultLoader


class _FakeDB:
    def __init__(self, existing):
        self.existing = existing
        self.updates = []

    async def execute_query(self, sql, params=None):
        return self.existing

    async def execute_update(self, sql, params=None):
        self.updates.append((" ".join(sql.split()), params))
        return True


def row(rid, content="{}", severity="high", enabled=True, name="n"):
    return {"id": rid, "customer_id": "default", "name": name, "description": "", "rule_content": content,
            "mitre_techniques": ["T1110"], "severity": severity, "is_enabled": enabled, "created_by": "system"}


def stored(rid, content="{}", severity="high", enabled=1, name="n"):
    return {"id": rid, "rule_content": content, "severity": severity, "is_enabled": enabled, "name": name,
            "description": "", "mitre_techniques": ["T1110"]}


@pytest.fixture
def make_loader():
    def make(existing):
        instance = MitreDefaultLoader.__new__(MitreDefaultLoader)
        instance._condition_evaluator = None
        instance.database = _FakeDB(existing)
        return instance
    return make


def reconcile(loader, rows):
    return asyncio.run(loader._reconcile_default_rules(rows))


def test_missing_rules_are_inserted_unchanged_ones_left_alone(make_loader):
    loader = make_loader([stored("a")])
    result = reconcile(loader, [row("a"), row("b")])
    assert (result["inserted"], result["updated"], result["unchanged"]) == (1, 0, 1)
    assert [u[0].split(" (")[0] for u in loader.database.updates] == ["INSERT INTO sigma_rules_mt"]


def test_changed_rules_are_updated_in_place(make_loader):
    loader = make_loader([stored("a", content='{"old": 1}')])
    result = reconcile(loader, [row("a", content='{"new": 1}')])
    assert result["updated"] == 1
    sql, params = loader.database.updates[0]
    assert sql.startswith("ALTER TABLE sigma_rules_mt UPDATE")
    assert "WHERE customer_id = %(customer_id)s AND id = %(id)s" in sql
    assert "mutations_sync = 2" in sql
    assert params["rule_content"] == '{"new": 1}' and params["id"] == "a"


def test_severity_or_name_changes_count_as_changes(make_loader):
    loader = make_loader([stored("a", severity="low"), stored("b", name="old")])
    assert reconcile(loader, [row("a"), row("b")])["updated"] == 2


def test_disabled_shipped_rules_are_re_enabled(make_loader):
    loader = make_loader([stored("a", enabled=0)])
    assert reconcile(loader, [row("a")])["updated"] == 1


def test_rules_no_longer_shipped_are_disabled(make_loader):
    loader = make_loader([stored("a"), stored("gone"), stored("already-off", enabled=0)])
    result = reconcile(loader, [row("a")])
    assert result["retired"] == 1
    sql, params = loader.database.updates[0]
    assert sql.startswith("ALTER TABLE sigma_rules_mt UPDATE is_enabled = 0")
    assert params["ids"] == ["gone"]


def test_nothing_is_retired_when_nothing_was_built(make_loader):
    loader = make_loader([stored("a")])
    assert reconcile(loader, [])["retired"] == 0
    assert loader.database.updates == []
