"""
Pack manager (Phase 7): install, upgrade and remove a pack for a tenant.

A plan shows what would change before anything does:

    create      new objects
    update      objects the pack changed that the tenant has not
    unchanged   nothing to do
    keep_local  objects the tenant changed since the install: kept as they are
    deleted     objects the tenant deleted since the install: not recreated
    conflict    an object with that name exists but this pack didn't create it
    remove      objects a newer version dropped (unless changed locally)

The manifest of an install records, for every object, the hash of the
pack's definition and the hash of what was stored, read back after writing.
A stored object whose hash differs later was changed by the tenant.
"""

import asyncio

import pytest

import pack_manager as pm


class MemoryAdapter:
    """Stores definitions as-is; `current` returns what is stored."""

    def __init__(self, kind):
        self.kind, self.store, self.writes, self.deletes = kind, {}, [], []

    async def prepare(self, tenant, pack):
        pass

    async def current(self, tenant, key, ref):
        return self.store.get((tenant, ref or key))

    async def write(self, tenant, key, definition, ref, pack):
        ref = ref or key
        self.store[(tenant, ref)] = dict(definition)
        self.writes.append(key)
        return ref

    async def delete(self, tenant, key, ref):
        self.store.pop((tenant, ref or key), None)
        self.deletes.append(key)


class FakePack:
    def __init__(self, version, objects):
        self.id, self.name, self.version, self._objects = "demo", "Demo", version, objects

    def objects(self):
        return self._objects


V1 = FakePack("1.0.0", {"pipeline:p": {"x": 1}, "rule:demo-a": {"r": 1}, "dashboard:D": {"d": 1}})
V2 = FakePack("1.1.0", {"pipeline:p": {"x": 2}, "rule:demo-a": {"r": 2}, "dashboard:D": {"d": 1},
                        "rule:demo-b": {"r": 9}})


@pytest.fixture
def adapters():
    return {kind: MemoryAdapter(kind) for kind in ("pipeline", "rule", "search", "dashboard", "lookup")}


def run(coro):
    return asyncio.run(coro)


def test_a_first_install_creates_everything(adapters):
    plan = run(pm.plan(V1, None, adapters, "acme"))
    assert plan.counts() == {"create": 3, "update": 0, "unchanged": 0, "keep_local": 0, "deleted": 0,
                             "conflict": 0, "remove": 0}
    manifest = run(pm.apply(plan, adapters, "acme"))
    assert manifest.version == "1.0.0" and set(manifest.objects) == {"pipeline:p", "rule:demo-a", "dashboard:D"}
    assert adapters["pipeline"].store[("acme", "p")] == {"x": 1}


def test_an_upgrade_updates_untouched_objects_and_keeps_local_changes(adapters):
    manifest = run(pm.apply(run(pm.plan(V1, None, adapters, "acme")), adapters, "acme"))
    adapters["rule"].store[("acme", "demo-a")] = {"r": 1, "tuned": True}   # an analyst tuned the rule
    plan = run(pm.plan(V2, manifest, adapters, "acme"))
    assert [a.key for a in plan.actions["update"]] == ["pipeline:p"]
    assert [a.key for a in plan.actions["keep_local"]] == ["rule:demo-a"]
    assert [a.key for a in plan.actions["unchanged"]] == ["dashboard:D"]
    assert [a.key for a in plan.actions["create"]] == ["rule:demo-b"]
    upgraded = run(pm.apply(plan, adapters, "acme"))
    assert adapters["rule"].store[("acme", "demo-a")] == {"r": 1, "tuned": True}
    assert adapters["pipeline"].store[("acme", "p")] == {"x": 2}
    assert upgraded.version == "1.1.0"
    # the kept object stays "changed locally" for the next upgrade too
    assert upgraded.objects["rule:demo-a"]["pack_hash"] == manifest.objects["rule:demo-a"]["pack_hash"]
    again = run(pm.plan(V2, upgraded, adapters, "acme"))
    assert [a.key for a in again.actions["keep_local"]] == ["rule:demo-a"]


def test_force_overwrites_local_changes(adapters):
    manifest = run(pm.apply(run(pm.plan(V1, None, adapters, "acme")), adapters, "acme"))
    adapters["rule"].store[("acme", "demo-a")] = {"r": "mine"}
    plan = run(pm.plan(V2, manifest, adapters, "acme", force=True))
    assert "rule:demo-a" in [a.key for a in plan.actions["update"]]


def test_deleted_objects_are_not_recreated_and_conflicts_are_left_alone(adapters):
    adapters["dashboard"].store[("acme", "D")] = {"d": "someone else's"}
    plan = run(pm.plan(V1, None, adapters, "acme"))
    assert [a.key for a in plan.actions["conflict"]] == ["dashboard:D"]
    manifest = run(pm.apply(plan, adapters, "acme"))
    assert adapters["dashboard"].store[("acme", "D")] == {"d": "someone else's"}
    assert "dashboard:D" not in manifest.objects
    adapters["pipeline"].store.pop(("acme", "p"))  # the tenant deleted the pipeline
    plan = run(pm.plan(V2, manifest, adapters, "acme"))
    assert [a.key for a in plan.actions["deleted"]] == ["pipeline:p"]


def test_objects_a_new_version_drops_are_removed(adapters):
    manifest = run(pm.apply(run(pm.plan(V2, None, adapters, "acme")), adapters, "acme"))
    plan = run(pm.plan(V1, manifest, adapters, "acme"))   # 1.0.0 has no demo-b
    assert [a.key for a in plan.actions["remove"]] == ["rule:demo-b"]
    run(pm.apply(plan, adapters, "acme"))
    assert ("acme", "demo-b") not in adapters["rule"].store


def test_removing_a_pack_keeps_what_the_tenant_changed(adapters):
    manifest = run(pm.apply(run(pm.plan(V1, None, adapters, "acme")), adapters, "acme"))
    adapters["dashboard"].store[("acme", "D")] = {"d": "edited"}
    result = run(pm.uninstall(manifest, adapters, "acme"))
    assert result == {"removed": ["pipeline:p", "rule:demo-a"], "kept": ["dashboard:D"]}
    assert ("acme", "D") in adapters["dashboard"].store and ("acme", "p") not in adapters["pipeline"].store


def test_plans_are_reported_with_reasons(adapters):
    plan = run(pm.plan(V1, None, adapters, "acme"))
    public = plan.to_public()
    assert public["pack"] == "demo" and public["from_version"] is None and public["to_version"] == "1.0.0"
    assert public["actions"]["create"][0] == {"key": "pipeline:p", "kind": "pipeline", "name": "p",
                                              "reason": "new in 1.0.0"}
