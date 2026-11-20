"""
Citation checks (Phase 8). Answers cite the ids tool results carry, in
square brackets after the sentence: "Logins failed 40 times [C1][C3]."

Every sentence that states something must cite; a sentence made only of
citations belongs to the one before it, and headings ending with ':' and
lines without letters need none.
"""

from __future__ import annotations

import re
from typing import Any

CITE = re.compile(r"\[(C\d+)\]")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=\S)")


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        for part in _SPLIT.split(line.strip()):
            part = part.strip()
            if not part:
                continue
            if out and not CITE.sub("", part).strip(" .,;"):
                out[-1] = f"{out[-1]} {part}"  # "... rose. [C1]"
            else:
                out.append(part)
    return out


def check_citations(text: str, issued: dict[str, Any]) -> dict[str, list[str]]:
    used: list[str] = []
    unknown: list[str] = []
    uncited: list[str] = []
    for cid in CITE.findall(text or ""):
        target = used if cid in issued else unknown
        if cid not in target:
            target.append(cid)
    for sentence in _sentences(text or ""):
        bare = CITE.sub("", sentence).strip()
        if not re.search(r"[A-Za-z]", bare) or bare.endswith(":"):
            continue
        if not CITE.search(sentence):
            uncited.append(sentence)
    return {"used": used, "unknown": unknown, "uncited": uncited}
