"""
Built-in pipelines (Phase 4): the formats Logforge parses out of the box,
expressed as ordinary pipelines in config/builtin_pipelines/*.yml.

* Tenants can select them by name (X-Logforge-Pipeline: syslog), view and
  copy them in the UI, or shadow one with a pipeline of the same id.
* The format endpoints (/v1/ingest/nginx, /syslog, /cef, /text and their
  /batch forms) parse through them: ParserFactory hands out PipelineParser
  for those formats, so there is one parsing mechanism. The old parser
  classes remain only as the reference for the parity tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

BUILTIN_DIR = Path(__file__).resolve().parent / "config" / "builtin_pipelines"
FORMAT_PIPELINES = {"nginx": "nginx-access", "syslog": "syslog", "cef": "cef", "text": "text"}


@lru_cache(maxsize=1)
def builtin_definitions() -> List[Dict[str, Any]]:
    return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(BUILTIN_DIR.glob("*.yml"))]


def builtin_records():
    from pipeline_store import PipelineRecord

    return {r.id: r for r in (PipelineRecord.from_dict({**d, "builtin": True}) for d in builtin_definitions())}


@lru_cache(maxsize=None)
def _builtin(pipeline_id: str):
    record = builtin_records().get(pipeline_id)
    if record is None:
        raise KeyError(f"no built-in pipeline {pipeline_id!r}")
    return record


def parse_line(pipeline_id: str, raw: str, service: str = "unknown", host: str = "", level: str = "info"):
    """Run one raw line through a built-in pipeline and return a LogEntry
    (raises parsers.ParseError if the pipeline fails or drops it)."""
    from models import LogEntry
    from parsers import ParseError
    from pipeline_processors import ProcessorContext

    doc: Dict[str, Any] = {"msg": raw, "service": service, "host": host, "level": level, "src_ip": "", "user_id": "",
                           "attrs": {}}
    result = _builtin(pipeline_id).pipeline.run(doc, ProcessorContext())
    if result.status != "ok":
        reason = result.error["message"] if result.error else "the event was dropped"
        raise ParseError(f"{pipeline_id} parse error: {reason}")
    out = result.doc
    out.pop("_route", None)
    out.setdefault("ts", datetime.now(timezone.utc))
    return LogEntry(**out)


def pipeline_parser_class(pipeline_id: str):
    from parsers import BaseParser

    class PipelineParser(BaseParser):
        """A ParserFactory parser backed by a built-in pipeline."""

        def parse(self, raw_message: str, **kwargs):
            return parse_line(pipeline_id, raw_message, service=kwargs.get("service", self.default_service),
                              host=kwargs.get("host", self.default_host), level=self.default_level)

    PipelineParser.__name__ = f"PipelineParser[{pipeline_id}]"
    return PipelineParser
