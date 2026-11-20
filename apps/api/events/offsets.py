"""
Kafka offsets to commit once their messages are processed (Phase 12).

Workers finish messages out of order, and Kafka commits one offset per
partition meaning "everything before this is done". So a partition's commit
advances only past a contiguous run of finished messages: one message still
being written holds back the commit of the ones after it (they're redelivered
if the consumer dies first: at-least-once, never lost).
"""

from __future__ import annotations

from typing import Any, Dict, Hashable, Iterable, Set


class OffsetTracker:
    def __init__(self) -> None:
        self._pending: Dict[Hashable, Set[int]] = {}
        self._done: Dict[Hashable, Set[int]] = {}
        self._committed: Dict[Hashable, int] = {}

    def track(self, tp: Hashable, offset: int) -> None:
        self._pending.setdefault(tp, set()).add(offset)

    def done(self, tp: Hashable, offset: int) -> None:
        if offset in self._pending.get(tp, ()):  # not if the partition was revoked meanwhile
            self._done.setdefault(tp, set()).add(offset)

    def revoke(self, tps: Iterable[Hashable]) -> None:
        for tp in tps:
            self._pending.pop(tp, None)
            self._done.pop(tp, None)
            self._committed.pop(tp, None)

    def pending(self) -> int:
        return sum(len(p) for p in self._pending.values())

    def committable(self) -> Dict[Any, int]:
        """{partition: next offset to read} for partitions that advanced since the last call."""
        out = {}
        for tp, pending in self._pending.items():
            done = self._done.get(tp, set())
            advanced = None
            for offset in sorted(pending):
                if offset not in done:
                    break
                advanced = offset
            if advanced is None:
                continue
            finished = {o for o in pending if o <= advanced}
            pending -= finished
            done -= finished
            if self._committed.get(tp) != advanced + 1:
                self._committed[tp] = advanced + 1
                out[tp] = advanced + 1
        return out
