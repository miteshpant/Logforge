"""ALTER TABLE ... UPDATE/DELETE must not call now()/now64()/today(): on replicated
tables each replica would evaluate it at a different moment, which ClickHouse
refuses unless allow_nondeterministic_mutations is on. The time is bound as a
parameter instead, and the HA profile no longer turns the setting on."""
import ast
import pathlib
import re

API = pathlib.Path(__file__).resolve().parent.parent / "apps" / "api"
NOW = re.compile(r"\b(now64|now|today)\(")


def _strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def test_no_mutation_calls_now():
    found = []
    for path in API.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and n.body and isinstance(n.body[0], ast.Expr)}
        for node in ast.walk(tree):
            if id(node) in docstrings:
                continue
            text = _strings(node)
            if text is None:
                continue
            upper = text.upper()
            is_mutation = "ALTER TABLE" in upper and (" UPDATE" in upper or " DELETE" in upper)
            is_fragment = re.search(r"\w+\s*=\s*(now64|now|today)\(", text) and "SELECT" not in upper \
                and "INSERT" not in upper and "DEFAULT" not in upper
            if (is_mutation and NOW.search(text)) or is_fragment:
                found.append(f"{path.relative_to(API)}:{node.lineno}")
    assert found == []


def test_ha_profile_does_not_allow_nondeterministic_mutations():
    profile = (API.parent.parent / "infra" / "docker" / "ha" / "profile.xml").read_text()
    assert "allow_nondeterministic_mutations" not in profile
