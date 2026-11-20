"""
Templates for action fields (Phase 13): `{{ path }}` placeholders filled from
the alert, case or run context, with a few filters. Deliberately not a
template engine: no expressions, no attribute access beyond dict keys and
list indexes, nothing that reaches Python objects.

    "[{{ alert.severity | upper }}] {{ alert.title }}"
    "{{ alert.entities.src_ip.0 }}"          list index
    "{{ case.owner | default('nobody') }}"
    "{{ alert.entities | json }}"
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

_PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")
_PATH = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)*$")
_DEFAULT = re.compile(r"^default\(\s*'([^']*)'\s*\)$")
FILTERS = ("upper", "lower", "json", "default('…')", "truncate(n)")
_TRUNCATE = re.compile(r"^truncate\(\s*(\d{1,5})\s*\)$")
_MISSING = object()


class TemplateError(ValueError):
    pass


def _lookup(path: str, ctx: Mapping[str, Any]) -> Any:
    if not _PATH.match(path) or any(part.startswith("_") for part in path.split(".")):
        raise TemplateError(f"not a field path: {path!r}")
    value: Any = ctx
    for part in path.split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        elif isinstance(value, (list, tuple)) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return _MISSING
    return value


def _text(value: Any) -> str:
    if value is _MISSING or value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def _expr(expr: str, ctx: Mapping[str, Any]) -> str:
    parts = [p.strip() for p in expr.split("|")]
    value = _lookup(parts[0], ctx)
    for f in parts[1:]:
        if f == "upper":
            value = _text(value).upper()
        elif f == "lower":
            value = _text(value).lower()
        elif f == "json":
            value = json.dumps(None if value is _MISSING else value, default=str)
        elif _DEFAULT.match(f):
            if value is _MISSING or value in (None, ""):
                value = _DEFAULT.match(f).group(1)
        elif _TRUNCATE.match(f):
            n = int(_TRUNCATE.match(f).group(1))
            text = _text(value)
            value = text if len(text) <= n else text[: max(0, n - 1)] + "…"
        else:
            raise TemplateError(f"unknown filter {f!r} (filters: {', '.join(FILTERS)})")
    return _text(value)


def render(template: str, ctx: Mapping[str, Any]) -> str:
    if not isinstance(template, str):
        return template
    return _PLACEHOLDER.sub(lambda m: _expr(m.group(1).strip(), ctx), template)


def render_tree(value: Any, ctx: Mapping[str, Any]) -> Any:
    """Render every string in a JSON-like structure."""
    if isinstance(value, str):
        return render(value, ctx)
    if isinstance(value, list):
        return [render_tree(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: render_tree(v, ctx) for k, v in value.items()}
    return value


def check(template: Any) -> None:
    """Raise TemplateError if any placeholder is malformed (checked when saved)."""
    if isinstance(template, str):
        for m in _PLACEHOLDER.finditer(template):
            _expr(m.group(1).strip(), {})
    elif isinstance(template, list):
        for v in template:
            check(v)
    elif isinstance(template, dict):
        for v in template.values():
            check(v)
