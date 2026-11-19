"""
Ingest pipelines (Phase 4): an ordered list of processors with conditions
and failure handling, modelled on Elastic ingest pipelines.

A pipeline definition (JSON or YAML):

    name: nginx
    description: Parse nginx access logs
    processors:
      - grok: {field: msg, patterns: ["%{COMBINEDAPACHELOG}"]}
        tag: parse
      - convert: {field: attrs.bytes, type: integer}
        ignore_failure: true
      - drop: {}
        if: attrs.request == '/healthz'
    on_failure:
      - set: {field: attrs.pipeline_error, value: "{{_error.message}}"}

Failure handling, for a processor that raises ProcessorError (or whose `if`
can't be evaluated):

1. `ignore_failure: true`: carry on with the next processor;
2. its own `on_failure` steps, then carry on;
3. the pipeline's `on_failure` steps, then stop (the event is kept);
4. otherwise the result is "failed" and the caller dead-letters the event.

While handlers run, `_error` holds {processor, index, tag, message}.
"""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pipeline_conditions import ConditionError, compile_condition
from pipeline_processors import DropEvent, ProcessorContext, ProcessorError, build_processor

MAX_PROCESSORS = 100
STEP_KEYS = {"if", "tag", "ignore_failure", "on_failure", "description"}


class PipelineError(ValueError):
    """The definition is invalid (refused when saved)."""


@dataclass
class Step:
    kind: str
    config: Dict[str, Any]
    fn: Any
    condition: Any = None
    condition_source: str = ""
    tag: str = ""
    description: str = ""
    ignore_failure: bool = False
    on_failure: List["Step"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {self.kind: self.config}
        if self.condition_source:
            out["if"] = self.condition_source
        if self.tag:
            out["tag"] = self.tag
        if self.description:
            out["description"] = self.description
        if self.ignore_failure:
            out["ignore_failure"] = True
        if self.on_failure:
            out["on_failure"] = [s.to_dict() for s in self.on_failure]
        return out


def _build_step(raw: Any, where: str, allow_handlers: bool) -> Step:
    if not isinstance(raw, dict):
        raise PipelineError(f"{where}: each processor must be an object")
    kinds = [k for k in raw if k not in STEP_KEYS]
    if len(kinds) != 1:
        raise PipelineError(f"{where}: each step needs exactly one processor (found {kinds or 'none'})")
    kind = kinds[0]
    config = raw[kind] if raw[kind] is not None else {}
    try:
        fn = build_processor(kind, config)
    except ProcessorError as e:
        raise PipelineError(f"{where}: {e}") from None
    step = Step(kind=kind, config=config, fn=fn, tag=str(raw.get("tag") or ""),
                description=str(raw.get("description") or ""), ignore_failure=bool(raw.get("ignore_failure")))
    if raw.get("if") not in (None, ""):
        step.condition_source = str(raw["if"])
        try:
            step.condition = compile_condition(step.condition_source)
        except ConditionError as e:
            raise PipelineError(f"{where}.if: {e}") from None
    if raw.get("on_failure"):
        if not allow_handlers:
            raise PipelineError(f"{where}: on_failure handlers cannot have their own on_failure")
        step.on_failure = _build_steps(raw["on_failure"], f"{where}.on_failure", allow_handlers=False)
    return step


def _build_steps(raw: Any, where: str, allow_handlers: bool = True) -> List[Step]:
    if not isinstance(raw, list):
        raise PipelineError(f"{where} must be a list")
    return [_build_step(item, f"{where}[{i}]", allow_handlers) for i, item in enumerate(raw)]


@dataclass
class Result:
    status: str  # ok | dropped | failed
    doc: Dict[str, Any]
    error: Optional[Dict[str, Any]] = None


class PipelineStats:
    """Per-processor counters for one pipeline version (thread-safe)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.events = {"in": 0, "ok": 0, "dropped": 0, "failed": 0}
        self.processors: List[Dict[str, Any]] = []

    def bind(self, steps: List[Step]) -> None:
        if len(self.processors) != len(steps):
            self.processors = [{"index": i, "type": s.kind, "tag": s.tag, "count": 0, "skipped": 0, "failed": 0,
                                "dropped": 0, "time_us": 0.0} for i, s in enumerate(steps)]

    def step(self, index: int, outcome: Optional[str], elapsed_s: float) -> None:
        with self._lock:
            entry = self.processors[index]
            entry["count"] += 1
            if outcome:
                entry[outcome] += 1
            entry["time_us"] += elapsed_s * 1e6

    def event(self, status: str) -> None:
        with self._lock:
            self.events["in"] += 1
            self.events[status] += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {"events": dict(self.events),
                    "processors": [{**p, "time_us": round(p["time_us"], 1),
                                    "avg_us": round(p["time_us"] / p["count"], 2) if p["count"] else 0.0}
                                   for p in self.processors]}


class Pipeline:
    def __init__(self, name: str, steps: List[Step], on_failure: List[Step], description: str = ""):
        self.name, self.steps, self.on_failure, self.description = name, steps, on_failure, description

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pipeline":
        if not isinstance(data, dict):
            raise PipelineError("a pipeline must be an object")
        name = str(data.get("name") or "").strip()
        if not name:
            raise PipelineError("a pipeline needs a name")
        raw = data.get("processors") or []
        if len(raw) > MAX_PROCESSORS:
            raise PipelineError(f"a pipeline can have at most {MAX_PROCESSORS} processors")
        return cls(name, _build_steps(raw, "processors"), _build_steps(data.get("on_failure") or [], "on_failure"),
                   str(data.get("description") or ""))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"name": self.name, "processors": [s.to_dict() for s in self.steps]}
        if self.description:
            out["description"] = self.description
        if self.on_failure:
            out["on_failure"] = [s.to_dict() for s in self.on_failure]
        return out

    # -- execution ---------------------------------------------------------
    def run(self, doc: Dict[str, Any], ctx: ProcessorContext, stats: Optional[PipelineStats] = None,
            trace: Optional[List[Dict[str, Any]]] = None) -> Result:
        if stats is not None:
            stats.bind(self.steps)
        result = self._run(doc, ctx, stats, trace)
        if stats is not None:
            stats.event(result.status)
        return result

    def _run(self, doc, ctx, stats, trace) -> Result:
        for index, step in enumerate(self.steps):
            started = time.perf_counter()
            outcome = _attempt(step, index, doc, ctx, trace)
            if stats is not None:
                stats.step(index, {"skipped": "skipped", "dropped": "dropped", "ok": None}.get(outcome[0], "failed"),
                           time.perf_counter() - started)
            status, error = outcome
            if status == "dropped":
                return Result("dropped", doc)
            if status != "error":
                continue
            if step.ignore_failure:
                continue
            handlers = step.on_failure or self.on_failure
            if not handlers:
                return Result("failed", doc, error)
            handled = _handle(handlers, error, doc, ctx, trace)
            if handled is not None:
                return handled
            if not step.on_failure:  # the pipeline-level handler ends the run, keeping the event
                return Result("ok", doc)
        return Result("ok", doc)


def _attempt(step: Step, index: int, doc, ctx, trace, handler: bool = False):
    """Run one step: ("ok" | "skipped" | "dropped" | "error", error)."""
    error = None
    try:
        if step.condition is not None and not step.condition(doc):
            _trace(trace, step, index, "skipped", doc, handler=handler)
            return "skipped", None
        step.fn(doc, ctx)
    except DropEvent:
        _trace(trace, step, index, "dropped", doc, handler=handler)
        return "dropped", None
    except (ProcessorError, ConditionError) as e:
        error = {"processor": step.kind, "index": index, "tag": step.tag, "message": str(e)}
    except Exception as e:  # a processor bug must not lose the event; report it as a failure
        error = {"processor": step.kind, "index": index, "tag": step.tag,
                 "message": f"{step.kind}: unexpected {type(e).__name__}: {e}"}
    if error:
        _trace(trace, step, index, "error", doc, error, handler=handler)
        return "error", error
    _trace(trace, step, index, "ok", doc, handler=handler)
    return "ok", None


def _handle(handlers: List[Step], error, doc, ctx, trace) -> Optional[Result]:
    """Run on_failure handlers; a Result if they end the event, else None."""
    doc["_error"] = dict(error)
    try:
        for index, step in enumerate(handlers):
            status, handler_error = _attempt(step, index, doc, ctx, trace, handler=True)
            if status == "dropped":
                return Result("dropped", doc)
            if status == "error" and not step.ignore_failure:
                return Result("failed", doc, handler_error)
    finally:
        doc.pop("_error", None)
    return None


# -- simulation ------------------------------------------------------------------

def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _trace(trace, step: Step, index: int, status: str, doc, error=None, handler: bool = False) -> None:
    if trace is None:
        return
    entry = {"index": index, "processor": step.kind, "tag": step.tag, "status": status,
             "doc": jsonable({k: v for k, v in doc.items() if k != "_error"})}
    if handler:
        entry["on_failure"] = True
    if error:
        entry["error"] = error["message"]
    trace.append(entry)


def simulate(pipeline: Pipeline, docs: List[Dict[str, Any]], ctx: ProcessorContext) -> List[Dict[str, Any]]:
    """Run copies of `docs` through the pipeline, recording the document after every step."""
    results = []
    for original in docs:
        steps: List[Dict[str, Any]] = []
        result = pipeline.run(copy.deepcopy(original), ctx, trace=steps)
        results.append({"status": result.status, "doc": jsonable(result.doc) if result.status != "dropped" else None,
                        "error": result.error, "steps": steps})
    return results
