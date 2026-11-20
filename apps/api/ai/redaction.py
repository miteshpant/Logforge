"""
Redaction (Phase 8): applied to everything sent to a provider (the
question, every tool result and every tool error) and therefore to what the
audit log keeps. It runs before long values are cut, so a cut can't leave
half a secret behind.

* Field names: a value is replaced when its key matches a configured name,
  case-insensitively, as a whole word segment of the key (`password` matches
  `db_password`, `password_hash`, `PasswordHash`; `session` matches
  `sessionid`) or, for dotted names, when the key's path ends with it
  (`attrs.user_email` matches `rows.0.attrs.user_email`).
* Secret-looking values are replaced wherever they appear, including inside
  free text: key=value and "key": "value" pairs for secret-ish keys,
  bearer and basic credentials, cookies, credentials in URLs, private keys
  (also when the END line is missing), JWTs, and well-known key formats
  (AWS, GitHub, GitLab, Slack, sk- keys).

Field-name redaction can't see a value renamed by a query (`| eval v =
attrs.password`); the text patterns still apply to it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

MASK = "[redacted]"

_SECRET_KEYS = (r"(?:password|passwd|pwd|secret|client_secret|aws_secret_access_key|secret_access_key|"
                r"token|access_token|auth_token|refresh_token|id_token|api[_-]?key|access[_-]?key|private[_-]?key|"
                r"credentials?)")
_PAIR = re.compile(r"(?i)(?<![A-Za-z0-9])(" + _SECRET_KEYS + r")(\"?\s*[=:]\s*\"?|\s+is\s+)"
                   r"(\"[^\"]*\"|'[^']*'|[^\s\",;&'}]+)")
_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.DOTALL),
    re.compile(r"(?i)(?<=bearer )[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)(?<=basic )[A-Za-z0-9+/=]{12,}"),
    re.compile(r"(?i)(?<=cookie: )[^\r\n]+"),
    re.compile(r"(?i)(?<=set-cookie: )[^\r\n]+"),
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
]


def _norm(name: str) -> str:
    return name.lower().replace("-", "_")


def _segments(key: str) -> list[str]:
    """db_password -> [db, password]; PasswordHash -> [password, hash]; sessionid -> [sessionid]."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return [p for p in re.split(r"[^a-z0-9]+", spaced.lower()) if p]


class Redactor:
    def __init__(self, fields: Iterable[str]):
        self.names: list[str] = []
        self.paths: list[str] = []
        for f in fields:
            f = _norm(str(f).strip())
            if f:
                (self.paths if "." in f else self.names).append(f)

    def _field(self, key: str, path: str) -> bool:
        k = _norm(key)
        parts = _segments(key)
        for n in self.names:
            if k == n or n in parts or "_" in n and n in k:
                return True
            if len(n) >= 6 and any(p.startswith(n) for p in parts):  # sessionid, passwordhash
                return True
        p = _norm(path)
        return any(p == q or p.endswith("." + q) for q in self.paths)

    def text(self, text: str) -> tuple[str, int]:
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
            text, n = self.text(value)
            return (MASK if n and text.strip() == MASK else text), n
        return value, 0
