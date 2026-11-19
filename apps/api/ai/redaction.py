"""
Redaction (Phase 8): applied to everything sent to a provider (the
question and every tool result) and therefore to what the audit log keeps.

* Field names: a value is replaced when its key matches a configured name
  (case-insensitive, `-` and `_` alike, also as a suffix: `password`
  matches `db_password`), or its dotted path matches (`attrs.user_email`).
* Secret-looking values are replaced wherever they appear, including inside
  free text: `password=...`-style pairs, bearer tokens, private keys, JWTs,
  and well-known key formats (AWS, GitHub, Slack, OpenAI/Anthropic-style
  `sk-` keys).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

MASK = "[redacted]"

_PAIR = re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret)"
                   r"(\s*[=:]\s*|\s+is\s+)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)")
_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"(?i)(?<=bearer )[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
]


def _norm(name: str) -> str:
    return name.lower().replace("-", "_")


class Redactor:
    def __init__(self, fields: Iterable[str]):
        self.names: list[str] = []
        self.paths: list[str] = []
        for f in fields:
            f = _norm(str(f).strip())
            if f:
                (self.paths if "." in f else self.names).append(f)

    def _field(self, key: str, path: str) -> bool:
        k, p = _norm(key), _norm(path)
        return any(k == n or k.endswith("_" + n) or k.endswith(n) and len(n) >= 6 for n in self.names) or p in self.paths

    def _text(self, text: str) -> tuple[str, int]:
        count = 0

        def pair(m):
            nonlocal count
            count += 1
            return m.group(1) + m.group(2) + MASK

        text = _PAIR.sub(pair, text)
        for pattern in _PATTERNS:
            text, n = pattern.subn(MASK, text)
            count += n
        return text, count

    def redact(self, value: Any, path: str = "") -> tuple[Any, int]:
        if isinstance(value, dict):
            out, total = {}, 0
            for k, v in value.items():
                child = f"{path}.{k}" if path else str(k)
                if self._field(str(k), child) and v not in (None, "", [], {}):
                    out[k] = MASK
                    total += 1
                else:
                    out[k], n = self.redact(v, child)
                    total += n
            return out, total
        if isinstance(value, list):
            out, total = [], 0
            for v in value:
                v, n = self.redact(v, path)
                out.append(v)
                total += n
            return out, total
        if isinstance(value, str):
            text, n = self._text(value)
            return (MASK if n and text.strip() == MASK else text), n
        return value, 0
