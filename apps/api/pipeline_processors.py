"""
Ingest pipeline processors (Phase 4).

A processor is built once from its config (build_processor validates it and
precompiles patterns, so a bad config is refused when the pipeline is
saved) and then called as fn(doc, ctx) for each event. `doc` is the log as a
dict (ts, host, service, level, msg, src_ip, user_id, status, attrs, ...);
fields are dotted paths. Processors change `doc` in place.

* ProcessorError: the processor could not do its job (bad input). The
  pipeline decides what happens: ignore_failure, on_failure, or the
  dead-letter queue.
* DropEvent: the event is discarded on purpose (`drop`).

Context (ProcessorContext) carries what some processors look up: GeoIP
ranges, lookup tables, the tenant's threat-intel indicator sets.
"""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pipeline_conditions import ConditionError, compile_script, delete_path, get_path, set_path

GROK_FILE = Path(__file__).resolve().parent / "config" / "grok_patterns.txt"
_MISSING = object()


class ProcessorError(Exception):
    pass


class DropEvent(Exception):
    pass


@dataclass
class ProcessorContext:
    tenant_id: str = ""
    now: Optional[datetime] = None
    geo: Any = None  # enrichment_processors.GeoIP
    tables: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # name -> {key: row}
    intel: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # threat-intel sets by type


Processor = Callable[[Dict[str, Any], ProcessorContext], None]
PROCESSORS: Dict[str, Callable[[Dict[str, Any]], Processor]] = {}


def processor(name: str):
    def register(builder):
        PROCESSORS[name] = builder
        return builder
    return register


def build_processor(kind: str, config: Dict[str, Any]) -> Processor:
    builder = PROCESSORS.get(kind)
    if builder is None:
        raise ProcessorError(f"unknown processor {kind!r} (one of {', '.join(sorted(PROCESSORS))})")
    if not isinstance(config, dict):
        raise ProcessorError(f"{kind}: options must be an object")
    try:
        return builder(config)
    except ProcessorError:
        raise
    except ConditionError as e:
        raise ProcessorError(f"{kind}: {e}") from None
    except (TypeError, ValueError, re.error) as e:
        raise ProcessorError(f"{kind}: invalid options: {e}") from None


# -- helpers ------------------------------------------------------------------

def _required(config: Dict[str, Any], key: str, kind: str) -> Any:
    value = config.get(key)
    if value in (None, "", []):
        raise ProcessorError(f"{kind}: option {key!r} is required")
    return value


def _read(doc: Dict[str, Any], path: str, kind: str, ignore_missing: bool = False) -> Any:
    value = get_path(doc, path, _MISSING)
    if value is _MISSING or value is None:
        if ignore_missing:
            return _MISSING
        raise ProcessorError(f"{kind}: field {path} is missing")
    return value


def _merge(doc: Dict[str, Any], target: str, values: Dict[str, Any]) -> None:
    if target in ("", "."):
        doc.update(values)
        return
    existing = get_path(doc, target)
    if not isinstance(existing, dict):
        existing = {}
        set_path(doc, target, existing)
    existing.update(values)


_TEMPLATE = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")


def render(template: Any, doc: Dict[str, Any]) -> Any:
    """{{attrs.user}} placeholders; a template that is exactly one placeholder keeps the value's type."""
    if not isinstance(template, str):
        return template
    whole = _TEMPLATE.fullmatch(template.strip())
    if whole:
        return get_path(doc, whole.group(1))
    return _TEMPLATE.sub(lambda m: "" if get_path(doc, m.group(1)) is None else str(get_path(doc, m.group(1))),
                         template)


def _field_processor(kind: str, config: Dict[str, Any]) -> Tuple[str, bool]:
    return _required(config, "field", kind), bool(config.get("ignore_missing", False))


# -- parse --------------------------------------------------------------------

@processor("json")
def _json(config):
    path, ignore_missing = _field_processor("json", config)
    target = config.get("target", "attrs")

    def run(doc, ctx):
        raw = _read(doc, path, "json", ignore_missing)
        if raw is _MISSING:
            return
        try:
            value = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        except ValueError as e:
            raise ProcessorError(f"json: {path} is not valid JSON ({e.msg})") from None
        if isinstance(value, dict):
            _merge(doc, target, value)
        else:
            set_path(doc, target, value)
    return run


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


@processor("kv")
def _kv(config):
    path, ignore_missing = _field_processor("kv", config)
    field_split = config.get("field_split", " ")
    value_split = config.get("value_split", "=")
    target, prefix = config.get("target", "attrs"), config.get("prefix", "")
    include, exclude = set(config.get("include_keys") or []), set(config.get("exclude_keys") or [])
    if not field_split or not value_split:
        raise ProcessorError("kv: field_split and value_split must not be empty")
    pair = re.compile(r'([^\s{fs}{vs}]+){vs}("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^{fs}]*)'.format(
        fs=re.escape(field_split), vs=re.escape(value_split)))

    def run(doc, ctx):
        raw = _read(doc, path, "kv", ignore_missing)
        if raw is _MISSING:
            return
        values = {}
        for key, value in pair.findall(str(raw)):
            key = key.strip()
            if (include and key not in include) or key in exclude:
                continue
            values[prefix + key] = _unquote(value.strip())
        if not values:
            raise ProcessorError(f"kv: no key{value_split}value pairs in {path}")
        _merge(doc, target, values)
    return run


@processor("csv")
def _csv(config):
    path, ignore_missing = _field_processor("csv", config)
    columns = _required(config, "columns", "csv")
    separator, quote = config.get("separator", ","), config.get("quote", '"')
    target = config.get("target", "attrs")
    if len(separator) != 1 or len(quote) != 1:
        raise ProcessorError("csv: separator and quote must be single characters")

    def run(doc, ctx):
        raw = _read(doc, path, "csv", ignore_missing)
        if raw is _MISSING:
            return
        try:
            row = next(csv.reader(io.StringIO(str(raw)), delimiter=separator, quotechar=quote))
        except (csv.Error, StopIteration) as e:
            raise ProcessorError(f"csv: cannot parse {path}: {e}") from None
        _merge(doc, target, {c: v for c, v in zip(columns, row) if c})
    return run


# grok ------------------------------------------------------------------------

def _load_grok(path: Path = GROK_FILE) -> Dict[str, str]:
    patterns = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, regex = line.partition(" ")
        patterns[name] = regex.strip()
    return patterns


GROK_PATTERNS = _load_grok()
_GROK_REF = re.compile(r"%\{(\w+)(?::([\w.\-@]+))?(?::(int|float|string))?\}")
_UNQUOTE_PATTERNS = {"QS", "QUOTEDSTRING"}


def _expand(pattern: str, definitions: Dict[str, str], captures: List[Tuple[str, str, str, Optional[str]]],
            depth: int = 0) -> str:
    if depth > 25:
        raise ProcessorError("grok: patterns refer to each other too deeply (recursive?)")

    def replace(match):
        name, field_name, cast = match.group(1), match.group(2), match.group(3)
        if name not in definitions:
            raise ProcessorError(f"grok: unknown pattern %{{{name}}}")
        inner = _expand(definitions[name], definitions, captures, depth + 1)
        if not field_name:
            return f"(?:{inner})"
        group = f"g{len(captures)}"
        captures.append((group, field_name, name, cast))
        return f"(?P<{group}>{inner})"

    return _GROK_REF.sub(replace, pattern)


def grok_to_regex(pattern: str, definitions: Optional[Dict[str, str]] = None) -> str:
    """The Python regex for a grok expression, with field names as group names
    (for display and tests; matching uses generated unique group names)."""
    captures: List[Tuple[str, str, str, Optional[str]]] = []
    regex = _expand(pattern, {**GROK_PATTERNS, **(definitions or {})}, captures)
    for group, field_name, _, _ in captures:
        regex = regex.replace(f"(?P<{group}>", f"(?P<{re.sub(r'[^0-9A-Za-z_]', '_', field_name)}>", 1)
    return regex


def _cast(value: str, cast: Optional[str]):
    if cast == "int":
        return int(value)
    if cast == "float":
        return float(value)
    return value


@processor("grok")
def _grok(config):
    path, ignore_missing = _field_processor("grok", config)
    patterns = _required(config, "patterns", "grok")
    if isinstance(patterns, str):
        patterns = [patterns]
    definitions = {**GROK_PATTERNS, **(config.get("pattern_definitions") or {})}
    target = config.get("target", "attrs")
    compiled = []
    for pattern in patterns:
        captures: List[Tuple[str, str, str, Optional[str]]] = []
        regex = _expand(pattern, definitions, captures)
        try:
            compiled.append((re.compile(regex), captures))
        except re.error as e:
            raise ProcessorError(f"grok: pattern {pattern!r} does not compile: {e}") from None

    def run(doc, ctx):
        raw = _read(doc, path, "grok", ignore_missing)
        if raw is _MISSING:
            return
        text = str(raw)
        for regex, captures in compiled:
            match = regex.search(text)
            if not match:
                continue
            values: Dict[str, Any] = {}
            for group, field_name, pattern_name, cast in captures:
                value = match.group(group)
                if value is None or field_name in values:
                    continue
                if pattern_name in _UNQUOTE_PATTERNS:
                    value = _unquote(value)
                try:
                    values[field_name] = _cast(value, cast)
                except ValueError:
                    values[field_name] = value
            for name, value in values.items():
                set_path(doc, name if "." in name else f"{target}.{name}" if target else name, value)
            return
        raise ProcessorError(f"grok: no grok pattern matched {path}")
    return run


@processor("regex")
def _regex(config):
    path, ignore_missing = _field_processor("regex", config)
    regex = re.compile(_required(config, "pattern", "regex"))
    if not regex.groupindex:
        raise ProcessorError("regex: the pattern needs named groups, e.g. (?P<ms>\\d+)")
    target = config.get("target", "attrs")

    def run(doc, ctx):
        raw = _read(doc, path, "regex", ignore_missing)
        if raw is _MISSING:
            return
        match = regex.search(str(raw))
        if not match:
            raise ProcessorError(f"regex: pattern did not match {path}")
        _merge(doc, target, {k: v for k, v in match.groupdict().items() if v is not None})
    return run


# syslog / CEF / LEEF ------------------------------------------------------------

_SYSLOG_LEVELS = {0: "fatal", 1: "fatal", 2: "fatal", 3: "error", 4: "warn", 5: "info", 6: "info", 7: "debug"}
_RFC5424 = re.compile(r"<(?P<pri>\d{1,3})>(?P<version>\d) (?P<ts>\S+) (?P<host>\S+) (?P<app>\S+) (?P<procid>\S+) "
                      r"(?P<msgid>\S+) (?P<sd>-|(?:\[(?:[^\]\\]|\\.)*\])+) ?(?P<msg>.*)", re.S)
_RFC3164 = re.compile(r"(?:<(?P<pri>\d{1,3})>)?(?P<ts>[A-Z][a-z]{2} [ \d]\d \d{2}:\d{2}:\d{2}) (?P<host>\S+) "
                      r"(?P<app>[^\s\[:]+)(?:\[(?P<pid>\d+)\])?: ?(?P<msg>.*)", re.S)


def _syslog_ts(value: str, now: datetime) -> Optional[datetime]:
    try:
        if value[:1].isdigit():
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        parsed = datetime.strptime(f"{now.year} {' '.join(value.split())}", "%Y %b %d %H:%M:%S")
        parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed - now > timedelta(days=1):  # December logs read in January
            parsed = parsed.replace(year=now.year - 1)
        return parsed
    except ValueError:
        return None


@processor("syslog")
def _syslog(config):
    path, ignore_missing = _field_processor("syslog", config)

    def run(doc, ctx):
        raw = _read(doc, path, "syslog", ignore_missing)
        if raw is _MISSING:
            return
        text = str(raw).strip()
        match = _RFC5424.match(text) or _RFC3164.match(text)
        if not match:
            raise ProcessorError(f"syslog: {path} is not an RFC 5424 or RFC 3164 message")
        parts = match.groupdict()
        info: Dict[str, Any] = {}
        if parts.get("pri"):
            pri = int(parts["pri"])
            info.update(priority=pri, facility=pri >> 3, severity=pri & 7)
            doc["level"] = _SYSLOG_LEVELS[pri & 7]
            doc["severity_num"], doc["facility"] = pri & 7, pri >> 3
        if parts.get("version"):
            info["version"] = int(parts["version"])
            for key in ("procid", "msgid"):
                if parts[key] != "-":
                    info[key] = parts[key]
            if parts["sd"] != "-":
                info["structured_data"] = parts["sd"]
        if parts.get("pid"):
            info["pid"] = int(parts["pid"])
        ts = _syslog_ts(parts["ts"], ctx.now or datetime.now(timezone.utc))
        if ts:
            doc["ts"] = ts
        if parts["host"] != "-":
            doc["host"] = parts["host"]
        if parts["app"] != "-":
            doc["service"] = parts["app"]
        doc["msg"] = parts["msg"]
        _merge(doc, "attrs.syslog", info)
    return run


def _cef_unescape(value: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "r": "\r"}.get(m.group(1), m.group(1)), value)


def _split_header(text: str, count: int) -> List[str]:
    """Split on unescaped | into `count` header fields plus the rest."""
    fields, current, i = [], [], 0
    while i < len(text) and len(fields) < count:
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            current.append(text[i:i + 2])
            i += 2
            continue
        if char == "|":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
        i += 1
    fields.append(text[i:] if len(fields) == count else "".join(current))
    return fields


_CEF_KEY = re.compile(r"(?:^|(?<=\s))([A-Za-z0-9_.\[\]-]+)=")


def _cef_extensions(text: str) -> Dict[str, str]:
    """CEF extensions: values may contain spaces; a value ends where the next ` key=` starts."""
    keys = [m for m in _CEF_KEY.finditer(text) if not (m.start() > 0 and text[m.start() - 1] == "\\")]
    values = {}
    for i, match in enumerate(keys):
        end = keys[i + 1].start() if i + 1 < len(keys) else len(text)
        values[match.group(1)] = _cef_unescape(text[match.end():end].rstrip())
    return values


def _cef_level(severity: int) -> str:
    return "fatal" if severity >= 8 else "error" if severity >= 6 else "warn" if severity >= 4 else "info"


@processor("cef")
def _cef(config):
    path, ignore_missing = _field_processor("cef", config)

    def run(doc, ctx):
        raw = _read(doc, path, "cef", ignore_missing)
        if raw is _MISSING:
            return
        text = str(raw).strip()
        start = text.find("CEF:")
        if start < 0:
            raise ProcessorError(f"cef: {path} has no CEF: header")
        parts = _split_header(text[start + 4:], 7)
        if len(parts) < 8:
            raise ProcessorError("cef: the header needs 7 |-separated fields")
        version, vendor, product, dev_version, signature, name, severity, extensions = parts
        try:
            sev = int(severity) if severity.strip().isdigit() else \
                {"low": 3, "medium": 5, "high": 7, "very-high": 9}[severity.strip().lower()]
        except KeyError:
            raise ProcessorError(f"cef: unknown severity {severity!r}") from None
        doc["attrs"] = doc.get("attrs") if isinstance(doc.get("attrs"), dict) else {}
        doc["attrs"]["cef"] = {"version": int(version) if version.isdigit() else version,
                               "device_vendor": _cef_unescape(vendor), "device_product": _cef_unescape(product),
                               "device_version": _cef_unescape(dev_version), "signature_id": _cef_unescape(signature),
                               "name": _cef_unescape(name), "severity": sev}
        ext = _cef_extensions(extensions)
        doc["attrs"].update(ext)
        doc["level"] = _cef_level(sev)
        doc["msg"] = _cef_unescape(name)
        if ext.get("src"):
            doc["src_ip"] = ext["src"]
        user = ext.get("suser") or ext.get("duser")
        if user:
            doc["user_id"] = user
        host = ext.get("dhost") or ext.get("shost") or ext.get("dvchost")
        if host:
            doc["host"] = host
    return run


@processor("leef")
def _leef(config):
    path, ignore_missing = _field_processor("leef", config)

    def run(doc, ctx):
        raw = _read(doc, path, "leef", ignore_missing)
        if raw is _MISSING:
            return
        text = str(raw).strip()
        start = text.find("LEEF:")
        if start < 0:
            raise ProcessorError(f"leef: {path} has no LEEF: header")
        body = text[start + 5:]
        version = body.split("|", 1)[0]
        count = 6 if version.startswith("2") else 5
        parts = body.split("|", count)
        if len(parts) < count + 1:
            raise ProcessorError("leef: incomplete header")
        delimiter = "\t"
        if version.startswith("2") and parts[5]:
            spec = parts[5]
            hex_digits = spec[2:] if spec.lower().startswith("0x") else spec[1:] if spec.lower().startswith("x") \
                and len(spec) > 1 else None
            try:
                delimiter = bytes.fromhex(hex_digits).decode() if hex_digits else spec
            except ValueError:
                raise ProcessorError(f"leef: bad delimiter {spec!r}") from None
        attributes = parts[count]
        doc.setdefault("attrs", {})
        doc["attrs"]["leef"] = {"version": version, "vendor": parts[1], "product": parts[2],
                                "product_version": parts[3], "event_id": parts[4]}
        for item in attributes.split(delimiter):
            key, sep, value = item.partition("=")
            if sep and key.strip():
                doc["attrs"][key.strip()] = value
        a = doc["attrs"]
        if a.get("src"):
            doc["src_ip"] = a["src"]
        if a.get("usrName"):
            doc["user_id"] = a["usrName"]
        if str(a.get("sev", "")).isdigit():
            doc["level"] = _cef_level(int(a["sev"]))
    return run


# date ---------------------------------------------------------------------------

def _zone(name: Optional[str]):
    if not name or name.upper() == "UTC":
        return timezone.utc
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ProcessorError(f"date: unknown time zone {name!r}") from None


def _parse_date(value: Any, fmt: str, zone) -> Optional[datetime]:
    try:
        if fmt == "ISO8601":
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        elif fmt in ("UNIX", "UNIX_MS"):
            number = float(value)
            parsed = datetime.fromtimestamp(number / 1000 if fmt == "UNIX_MS" else number, tz=timezone.utc)
        elif fmt == "HTTPDATE":
            parsed = datetime.strptime(str(value).strip(), "%d/%b/%Y:%H:%M:%S %z")
        else:
            parsed = datetime.strptime(str(value).strip(), fmt)
    except (ValueError, TypeError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


@processor("date")
def _date(config):
    path, ignore_missing = _field_processor("date", config)
    formats = config.get("formats") or ["ISO8601"]
    zone = _zone(config.get("timezone"))
    target = config.get("target", "ts")

    def run(doc, ctx):
        raw = _read(doc, path, "date", ignore_missing)
        if raw is _MISSING:
            return
        for fmt in formats:
            parsed = _parse_date(raw, fmt, zone)
            if parsed is not None:
                set_path(doc, target, parsed if target == "ts" else parsed.isoformat())
                return
        raise ProcessorError(f"date: {path}={str(raw)[:60]!r} matches none of {formats}")
    return run


# user agent -----------------------------------------------------------------------

_BROWSERS = [("Edge", r"Edg(?:e|A|iOS)?/([\d.]+)"), ("Opera", r"(?:OPR|Opera)/([\d.]+)"),
             ("Firefox", r"Firefox/([\d.]+)"), ("Chrome", r"(?:Chrome|CriOS)/([\d.]+)"),
             ("Safari", r"Version/([\d.]+).*Safari/"), ("curl", r"curl/([\d.]+)"),
             ("Python Requests", r"python-requests/([\d.]+)"), ("Go HTTP client", r"Go-http-client/([\d.]+)")]
_SYSTEMS = [("iOS", r"iPhone|iPad|iPod"), ("Android", r"Android"), ("Windows", r"Windows"),
            ("macOS", r"Mac OS X|Macintosh"), ("Linux", r"Linux|X11")]
_BOT = re.compile(r"bot|crawl|spider|slurp|monitor|probe", re.I)


@processor("user_agent")
def _user_agent(config):
    path, ignore_missing = _field_processor("user_agent", config)
    target = config.get("target", "attrs.user_agent")

    def run(doc, ctx):
        raw = _read(doc, path, "user_agent", ignore_missing)
        if raw is _MISSING:
            return
        agent = str(raw)
        info: Dict[str, Any] = {"name": "Other", "os": "Other"}
        for name, pattern in _BROWSERS:
            match = re.search(pattern, agent)
            if match:
                info.update(name=name, version=match.group(1))
                break
        for name, pattern in _SYSTEMS:
            if re.search(pattern, agent):
                info["os"] = name
                break
        if _BOT.search(agent):
            info["device"] = "bot"
        elif re.search(r"Mobile|iPhone|Android.*Mobile", agent):
            info["device"] = "mobile"
        elif re.search(r"iPad|Tablet|Android", agent):
            info["device"] = "tablet"
        elif info["os"] in ("Windows", "macOS", "Linux"):
            info["device"] = "desktop"
        else:
            info["device"] = "other"
        info["original"] = agent
        set_path(doc, target, info)
    return run


# -- transform ----------------------------------------------------------------------

@processor("rename")
def _rename(config):
    path, ignore_missing = _field_processor("rename", config)
    target = _required(config, "target_field", "rename")

    def run(doc, ctx):
        value = _read(doc, path, "rename", ignore_missing)
        if value is _MISSING:
            return
        delete_path(doc, path)
        set_path(doc, target, value)
    return run


@processor("set")
def _set(config):
    path = _required(config, "field", "set")
    if "value" not in config and "copy_from" not in config:
        raise ProcessorError("set: give value or copy_from")
    value, source, override = config.get("value"), config.get("copy_from"), config.get("override", True)

    def run(doc, ctx):
        if not override and get_path(doc, path) not in (None, ""):
            return
        set_path(doc, path, get_path(doc, source) if source else render(value, doc))
    return run


@processor("remove")
def _remove(config):
    paths = _required(config, "field", "remove")
    paths = [paths] if isinstance(paths, str) else list(paths)
    ignore_missing = bool(config.get("ignore_missing", False))

    def run(doc, ctx):
        for path in paths:
            if not delete_path(doc, path) and not ignore_missing:
                raise ProcessorError(f"remove: field {path} is missing")
    return run


_TRUE, _FALSE = {"true", "yes", "1", "on", "y", "t"}, {"false", "no", "0", "off", "n", "f"}


def _convert(value: Any, kind: str) -> Any:
    if kind == "integer":
        return int(float(value)) if isinstance(value, str) and "." in value else int(value)
    if kind == "float":
        return float(value)
    if kind == "boolean":
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ValueError(value)
    if kind == "string":
        return str(value)
    if kind == "ip":
        return str(ipaddress.ip_address(str(value).strip()))
    raise ValueError(kind)


@processor("convert")
def _convert_processor(config):
    path, ignore_missing = _field_processor("convert", config)
    kind = config.get("type")
    if kind not in ("integer", "float", "boolean", "string", "ip"):
        raise ProcessorError("convert: type must be integer, float, boolean, string or ip")
    target = config.get("target_field", path)

    def run(doc, ctx):
        value = _read(doc, path, "convert", ignore_missing)
        if value is _MISSING:
            return
        try:
            converted = [_convert(v, kind) for v in value] if isinstance(value, list) else _convert(value, kind)
        except (ValueError, TypeError):
            raise ProcessorError(f"convert: {path}={str(value)[:60]!r} is not a valid {kind}") from None
        set_path(doc, target, converted)
    return run


def _case(name: str, fn):
    def build(config):
        path, ignore_missing = _field_processor(name, config)

        def run(doc, ctx):
            value = _read(doc, path, name, ignore_missing)
            if value is _MISSING:
                return
            set_path(doc, path, [fn(str(v)) for v in value] if isinstance(value, list) else fn(str(value)))
        return run
    PROCESSORS[name] = build


_case("lowercase", str.lower)
_case("uppercase", str.upper)
_case("trim", str.strip)


@processor("split")
def _split(config):
    path, ignore_missing = _field_processor("split", config)
    separator = config.get("separator", ",")
    if not separator:
        raise ProcessorError("split: separator must not be empty")
    target = config.get("target_field", path)

    def run(doc, ctx):
        value = _read(doc, path, "split", ignore_missing)
        if value is _MISSING:
            return
        set_path(doc, target, [part.strip() for part in str(value).split(separator) if part.strip()])
    return run


@processor("script")
def _script(config):
    source = _required(config, "source", "script")
    try:
        program = compile_script(source)
    except ConditionError as e:
        raise ProcessorError(f"script: {e}") from None

    def run(doc, ctx):
        try:
            program(doc)
        except ConditionError as e:
            raise ProcessorError(f"script: {e}") from None
    return run


# -- enrich ---------------------------------------------------------------------------

@processor("geoip")
def _geoip(config):
    path, ignore_missing = _field_processor("geoip", config)
    target = config.get("target", f"attrs.geo.{path.split('.')[-1]}")

    def run(doc, ctx):
        value = _read(doc, path, "geoip", ignore_missing=True)
        if value is _MISSING:
            if not ignore_missing:
                raise ProcessorError(f"geoip: field {path} is missing")
            return
        if ctx.geo is None:
            return  # no GeoIP database configured: nothing to add
        found = ctx.geo.lookup(value)
        if found:
            set_path(doc, target, found)
    return run


@processor("lookup")
def _lookup(config):
    path, ignore_missing = _field_processor("lookup", config)
    table, inline = config.get("table"), config.get("values")
    if not table and not isinstance(inline, dict):
        raise ProcessorError("lookup: give a table name or inline values")
    target = _required(config, "target", "lookup")
    default = config.get("default")
    inline = {str(k).lower(): v for k, v in (inline or {}).items()}

    def run(doc, ctx):
        value = _read(doc, path, "lookup", ignore_missing)
        if value is _MISSING:
            return
        rows = inline if not table else {str(k).lower(): v for k, v in (ctx.tables.get(table) or {}).items()}
        found = rows.get(str(value).strip().lower(), default)
        if found is not None:
            set_path(doc, target, found)
    return run


@processor("threat_intel")
def _threat_intel(config):
    def run(doc, ctx):
        if not ctx.intel:
            return
        from ingest_enrichment import _matches

        hits = _matches(ctx.intel, doc, ctx.now or datetime.now(timezone.utc))
        if hits:
            doc.setdefault("attrs", {})["threat"] = {
                "matched": True, "max_confidence": max(h["confidence"] for h in hits),
                "threat_types": sorted({h["threat_type"] for h in hits}), "indicators": hits}
    return run


# -- privacy ------------------------------------------------------------------------------

_MASKS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "card": re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
    "token": re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b"
                        r"|\bAKIA[0-9A-Z]{16}\b|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
                        r"|\bxox[abpr]-[A-Za-z0-9-]{10,}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


def _luhn(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


@processor("mask")
def _mask(config):
    path, ignore_missing = _field_processor("mask", config)
    kinds = config.get("kinds") or []
    pattern = config.get("pattern")
    if not kinds and not pattern:
        raise ProcessorError("mask: give kinds (email, card, token, ipv4) or a pattern")
    unknown = set(kinds) - set(_MASKS)
    if unknown:
        raise ProcessorError(f"mask: unknown kinds {sorted(unknown)} (one of {sorted(_MASKS)})")
    custom = re.compile(pattern) if pattern else None
    replacement = config.get("replacement")

    def mask_text(text: str) -> str:
        for kind in kinds:
            if kind == "card":
                text = _MASKS[kind].sub(lambda m: (replacement or "[card]") if _luhn(m.group(0)) else m.group(0), text)
            else:
                text = _MASKS[kind].sub(replacement or f"[{kind}]", text)
        if custom:
            text = custom.sub(replacement or "[masked]", text)
        return text

    def run(doc, ctx):
        value = _read(doc, path, "mask", ignore_missing)
        if value is _MISSING:
            return
        set_path(doc, path, mask_text(str(value)))
    return run


@processor("hash")
def _hash(config):
    path, ignore_missing = _field_processor("hash", config)
    method = config.get("method", "sha256")
    if method not in ("sha256", "sha1", "md5", "sha512"):
        raise ProcessorError("hash: method must be sha256, sha512, sha1 or md5")
    salt = str(config.get("salt", ""))
    target = config.get("target_field", path)

    def run(doc, ctx):
        value = _read(doc, path, "hash", ignore_missing)
        if value is _MISSING:
            return
        set_path(doc, target, hashlib.new(method, (salt + str(value)).encode()).hexdigest())
    return run


# -- flow ---------------------------------------------------------------------------------

@processor("drop")
def _drop(config):
    def run(doc, ctx):
        raise DropEvent()
    return run


ROUTE_KEYS = ("retention", "stream")


@processor("route")
def _route(config):
    route = {k: config[k] for k in ROUTE_KEYS if config.get(k)}
    if not route:
        raise ProcessorError("route: give retention and/or stream")
    for key, value in route.items():
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", str(value)):
            raise ProcessorError(f"route: {key} must be letters, digits, . _ or - (max 64)")

    def run(doc, ctx):
        doc["_route"] = dict(route)
    return run


@processor("fail")
def _fail(config):
    message = _required(config, "message", "fail")

    def run(doc, ctx):
        raise ProcessorError(str(render(message, doc)))
    return run
