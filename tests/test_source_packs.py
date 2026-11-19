"""
Source packs (Phase 7): one directory that makes a data source useful.

    packages/packs/<id>/
      pack.yml          id, name, version, description, sources, samples
      pipelines/*.yml   ingest pipelines (Phase 4) with routing; the schema
                        mapping (Phase 5) is part of the pipeline
      rules/*.yml       detection rules with fixtures (Phase 1), ids <id>-*
      searches/*.yml    saved searches and alert templates (Phase 6)
      dashboards/*.yml  dashboards of LogforgeQL panels with variables
      lookups/*.csv     lookup tables
      samples/*         sample logs, with expectations in pack.yml

Every part is validated with the same code that installs it, so a pack
that loads is one that can be installed.
"""

import textwrap
from pathlib import Path

import pytest

import source_packs as sp
from source_packs import PackError


def write(root: Path, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip())
    return root


PACK = {
    "pack.yml": """
        id: demo
        name: Demo source
        version: 1.2.0
        description: A demo pack.
        sources:
          - name: demo app
            service: demo-app
            paths: [/var/log/demo.log]
        samples:
          - file: samples/demo.log
            service: demo-app
            pipeline: demo-app
            expect:
              - contains: "login failed"
                fields: {attrs.outcome: failure}
                min: 2
            rules: [demo-login-failed]
    """,
    "pipelines/demo-app.yml": """
        name: demo-app
        description: Parse demo lines
        routing: {services: [demo-app]}
        processors:
          - kv: {field: msg, target: attrs}
          - set: {field: attrs.outcome, value: failure}
            if: "contains(msg, 'login failed')"
    """,
    "rules/auth.yml": """
        title: Demo failed login
        id: demo-login-failed
        status: stable
        description: A failed login in the demo app.
        tags: [attack.credential_access, attack.t1110]
        logsource: {product: demo}
        detection:
          selection: {outcome: failure}
          condition: selection
        fixtures:
          true_positive: {outcome: failure, user: bob}
          true_negative: {outcome: success, user: bob}
        level: low
    """,
    "searches/failures.yml": """
        name: Demo failures per user
        query: '| where attrs.outcome = "failure" | stats count() as n by attrs.user | where n > 5'
        every: 15m
        window: 1h
        enabled: false
        alert: {condition: {kind: rows, op: gt, value: 0}, severity: medium}
    """,
    "dashboards/overview.yml": """
        name: Demo overview
        description: Demo app activity
        variables:
          - {name: user, type: text, default: ""}
        panels:
          - {name: Events, type: metric, query: "| where service = \\"demo-app\\" | stats count() as events"}
          - {name: Failures over time, type: line_chart, size: {w: 2, h: 2},
             query: '| where attrs.outcome = "failure" | timechart count()'}
    """,
    "lookups/demo_users.csv": "user,team\nbob,eng\n",
    "samples/demo.log": "user=bob action=login failed\nuser=amy action=login ok\nuser=bob action=login failed\n",
}


@pytest.fixture
def pack_dir(tmp_path):
    return write(tmp_path / "demo", PACK)


def test_a_pack_loads_with_all_its_parts(pack_dir):
    pack = sp.load_pack(pack_dir)
    assert (pack.id, pack.name, pack.version) == ("demo", "Demo source", "1.2.0")
    assert [p.id for p in pack.pipelines] == ["demo-app"] and pack.pipelines[0].routing["services"] == ["demo-app"]
    assert [r["id"] for r in pack.rules] == ["demo-login-failed"]
    assert [s.id for s in pack.searches] == ["demo_failures_per_user"] and pack.searches[0].enabled is False
    assert pack.dashboards[0]["name"] == "Demo overview" and len(pack.dashboards[0]["panels"]) == 2
    assert pack.dashboards[0]["variables"][0]["name"] == "user"
    assert list(pack.lookups) == ["demo_users"] and pack.lookups["demo_users"]["rows"] == {"bob": {"team": "eng"}}
    assert pack.samples[0].lines == ["user=bob action=login failed", "user=amy action=login ok",
                                     "user=bob action=login failed"]
    summary = pack.summary()
    assert summary["contents"] == {"pipelines": 1, "rules": 1, "searches": 1, "dashboards": 1, "lookups": 1}


@pytest.mark.parametrize("change, message", [
    ({"pack.yml": "id: Bad Id\nname: x\nversion: 1.0.0\n"}, "id"),
    ({"pack.yml": "id: demo\nname: x\nversion: one\n"}, "version"),
    ({"pack.yml": "id: other\nname: x\nversion: 1.0.0\n"}, "directory"),
    ({"pipelines/demo-app.yml": "name: demo-app\nprocessors: [{nonsense: {}}]\n"}, "pipelines/demo-app.yml"),
    ({"rules/auth.yml": "title: x\nid: wrong-prefix\ndetection: {s: {a: 1}, condition: s}\nlevel: low\n"},
     "start with demo-"),
    ({"searches/failures.yml": "name: x\nquery: '| frobnicate'\n"}, "searches/failures.yml"),
    ({"dashboards/overview.yml": "name: x\npanels: [{name: p, type: sparkle, query: '| head 1'}]\n"}, "type"),
    ({"dashboards/overview.yml": "name: x\npanels: [{name: p, type: table, query: '| where $nope = 1'}]\n"},
     "Unknown variable"),
    ({"lookups/demo_users.csv": "a,a\n1,2\n"}, "lookups/demo_users.csv"),
])
def test_invalid_packs_are_explained(tmp_path, change, message):
    files = {**PACK, **change}
    if "version: one" in change.get("pack.yml", "") or "Bad Id" in change.get("pack.yml", "") \
            or "id: other" in change.get("pack.yml", ""):
        files = {**change, "samples/demo.log": PACK["samples/demo.log"]}
    with pytest.raises(PackError, match=message):
        sp.load_pack(write(tmp_path / "demo", files))


def test_sample_files_must_exist(tmp_path):
    files = {**PACK, "pack.yml": PACK["pack.yml"].replace("samples/demo.log", "samples/missing.log")}
    with pytest.raises(PackError, match="missing.log"):
        sp.load_pack(write(tmp_path / "demo", files))


def test_the_catalogue_lists_every_pack_and_reports_broken_ones(tmp_path):
    write(tmp_path / "demo", PACK)
    write(tmp_path / "broken", {"pack.yml": "id: broken\nname: x\nversion: nope\n"})
    write(tmp_path / "_template", {"pack.yml": "id: _template\n"})  # underscore dirs are not packs
    packs, errors = sp.load_catalogue(tmp_path)
    assert [p.id for p in packs] == ["demo"]
    assert list(errors) == ["broken"] and "version" in errors["broken"]


def test_content_hashes_are_stable_and_change_with_content(pack_dir):
    a = sp.load_pack(pack_dir)
    b = sp.load_pack(pack_dir)
    assert a.object_hashes() == b.object_hashes()
    assert set(a.object_hashes()) == {"pipeline:demo-app", "rule:demo-login-failed", "search:demo_failures_per_user",
                                      "dashboard:Demo overview", "lookup:demo_users"}
    (pack_dir / "pipelines/demo-app.yml").write_text(
        (pack_dir / "pipelines/demo-app.yml").read_text().replace("Parse demo lines", "Parse demo lines v2"))
    c = sp.load_pack(pack_dir)
    changed = {k for k in a.object_hashes() if a.object_hashes()[k] != c.object_hashes()[k]}
    assert changed == {"pipeline:demo-app"}
