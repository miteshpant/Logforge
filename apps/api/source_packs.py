"""
Source packs (Phase 7): everything that makes one kind of data source useful,
in one versioned directory under packages/packs/<id>/:

    pack.yml          id, name, version (semver), description, sources (what
                      to ship and how), samples (with expectations)
    pipelines/*.yml   ingest pipelines with routing; the common-schema
                      mapping is part of the pipeline
    rules/*.yml       detection rules with fixtures; ids start with <id>-
    searches/*.yml    saved searches and alert templates
    dashboards/*.yml  dashboards: variables and LogforgeQL panels
    lookups/*.csv     lookup tables, named after the file
    samples/*         sample logs from the source

Each part is checked with the code that installs it (PipelineRecord,
the rule gate, SavedSearch, dashboard variables, the query compiler, the
lookup CSV parser), so a pack that loads is a pack that can be installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PANEL_TYPES = ("metric", "stat", "gauge", "table", "line_chart", "area_chart", "bar_chart", "pie_chart")
MAX_SAMPLE_LINES = 5000


class PackError(ValueError):
    """A pack that cannot be loaded. The message names the file and the reason."""


def version_key(version: str) -> Tuple[int, int, int]:
    match = _VERSION_RE.match(version or "")
    if not match:
        raise PackError(f"version must be MAJOR.MINOR.PATCH, got {version!r}")
    return tuple(int(x) for x in match.groups())  # type: ignore[return-value]


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


@dataclass
class Sample:
    file: str
    service: str
    lines: List[str]
    pipeline: Optional[str] = None
    expect: List[Dict[str, Any]] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)


@dataclass
class Pack:
    id: str
    name: str
    version: str
    description: str
    path: Path
    sources: List[Dict[str, Any]] = field(default_factory=list)
    pipelines: List[Any] = field(default_factory=list)       # PipelineRecord
    rules: List[Dict[str, Any]] = field(default_factory=list)  # Sigma documents
    searches: List[Any] = field(default_factory=list)        # SavedSearch
    dashboards: List[Dict[str, Any]] = field(default_factory=list)
    lookups: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    samples: List[Sample] = field(default_factory=list)

    # -- identity of each installable object ------------------------------------
    def objects(self) -> Dict[str, Any]:
        """kind:key -> the definition installed for it."""
        out: Dict[str, Any] = {}
        for p in self.pipelines:
            out[f"pipeline:{p.id}"] = {"name": p.name, "description": p.description, "routing": p.routing,
                                       **p.definition()}
        for r in self.rules:
            out[f"rule:{r['id']}"] = r
        for s in self.searches:
            out[f"search:{s.id}"] = {"name": s.name, "description": s.description, "enabled": s.enabled,
                                     **s.definition()}
        for d in self.dashboards:
            out[f"dashboard:{d['name']}"] = d
        for name, table in self.lookups.items():
            out[f"lookup:{name}"] = {"columns": table["columns"], "key": table["key"], "rows": table["rows"]}
        return out

    def object_hashes(self) -> Dict[str, str]:
        return {key: canonical_hash(value) for key, value in self.objects().items()}

    def summary(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "version": self.version, "description": self.description,
                "sources": self.sources,
                "contents": {"pipelines": len(self.pipelines), "rules": len(self.rules),
                             "searches": len(self.searches), "dashboards": len(self.dashboards),
                             "lookups": len(self.lookups)}}

    def detail(self) -> Dict[str, Any]:
        return {**self.summary(),
                "pipelines": [{"id": p.id, "name": p.name, "description": p.description, "routing": p.routing}
                              for p in self.pipelines],
                "rules": [{"id": r["id"], "title": r.get("title"), "level": r.get("level"),
                           "description": r.get("description", ""), "tags": r.get("tags", [])} for r in self.rules],
                "searches": [{"id": s.id, "name": s.name, "every": s.every, "alert": bool(s.alert),
                              "enabled": s.enabled} for s in self.searches],
                "dashboards": [{"name": d["name"], "panels": len(d["panels"])} for d in self.dashboards],
                "lookups": [{"name": n, "rows": len(t["rows"])} for n, t in self.lookups.items()],
                "samples": [{"file": s.file, "service": s.service, "lines": len(s.lines)} for s in self.samples]}


def _read_yaml(path: Path, rel: str, multi: bool = False) -> Any:
    try:
        text = path.read_text()
        if multi:
            return [d for d in yaml.safe_load_all(text) if d is not None]
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PackError(f"{rel}: invalid YAML: {e}") from None


def _files(root: Path, sub: str, suffixes: Tuple[str, ...]) -> List[Path]:
    folder = root / sub
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in suffixes)


def _lookup_metas(lookups: Dict[str, Dict[str, Any]]):
    import logql_pipeline as lp

    return {name: lp.LookupMeta(name=name, version=1, columns=t["columns"], key=t["key"])
            for name, t in lookups.items()}


def check_query(query: str, rel: str, lookups: Dict[str, Dict[str, Any]],
                variables: Optional[Dict[str, Any]] = None) -> None:
    import logql_pipeline as lp
    from query_engine import QueryFieldError

    end = datetime(2026, 1, 8, tzinfo=timezone.utc)
    try:
        lp.compile_pipeline(query, customer_id="pack-check", start=end - timedelta(days=7), end=end,
                            lookups=_lookup_metas(lookups), variables=variables or {})
    except (lp.PipelineError, QueryFieldError) as e:
        raise PackError(f"{rel}: {e}") from None


def load_pack(root: Path) -> Pack:
    from dashboard_queries import VariableError, validate_variables
    from lookup_tables import LookupValidationError, parse_csv
    from pipeline_store import PipelineRecord
    from pipelines import PipelineError
    from saved_searches import SavedSearch, SearchValidationError

    root = Path(root)
    meta = _read_yaml(root / "pack.yml", "pack.yml") if (root / "pack.yml").is_file() else None
    if not isinstance(meta, dict):
        raise PackError("pack.yml is missing or not a mapping")
    pack_id = str(meta.get("id") or "")
    if not _ID_RE.match(pack_id):
        raise PackError(f"pack.yml: id {pack_id!r} must be lowercase letters, digits and - (2-40)")
    if pack_id != root.name:
        raise PackError(f"pack.yml: id {pack_id!r} must match the directory name {root.name!r}")
    version = str(meta.get("version") or "")
    try:
        version_key(version)
    except PackError as e:
        raise PackError(f"pack.yml: {e}") from None
    name = str(meta.get("name") or "").strip()
    if not name:
        raise PackError("pack.yml: name is required")
    pack = Pack(id=pack_id, name=name, version=version, description=str(meta.get("description") or ""),
                path=root, sources=list(meta.get("sources") or []))

    for path in _files(root, "lookups", (".csv",)):
        rel = f"lookups/{path.name}"
        try:
            columns, key, rows = parse_csv(path.read_text())
        except LookupValidationError as e:
            raise PackError(f"{rel}: {e}") from None
        pack.lookups[path.stem] = {"columns": columns, "key": key, "rows": rows}

    for path in _files(root, "pipelines", (".yml", ".yaml")):
        rel = f"pipelines/{path.name}"
        data = _read_yaml(path, rel)
        try:
            pack.pipelines.append(PipelineRecord.from_dict(data if isinstance(data, dict) else {}))
        except (PipelineError, ValueError, TypeError) as e:
            raise PackError(f"{rel}: {e}") from None

    for path in _files(root, "rules", (".yml", ".yaml")):
        rel = f"rules/{path.name}"
        for doc in _read_yaml(path, rel, multi=True):
            if not isinstance(doc, dict):
                raise PackError(f"{rel}: each document must be a rule mapping")
            rule_id = str(doc.get("id") or "")
            if not rule_id.startswith(f"{pack_id}-"):
                raise PackError(f"{rel}: rule id {rule_id!r} must start with {pack_id}-")
            pack.rules.append(doc)
    if pack.rules:
        _gate_rules(pack)

    for path in _files(root, "searches", (".yml", ".yaml")):
        rel = f"searches/{path.name}"
        data = _read_yaml(path, rel)
        try:
            search = SavedSearch.from_dict(data if isinstance(data, dict) else {})
        except SearchValidationError as e:
            raise PackError(f"{rel}: {e}") from None
        check_query(search.query, rel, pack.lookups)
        pack.searches.append(search)

    for path in _files(root, "dashboards", (".yml", ".yaml")):
        rel = f"dashboards/{path.name}"
        data = _read_yaml(path, rel)
        if not isinstance(data, dict) or not data.get("name"):
            raise PackError(f"{rel}: a dashboard needs a name")
        try:
            variables = validate_variables(data.get("variables") or [])
        except VariableError as e:
            raise PackError(f"{rel}: {e}") from None
        panels = []
        for i, panel in enumerate(data.get("panels") or []):
            where = f"{rel}: panel {i + 1}"
            if not isinstance(panel, dict) or not panel.get("name") or not panel.get("query"):
                raise PackError(f"{where}: needs a name and a query")
            if panel.get("type") not in PANEL_TYPES:
                raise PackError(f"{where}: type must be one of {', '.join(PANEL_TYPES)}")
            check_query(panel["query"], where, pack.lookups, {v["name"]: "x" for v in variables})
            panels.append({"name": str(panel["name"]), "type": panel["type"], "query": panel["query"],
                           "size": panel.get("size") or {"w": 1 if panel["type"] in ("metric", "stat") else 2,
                                                         "h": 1 if panel["type"] in ("metric", "stat") else 2}})
        if not panels:
            raise PackError(f"{rel}: a dashboard needs panels")
        pack.dashboards.append({"name": str(data["name"]), "description": str(data.get("description") or ""),
                                "variables": variables, "panels": panels})

    for i, raw in enumerate(meta.get("samples") or []):
        where = f"pack.yml: samples[{i}]"
        if not isinstance(raw, dict) or not raw.get("file") or not raw.get("service"):
            raise PackError(f"{where}: needs file and service")
        path = root / str(raw["file"])
        if not path.is_file():
            raise PackError(f"{where}: {raw['file']} does not exist")
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        if not lines or len(lines) > MAX_SAMPLE_LINES:
            raise PackError(f"{where}: {raw['file']} needs 1 to {MAX_SAMPLE_LINES} lines")
        pack.samples.append(Sample(file=str(raw["file"]), service=str(raw["service"]), lines=lines,
                                   pipeline=raw.get("pipeline"), expect=list(raw.get("expect") or []),
                                   rules=[str(r) for r in raw.get("rules") or []]))
    return pack


def _gate_rules(pack: Pack) -> None:
    from detection_as_code import _gate

    _, rejected = _gate("pack-check", pack.rules)
    if rejected:
        reasons = "; ".join(f"{r['rule']}: {r['reason']}" for r in rejected)
        raise PackError(f"rules: {reasons}")


def default_packs_dir() -> Path:
    """$SOURCE_PACKS_DIR, the repository checkout, or the compose mount."""
    env = os.getenv("SOURCE_PACKS_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "packages" / "packs"
        if candidate.is_dir():
            return candidate
    return Path("/packages/packs")


def load_catalogue(root: Optional[Path] = None) -> Tuple[List[Pack], Dict[str, str]]:
    """Every pack under `root` (directories starting with _ are templates), and
    the reason each broken one failed to load."""
    root = Path(root or default_packs_dir())
    packs, errors = [], {}
    if not root.is_dir():
        return packs, errors
    for path in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        try:
            packs.append(load_pack(path))
        except PackError as e:
            errors[path.name] = str(e)
    return packs, errors
