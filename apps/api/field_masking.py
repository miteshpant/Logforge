"""
Field-level masking: fields a custom role hides from its holders.

The middleware applies it to every request of a user whose roles mask fields:

- JSON responses have the values of masked keys replaced with "[masked]" at any
  depth, including inside JSON-encoded strings (a log's attrs) and in tabular
  results (`columns` + `rows`).
- A request that names a masked field (in its query string or JSON body, as a
  whole word) is refused: a query could otherwise copy the value to another
  name (`| eval e = attrs.email`).
- A successful response that isn't JSON (event streams, CSV, PDF, archive
  downloads) is refused, because it can't be masked.

Names match case-insensitively on their last dotted segment, so `attrs.email`
and `email` both mask every `email` key. That over-masks rather than under.
"""

from __future__ import annotations

import contextvars
import json
import re
from typing import Any, FrozenSet, Iterable, Optional

MASK = "[masked]"
_FIELDS: contextvars.ContextVar[FrozenSet[str]] = contextvars.ContextVar("logforge_masked_fields", default=frozenset())


def normalise_fields(names: Iterable[str]) -> FrozenSet[str]:
    return frozenset(n.strip().split(".")[-1].lower() for n in names if n and n.strip())


def current() -> FrozenSet[str]:
    return _FIELDS.get()


def set_fields(fields: FrozenSet[str]) -> contextvars.Token:
    return _FIELDS.set(fields)


def reset(token: contextvars.Token) -> None:
    _FIELDS.reset(token)


def _masked_key(key: Any, fields: FrozenSet[str]) -> bool:
    return isinstance(key, str) and key.split(".")[-1].lower() in fields


def mask(value: Any, fields: FrozenSet[str]) -> Any:
    if not fields:
        return value
    if isinstance(value, dict):
        out = {k: (MASK if _masked_key(k, fields) else mask(v, fields)) for k, v in value.items()}
        columns, rows = out.get("columns"), out.get("rows")
        if isinstance(columns, list) and isinstance(rows, list):
            hidden = {i for i, c in enumerate(columns) if _masked_key(c if isinstance(c, str) else
                                                                     (c or {}).get("name"), fields)}
            if hidden:
                out["rows"] = [[MASK if i in hidden else cell for i, cell in enumerate(row)]
                               if isinstance(row, list) else row for row in rows]
        return out
    if isinstance(value, list):
        return [mask(v, fields) for v in value]
    if isinstance(value, str) and value[:1] in "{[" and len(value) < 1_000_000:
        try:
            parsed = json.loads(value)
        except ValueError:
            return value
        if isinstance(parsed, (dict, list)):
            return json.dumps(mask(parsed, fields))
    return value


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)


def mentions(value: Any, fields: FrozenSet[str]) -> Optional[str]:
    """The first masked field named (as a whole word) anywhere in `value`, if any."""
    if not fields:
        return None
    pattern = re.compile(r"(?<![\w])(" + "|".join(re.escape(f) for f in sorted(fields)) + r")(?![\w])", re.IGNORECASE)
    for text in _strings(value):
        found = pattern.search(text)
        if found:
            return found.group(1).lower()
    return None
