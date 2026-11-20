"""
Pipeline condition and script language (Phase 4).

A small, sandboxed expression language for processor `if:` conditions and
the `script` processor. It is parsed with Python's `ast` and evaluated by
walking a whitelist of node types, never with eval/exec:

* field paths: `service`, `attrs.user`, `field("attrs.x-forwarded-for")`;
  a missing field is None, never an error;
* literals, lists, comparisons (== != < <= > >= in, not in), and/or/not,
  arithmetic (+ - * / %) and string concatenation;
* a fixed set of functions: contains, startswith, endswith, matches,
  exists, lower, upper, len, int, float, str, cidr;
* scripts: `;`- or newline-separated assignments to field paths and
  `del path`.

Anything else (attribute access on values, subscripts of arbitrary objects,
calls to unknown names, lambdas, comprehensions, imports, dunder names) is
rejected when the pipeline is saved. Size and string-growth limits stop
expensive expressions.
"""

import pytest

from pipeline_conditions import ConditionError, compile_condition, compile_script

DOC = {"service": "nginx", "level": "warn", "msg": "GET /login 401", "status": 401, "src_ip": "10.1.2.3",
       "attrs": {"user": "Alice", "tags": ["edge", "eu"], "bytes": 512, "x-forwarded-for": "203.0.113.9"}}


@pytest.mark.parametrize("expression, expected", [
    ('service == "nginx"', True),
    ('service == "nginx" and status >= 400', True),
    ('status in [200, 204]', False),
    ('not (level == "info")', True),
    ('attrs.user == "Alice"', True),
    ('lower(attrs.user) == "alice"', True),
    ('"eu" in attrs.tags', True),
    ('attrs.missing == None', True),
    ('exists("attrs.user") and not exists("attrs.nope")', True),
    ('contains(msg, "/login")', True),
    ('startswith(msg, "GET") and endswith(msg, "401")', True),
    ('matches(msg, "^GET /\\\\w+ 4\\\\d\\\\d$")', True),
    ('attrs.bytes * 2 > 1000', True),
    ('len(attrs.tags) == 2', True),
    ('cidr(src_ip, "10.0.0.0/8")', True),
    ('cidr(src_ip, "192.168.0.0/16")', False),
    ('field("attrs.x-forwarded-for") == "203.0.113.9"', True),
    ('attrs.missing > 3', False),  # comparing None never raises
    ('int("42") + 1 == 43', True),
])
def test_conditions(expression, expected):
    assert compile_condition(expression)(DOC) is expected


@pytest.mark.parametrize("expression", [
    "__import__('os').system('id')",
    "attrs.user.upper()",
    "open('/etc/passwd')",
    "[x for x in attrs.tags]",
    "lambda: 1",
    "service.__class__",
    "msg[0]",
    "2 ** 1000000",
    "eval('1')",
    "x := 1",
])
def test_unsafe_or_unsupported_expressions_are_rejected(expression):
    with pytest.raises(ConditionError):
        compile_condition(expression)


def test_expression_size_is_limited():
    with pytest.raises(ConditionError, match="too long"):
        compile_condition(" or ".join(['service == "x"'] * 500))


def test_string_growth_is_limited_at_run_time():
    run = compile_condition('len(msg * 1000000) > 0')
    with pytest.raises(ConditionError, match="too large"):
        run(DOC)


def test_scripts_assign_and_delete_fields():
    doc = {"msg": "x", "status": 503, "attrs": {"bytes": "2048", "secret": "s"}}
    compile_script('attrs.kb = int(attrs.bytes) / 1024; attrs.category = "server_error"\n'
                   'level = "error"\ndel attrs.secret')(doc)
    assert doc["attrs"] == {"bytes": "2048", "kb": 2.0, "category": "server_error"}
    assert doc["level"] == "error"


def test_scripts_reject_anything_but_assignments():
    for source in ["import os", "while True: pass", "attrs.x = 1; print(1)", "def f(): pass", "attrs[0] = 1"]:
        with pytest.raises(ConditionError):
            compile_script(source)


def test_numeric_path_parts_index_lists():
    """JSON sources nest values in lists (Okta targets, Workspace parameters):
    a numeric part of a path reads that element; a missing one is None."""
    from pipeline_conditions import get_path

    doc = {"attrs": {"target": [{"id": "u1", "type": "User"}, {"id": "g1", "type": "Group"}]}}
    assert get_path(doc, "attrs.target.0.id") == "u1"
    assert get_path(doc, "attrs.target.1.type") == "Group"
    assert get_path(doc, "attrs.target.2.id") is None and get_path(doc, "attrs.target.x") is None
    assert compile_condition('field("attrs.target.1.type") == "Group"')(doc)
    assert compile_condition('exists("attrs.target.0.id") and not exists("attrs.target.5")')(doc)
