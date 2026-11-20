"""
Log pattern clustering (Phase 11): Drain-style templates, new and rare
patterns against a baseline, and the speed target (1 M lines < 30 s is
measured by tests/bench/patterns_bench.py; here a smaller smoke check).
"""

import random
import time
from datetime import datetime, timedelta, timezone

from log_patterns import Clusterer, mask

T = datetime(2026, 11, 20, tzinfo=timezone.utc)


def test_masking_variables():
    assert mask("Failed password for root from 203.0.113.5 port 40112 ssh2") == \
        "Failed password for root from <*> port <*> ssh2"
    assert mask("request 6f1c2b8e-3a4d-4e5f-8a9b-0c1d2e3f4a5b took 312ms status=500") == \
        "request <*> took <*> status=<*>"
    assert mask("ptr 0x7ffde4a0 h2 v1.2.3") == "ptr <*> h2 <*>"


def test_lines_group_into_templates():
    c = Clusterer()
    for i in range(50):
        c.add(f"Failed password for {random.choice(['root', 'admin', 'bob'])} from 10.0.0.{i} port {4000 + i} ssh2",
              T + timedelta(seconds=i), "sshd")
        c.add(f"GET /api/orders/{i} 200 {i * 3}ms", T, "nginx")
    c.add("kernel: Out of memory: Killed process 4242 (java)", T + timedelta(hours=1), "kernel")
    rows = c.results()
    assert [r["pattern"] for r in rows[:2]] == ["Failed password for <*> from <*> port <*> ssh2",
                                                "GET /api/orders/<*> <*> <*>"]
    assert rows[0]["count"] == 50 and rows[0]["services"] == "sshd" and rows[0]["example"].startswith("Failed")
    assert len(rows) == 3 and rows[2]["rare"] == 1


def test_new_patterns_are_the_ones_the_baseline_never_had():
    c = Clusterer()
    c.baseline([f"user {u} logged in from 10.0.0.{i}" for i, u in enumerate(["a", "b", "c"] * 20)])
    for i in range(30):
        c.add(f"user x logged in from 10.0.0.{i}", T)
    c.add("panic: runtime error: index out of range [3] with length 3", T + timedelta(minutes=5), "checkout")
    new = c.results("new", with_baseline=True)
    assert [r["pattern"] for r in new] == ["panic: runtime error: index out of range [<*>] with length <*>"]
    assert c.results("all", with_baseline=True)[0]["new"] == 0


def test_speed_smoke():
    r = random.Random(1)
    verbs = ["GET", "POST", "PUT"]
    lines = [f"{r.choice(verbs)} /api/{r.choice(['orders', 'users', 'carts'])}/{r.randint(1, 10**6)} "
             f"{r.choice([200, 201, 404, 500])} {r.randint(1, 900)}ms" for _ in range(100_000)]
    c = Clusterer()
    began = time.perf_counter()
    for line in lines:
        c.add(line)
    took = time.perf_counter() - began
    assert len(c.results()) <= 30 and took < 6.0, took


def test_the_patterns_stage():
    import pytest
    from pattern_query import PatternQueryError, lines_query, split

    assert split('"timeout" | patterns') == ('"timeout"', "all")
    assert split('| where level = "error" | patterns new') == ('| where level = "error"', "new")
    assert split("| patterns rare") == ("*", "rare")
    assert split('"| patterns" | stats count()') is None and split("error") is None
    for bad in ("| patterns everything", "| patterns new now", "| patterns | stats count()"):
        with pytest.raises(PatternQueryError):
            split(bad)
    assert lines_query("*", 10) == "* | fields ts, service, msg | head 10"


def test_the_lines_query_compiles():
    from ai.nl2query import compile_error
    from pattern_query import lines_query

    for base in ("*", '| where service = "checkout"', '| where level = "error"', '"timeout"'):
        assert compile_error(lines_query(base, 1000)) is None, base
