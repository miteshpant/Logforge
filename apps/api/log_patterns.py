"""
Log pattern clustering (Phase 11), Drain-style, no language model.

Each line is masked (addresses, UUIDs, hex ids, versions, numbers become
<*>), split into tokens, and matched against the templates that have its
token count and first token. It joins the most similar one if few enough
tokens differ (<*> matching anything): at most one in a short line, at most
MAX_DIFFERENT of them in a long one. The differing positions become <*>;
otherwise the line starts a new template. A fixed similarity ratio merges
too much in short lines ("x task started id=<*>" and "y task completed
id=<*>" are 3 of 5 alike, but different messages). Already-seen masked lines skip the
search, so the cost is close to one regex pass per line.

`new`: when a baseline is clustered first (the days before the window),
templates first created by the window's lines are new. `rare`: seen at most
RARE times in the window.

Reference: He et al., "Drain: An Online Log Parsing Approach with Fixed
Depth Tree" (ICWS 2017).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

MAX_DIFFERENT = 0.3  # share of a line's tokens that may differ from its template (at least one)
MAX_TOKENS = 80
MAX_BUCKET = 200  # templates per (length, first token) before new ones join the wildcard bucket
RARE = 2
WILD = "<*>"

_MASK = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"   # UUID
    r"|\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"                                            # IPv4[:port]
    r"|\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b"                                   # IPv6 (full-ish)
    r"|\b0x[0-9a-fA-F]+\b|\b[0-9a-fA-F]{12,}\b"                                          # hex ids
    r"|\bv?\d+(?:\.\d+){1,3}\b"                                                        # versions
    r"|(?<![A-Za-z0-9_])[-+]?\d+(?:[.,:]\d+)*(?:ms|s|m|h|kb|mb|gb|b|%)?\b"               # numbers, times
)


def mask(line: str) -> str:
    return _MASK.sub(WILD, line)


@dataclass
class Template:
    id: int
    tokens: List[str]
    count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    example: str = ""
    services: Dict[str, int] = field(default_factory=dict)
    baseline: bool = False  # created while clustering the baseline
    baseline_count: int = 0
    merged: set = field(default_factory=set)  # positions made <*> by merging lines (not by masking)

    @property
    def text(self) -> str:
        return " ".join(self.tokens)


class Clusterer:
    def __init__(self, max_different: float = MAX_DIFFERENT):
        self.max_different = max_different
        self.templates: List[Template] = []
        self._tree: Dict[Tuple[int, str], List[Template]] = {}
        self._seen: Dict[str, Template] = {}
        self._baseline = False

    def baseline(self, lines: Iterable[str]) -> None:
        """Cluster lines from before the window: their templates are not new."""
        self._baseline = True
        try:
            for line in lines:
                self.add(line)
        finally:
            self._baseline = False

    def add(self, line: str, ts: Optional[datetime] = None, service: Optional[str] = None) -> Template:
        masked = mask(line or "")
        template = self._seen.get(masked)
        if template is None:
            tokens = masked.split()[:MAX_TOKENS] or [""]
            template = self._match(tokens)
            if len(self._seen) < 2_000_000:
                self._seen[masked] = template
        if self._baseline:
            template.baseline_count += 1
            return template
        template.count += 1
        if template.count == 1:
            template.example = (line or "")[:500]
        if ts is not None:
            if template.first_seen is None or ts < template.first_seen:
                template.first_seen = ts
            if template.last_seen is None or ts > template.last_seen:
                template.last_seen = ts
        if service:
            template.services[service] = template.services.get(service, 0) + 1
        return template

    def _limit(self, length: int) -> int:
        return max(1, int(self.max_different * length))

    def _fit(self, template: Template, tokens: List[str]) -> Optional[set]:
        """The positions the template would have merged after taking the line, or None if too many."""
        differ = {i for i, (a, b) in enumerate(zip(template.tokens, tokens)) if a != b and a != WILD}
        merged = template.merged | differ
        return merged if len(merged) <= self._limit(len(tokens)) else None

    def _take(self, template: Template, tokens: List[str], merged: set) -> Template:
        if merged != template.merged:
            template.tokens = [WILD if i in merged else a for i, a in enumerate(template.tokens)]
            template.merged = merged
        return template

    def _new(self, key: Tuple[int, str], tokens: List[str]) -> Template:
        template = Template(id=len(self.templates) + 1, tokens=list(tokens), baseline=self._baseline)
        self.templates.append(template)
        self._tree.setdefault(key, []).append(template)
        return template

    def _match(self, tokens: List[str]) -> Template:
        first = tokens[0]
        key = (len(tokens), WILD if WILD in first or any(c.isdigit() for c in first) else first)
        bucket = self._tree.get(key) or []
        best, best_merged = None, None
        for template in bucket:
            merged = self._fit(template, tokens)
            if merged is not None and (best is None or len(merged) < len(best_merged)):
                best, best_merged = template, merged
                if not merged - template.merged:
                    break
        if best is not None:
            return self._take(best, tokens, best_merged)
        if len(bucket) >= MAX_BUCKET and key[1] != WILD:
            wild = (len(tokens), WILD)
            for template in self._tree.get(wild) or []:
                merged = self._fit(template, tokens)
                if merged is not None:
                    return self._take(template, tokens, merged)
            return self._new(wild, tokens)
        return self._new(key, tokens)

    def results(self, mode: str = "all", with_baseline: bool = False) -> List[Dict[str, Any]]:
        """The window's templates, most frequent first. mode: all | new | rare (new or rare)."""
        rows = []
        for t in self.templates:
            if t.count == 0:
                continue
            new = with_baseline and not t.baseline
            rare = t.count <= RARE
            if mode == "new" and not new or mode == "rare" and not (new or rare):
                continue
            rows.append({"pattern_id": t.id, "pattern": t.text, "count": t.count, "first_seen": t.first_seen,
                         "last_seen": t.last_seen, "new": int(new), "rare": int(rare),
                         "baseline_count": t.baseline_count, "example": t.example,
                         "services": ", ".join(s for s, _ in sorted(t.services.items(), key=lambda x: -x[1])[:5])})
        rows.sort(key=lambda r: (-r["new"], -r["count"]) if mode != "all" else (-r["count"], r["pattern_id"]))
        return rows
