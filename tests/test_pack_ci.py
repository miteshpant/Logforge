"""
Pack CI (Phase 7): every pack in packages/packs is checked on every change.

* each sample line goes through the pack's own pipelines, routed as ingest
  routes it, and lands in the pipeline the sample names;
* each expectation (lines containing some text have these field values) holds
  for at least `min` events;
* each rule a sample lists matches at least one of its events;
* every rule passes the fixture gate, and every search and dashboard query
  compiles (checked when the pack loads).

The queries are also run against the parsed samples in ClickHouse
(test_pack_ci_live.py).
"""

import pytest

import pack_ci
import source_packs as sp
from test_source_packs import PACK, write


def report(tmp_path, changes=None):
    return pack_ci.check_pack(sp.load_pack(write(tmp_path / "demo", {**PACK, **(changes or {})})))


def test_a_good_pack_passes_with_its_parsed_samples(tmp_path):
    r = report(tmp_path)
    assert r.ok, r.failures
    assert r.events["samples/demo.log"][0]["attrs"]["user"] == "bob"
    assert r.checked == {"samples": 1, "events": 3, "expectations": 1, "rules": 1}


def test_an_expectation_that_does_not_hold_fails(tmp_path):
    r = report(tmp_path, {"pack.yml": PACK["pack.yml"].replace("min: 2", "min: 3")})
    assert not r.ok and "2 of 3" in r.failures[0] and "login failed" in r.failures[0]


def test_lines_routed_elsewhere_fail(tmp_path):
    r = report(tmp_path, {"pipelines/demo-app.yml": PACK["pipelines/demo-app.yml"].replace(
        "routing: {services: [demo-app]}", "routing: {services: [other-app]}")})
    assert not r.ok and any("routed to no pipeline" in f for f in r.failures)


def test_a_listed_rule_that_matches_nothing_fails(tmp_path):
    r = report(tmp_path, {"samples/demo.log": "user=amy action=login ok\nuser=bob action=login ok\nuser=x login failed\n",
                          "pack.yml": PACK["pack.yml"].replace("min: 2", "min: 1")})
    assert r.ok
    r = report(tmp_path / "b", {"samples/demo.log": "user=amy action=login ok\n",
                                "pack.yml": PACK["pack.yml"].replace("min: 2", "min: 0")})
    assert not r.ok and any("demo-login-failed matched none" in f for f in r.failures)


def test_unknown_rules_in_samples_fail(tmp_path):
    r = report(tmp_path, {"pack.yml": PACK["pack.yml"].replace("rules: [demo-login-failed]", "rules: [demo-nope]")})
    assert not r.ok and any("demo-nope is not a rule of this pack" in f for f in r.failures)


CATALOGUE, BROKEN = sp.load_catalogue()


def test_no_shipped_pack_is_broken():
    assert BROKEN == {}


@pytest.mark.parametrize("pack", CATALOGUE, ids=[p.id for p in CATALOGUE])
def test_every_shipped_pack_passes(pack):
    r = pack_ci.check_pack(pack)
    assert r.ok, r.failures
    assert pack.samples and pack.dashboards and pack.rules and pack.pipelines, "a pack needs all four"
    assert any(s.rules for s in pack.samples), "a sample should show a rule firing"


def test_the_template_is_a_working_pack(tmp_path):
    """packages/packs/_template is what contributors copy (docs/packs.md); it
    is skipped by the catalogue but must itself pass pack CI."""
    import shutil
    from pathlib import Path

    template = Path(sp.default_packs_dir()) / "_template"
    assert "_template" not in [p.id for p in CATALOGUE]
    shutil.copytree(template, tmp_path / "example")
    pack = sp.load_pack(tmp_path / "example")
    r = pack_ci.check_pack(pack)
    assert r.ok, r.failures
    assert pack.samples and pack.dashboards and pack.rules and pack.pipelines and pack.searches
