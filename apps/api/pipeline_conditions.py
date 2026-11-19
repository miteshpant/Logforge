"""
Sandboxed expressions for ingest pipelines (Phase 4): processor `if:`
conditions and the `script` processor.

Expressions are parsed with `ast` and evaluated by a tree walker that only
knows a whitelist of node types. Nothing is ever passed to eval/exec, names
resolve to document fields (never Python objects), and the only callables
are the functions in FUNCTIONS. Validation happens at compile time, so a bad
expression is rejected when the pipeline is saved, not on the hot path.

Field paths are dotted names (`attrs.user`; a number picks a list element,
`attrs.target.0.id`); a missing field is None. Names
that aren't identifiers use field("attrs.x-forwarded-for").
"""

from __future__ import annotations

import ast
import ipaddress
import operator
import re
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional

MAX_SOURCE = 2000
MAX_NODES = 400
MAX_VALUE = 100_000  # longest string/list an expression may build


class ConditionError(ValueError):
    pass


_MISSING = object()


# -- document paths -----------------------------------------------------------

def get_path(doc: Dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = doc
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return default
    return current


def set_path(doc: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = doc
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            current[part] = nxt
        current = nxt
    current[parts[-1]] = value


def delete_path(doc: Dict[str, Any], path: str) -> bool:
    parts = path.split(".")
    current: Any = doc
    for part in parts[:-1]:
        current = current.get(part) if isinstance(current, dict) else None
        if current is None:
            return False
    if isinstance(current, dict) and parts[-1] in current:
        del current[parts[-1]]
        return True
    return False


# -- functions ----------------------------------------------------------------

@lru_cache(maxsize=512)
def _regex(pattern: str) -> "re.Pattern[str]":
    try:
        return re.compile(pattern)
    except re.error as e:
        raise ConditionError(f"bad regular expression {pattern!r}: {e}") from None


@lru_cache(maxsize=256)
def _network(cidr: str):
    try:
        return ipaddress.ip_network(cidr, strict=False)
    except ValueError as e:
        raise ConditionError(f"bad network {cidr!r}: {e}") from None


def _cidr(value: Any, *networks: str) -> bool:
    try:
        address = ipaddress.ip_address(str(value).strip())
    except ValueError:
        return False
    return any(address in _network(n) for n in networks)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _len(value: Any) -> int:
    try:
        return len(value)
    except TypeError:
        return 0


FUNCTIONS: Dict[str, Callable[..., Any]] = {
    "contains": lambda value, part: part in value if isinstance(value, (list, dict)) else _text(part) in _text(value),
    "startswith": lambda value, prefix: _text(value).startswith(_text(prefix)),
    "endswith": lambda value, suffix: _text(value).endswith(_text(suffix)),
    "matches": lambda value, pattern: _regex(_text(pattern)).search(_text(value)) is not None,
    "lower": lambda value: _text(value).lower(),
    "upper": lambda value: _text(value).upper(),
    "len": _len,
    "int": lambda value: int(float(value)) if isinstance(value, str) and "." in value else int(value),
    "float": float,
    "str": _text,
    "cidr": _cidr,
}
_DOC_FUNCTIONS = {"field", "exists"}  # take a path string and read the document

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Mod: operator.mod}
_COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
            ast.Gt: operator.gt, ast.GtE: operator.ge}


# -- compilation --------------------------------------------------------------

def _path_of(node: ast.AST) -> Optional[str]:
    """`attrs.user` -> "attrs.user"; None if the node is not a plain path."""
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        path = ".".join(reversed(parts))
        if "__" in path:
            raise ConditionError("names with __ are not allowed")
        return path
    return None


def _check(node: ast.AST) -> None:
    """Reject anything outside the whitelist."""
    count = sum(1 for _ in ast.walk(node))
    if count > MAX_NODES:
        raise ConditionError("expression is too complex")
    for child in ast.walk(node):
        if isinstance(child, (ast.Expression, ast.Load, ast.Store, ast.Del, ast.And, ast.Or, ast.Not, ast.USub,
                              ast.UAdd, ast.In, ast.NotIn, ast.Constant, ast.List, ast.Tuple, ast.BoolOp,
                              ast.UnaryOp, ast.Compare, ast.IfExp, ast.Name, ast.Attribute)):
            continue
        if isinstance(child, tuple(_COMPARE)) or isinstance(child, tuple(_BINARY)):
            continue
        if isinstance(child, ast.BinOp):
            if type(child.op) not in _BINARY:
                raise ConditionError(f"operator {type(child.op).__name__} is not allowed")
            continue
        if isinstance(child, ast.Call):
            name = child.func.id if isinstance(child.func, ast.Name) else None
            if name not in FUNCTIONS and name not in _DOC_FUNCTIONS:
                raise ConditionError("only these functions can be called: "
                                     + ", ".join(sorted(set(FUNCTIONS) | _DOC_FUNCTIONS)))
            if child.keywords:
                raise ConditionError("keyword arguments are not allowed")
            if name in _DOC_FUNCTIONS and not (len(child.args) == 1 and isinstance(child.args[0], ast.Constant)
                                               and isinstance(child.args[0].value, str)):
                raise ConditionError(f"{name}() takes one field path string")
            continue
        raise ConditionError(f"{type(child).__name__} is not allowed in expressions")
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            if _path_of(child) is None:
                raise ConditionError("attributes can only be used in field paths (attrs.user)")
        if isinstance(child, ast.Name) and child.id.startswith("__"):
            raise ConditionError("names with __ are not allowed")


def _bounded(value: Any) -> Any:
    if isinstance(value, (str, list, tuple)) and len(value) > MAX_VALUE:
        raise ConditionError("value too large")
    return value


def _evaluate(node: ast.AST, doc: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Name, ast.Attribute)):
        return get_path(doc, _path_of(node))
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_evaluate(e, doc) for e in node.elts]
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: Any = True
            for value in node.values:
                result = _evaluate(value, doc)
                if not result:
                    return result
            return result
        for value in node.values:
            result = _evaluate(value, doc)
            if result:
                return result
        return result
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, doc)
        if isinstance(node.op, ast.Not):
            return not value
        try:
            return -value if isinstance(node.op, ast.USub) else +value
        except TypeError:
            return None
    if isinstance(node, ast.BinOp):
        left, right = _evaluate(node.left, doc), _evaluate(node.right, doc)
        if isinstance(node.op, ast.Mult) and isinstance(left, (str, list)) and isinstance(right, int) \
                and len(left) * right > MAX_VALUE:
            raise ConditionError("value too large")
        try:
            return _bounded(_BINARY[type(node.op)](left, right))
        except (TypeError, ZeroDivisionError, ValueError):
            return None
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, doc)
        for op, comparator in zip(node.ops, node.comparators):
            right = _evaluate(comparator, doc)
            try:
                if isinstance(op, ast.In):
                    ok = left in right if right is not None else False
                elif isinstance(op, ast.NotIn):
                    ok = left not in right if right is not None else True
                else:
                    ok = _COMPARE[type(op)](left, right)
            except TypeError:
                ok = False
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _evaluate(node.body if _evaluate(node.test, doc) else node.orelse, doc)
    if isinstance(node, ast.Call):
        name = node.func.id
        if name == "field":
            return get_path(doc, node.args[0].value)
        if name == "exists":
            return get_path(doc, node.args[0].value, _MISSING) is not _MISSING
        args = [_evaluate(a, doc) for a in node.args]
        try:
            return _bounded(FUNCTIONS[name](*args))
        except ConditionError:
            raise
        except (TypeError, ValueError, OverflowError):
            return None
    raise ConditionError(f"{type(node).__name__} is not allowed")  # unreachable after _check


def _parse(source: str, mode: str) -> ast.AST:
    if not isinstance(source, str) or not source.strip():
        raise ConditionError("expression is empty")
    if len(source) > MAX_SOURCE:
        raise ConditionError(f"expression is too long (max {MAX_SOURCE} characters)")
    try:
        return ast.parse(source.strip(), mode=mode)
    except SyntaxError as e:
        raise ConditionError(f"syntax error: {e.msg}") from None


@lru_cache(maxsize=1024)
def compile_condition(source: str) -> Callable[[Dict[str, Any]], bool]:
    tree = _parse(source, "eval")
    _check(tree)
    body = tree.body

    def run(doc: Dict[str, Any]) -> bool:
        return bool(_evaluate(body, doc))

    return run


@lru_cache(maxsize=512)
def compile_script(source: str) -> Callable[[Dict[str, Any]], None]:
    """Statements: `path = expression` and `del path`, separated by ; or newlines."""
    tree = _parse(source, "exec")
    steps: List[tuple] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            path = _path_of(statement.targets[0])
            if path is None:
                raise ConditionError("scripts can only assign to field paths (attrs.x = ...)")
            expression = ast.Expression(statement.value)
            _check(expression)
            steps.append(("set", path, expression.body))
        elif isinstance(statement, ast.Delete):
            for target in statement.targets:
                path = _path_of(target)
                if path is None:
                    raise ConditionError("del takes field paths")
                steps.append(("del", path, None))
        else:
            raise ConditionError(f"{type(statement).__name__} is not allowed in scripts "
                                 "(only assignments and del)")
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES * 2:
        raise ConditionError("script is too complex")

    def run(doc: Dict[str, Any]) -> None:
        for kind, path, expression in steps:
            if kind == "set":
                set_path(doc, path, _evaluate(expression, doc))
            else:
                delete_path(doc, path)

    return run
