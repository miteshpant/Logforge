"""
Default Detection Content Loader

Loads the platform's default detection library into `sigma_rules_mt`:

1. **Vendored SigmaHQ rules** (LF-005) from `content/rules/` — genuine,
   upstream-curated Sigma detections pinned to a specific SigmaHQ commit
   (see `content/rules/MANIFEST.md`). Field names are translated to the
   normalized vocabulary of `config/field_mapping.yml` at load time so the
   sigma engine can evaluate them against normalized logs.
2. **Metadata-synthesised MITRE rules** (ENH-038) — for the small set of
   techniques whose catalogue metadata supports a discriminating selection.

Every candidate rule — vendored or generated — must pass the same gate before
insertion (LF-005):

* a true-positive fixture synthesised from the rule's own detection logic must
  FIRE through the real engine evaluator, and
* the rule must stay SILENT on a benign event corpus (ordinary logons, web
  requests, cron/service activity).

Rules failing either check are reported as `awaiting_content`, never inserted.
The verified fixtures are stored inside `rule_content.fixtures` so coverage
reporting (LF-040) can distinguish fixture-tested rules from anything else.

Tenancy sentinel (LF-003): platform-default rules are stored with
`customer_id = 'default'` — the one sentinel the read path
(`SecurityDAO.get_sigma_rules`) already expects. The column is a non-nullable
String, so the previous `None` / `IS NULL` variants could never round-trip.

Idempotency (LF-004): existing default rule ids are fetched once per run and
only missing rules are inserted, so restarting the API never grows the table.
"""

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from mitre_metadata_generator import generate_production_metadata
from database_layer import DatabaseLayer

logger = structlog.get_logger(__name__)

# LF-003: the single tenancy sentinel for platform-provided rules. This is what
# the read path (`security_dao.get_sigma_rules`) matches; nothing may write any
# other sentinel ('', NULL) for default content.
DEFAULT_RULE_TENANT = "default"

# Vendored detection content (LF-005). See content/rules/MANIFEST.md for the
# pinned upstream commit and the selection criteria.
CONTENT_RULES_DIR = Path(__file__).resolve().parent / "content" / "rules"
SIGMAHQ_PINNED_COMMIT = "3c0d35188942eb6a8c373e4f4973ac7e84116993"

# SigmaHQ field name -> LogForge normalized field name. The normalizer
# (`services/high_performance_normalizer.py` + `config/field_mapping.yml`)
# emits the right-hand names, so rules must reference those to ever match.
SIGMA_FIELD_TRANSLATION = {
    "Image": "process_name",
    "CommandLine": "command_line",
    "User": "user",
    "TargetUsername": "user",
    "Computer": "hostname",
    "ComputerName": "hostname",
    "SourceIp": "src_ip",
    "SourceIP": "src_ip",
    "DestinationIp": "dst_ip",
    "DestinationIP": "dst_ip",
    "DestinationPort": "port",
    "SourcePort": "src_port",
    "Protocol": "protocol",
    "TargetFilename": "file_path",
    "c-ip": "src_ip",
    "cs-ip": "src_ip",
    "c-uri": "url",
    "cs-uri": "url",
    "cs-uri-stem": "url",
    "cs-uri-query": "url",
    "c-useragent": "user_agent",
    "cs-user-agent": "user_agent",
    "cs-method": "http_method",
    "sc-status": "status_code",
    # Already-normalized names pass through unchanged.
    "user": "user",
    "src_ip": "src_ip",
    "dst_ip": "dst_ip",
    "message": "message",
    "event_type": "event_type",
    "process_name": "process_name",
    "command_line": "command_line",
    "file_name": "file_name",
    "file_path": "file_path",
    "port": "port",
    "src_port": "src_port",
    "protocol": "protocol",
    "service": "service",
    "hostname": "hostname",
    "url": "url",
    "user_agent": "user_agent",
    "http_method": "http_method",
    "status_code": "status_code",
    "query": "query",
    "md5": "md5",
    "sha1": "sha1",
    "sha256": "sha256",
}

# Modifiers `SigmaFieldMatcher` can evaluate. `re` is Sigma's name for what the
# engine calls `regex`; it is renamed during translation.
SUPPORTED_SIGMA_MODIFIERS = {
    "contains", "all", "startswith", "endswith", "re", "regex",
    "gt", "gte", "lt", "lte",
}

_TECHNIQUE_TAG_RE = re.compile(r"^attack\.(t\d{4}(?:\.\d{3})?)$", re.IGNORECASE)

# Benign traffic every default rule must stay silent on (LF-005). One benign
# Windows logon used to trigger 92 rules; this corpus is the regression gate.
BENIGN_EVENTS: List[Dict[str, Any]] = [
    {   # Ordinary interactive Windows logon (the historical failure mode).
        "event_id": 4624,
        "process_name": "C:\\Windows\\explorer.exe",
        "command_line": "C:\\Windows\\explorer.exe",
        "user": "alice",
        "hostname": "WS-042",
        "status": "success",
        "event_type": "login_success",
        "message": "An account was successfully logged on",
    },
    {   # Routine scheduled PowerShell maintenance script.
        "process_name": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "command_line": "powershell.exe -File C:\\scripts\\backup.ps1",
        "user": "svc_backup",
        "hostname": "WS-042",
        "message": "Process created",
    },
    {   # Linux cron heartbeat.
        "process_name": "/usr/sbin/cron",
        "command_line": "/usr/sbin/CRON -f",
        "user": "root",
        "hostname": "app-01",
        "message": "pam_unix(cron:session): session opened for user root",
    },
    {   # Successful SSH login.
        "process_name": "/usr/sbin/sshd",
        "command_line": "sshd: alice [priv]",
        "user": "alice",
        "hostname": "app-01",
        "event_type": "login_success",
        "message": "Accepted publickey for alice from 10.0.0.8 port 51234 ssh2",
    },
    {   # Routine package update by an operator.
        "process_name": "/usr/bin/apt-get",
        "command_line": "apt-get update",
        "user": "root",
        "hostname": "app-01",
        "message": "Reading package lists",
    },
    {   # Ordinary web request.
        "url": "/index.html",
        "http_method": "GET",
        "status_code": 200,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "src_ip": "10.0.0.5",
        "message": "GET /index.html HTTP/1.1 200",
    },
]


class MitreDefaultLoader:
    """Loads the default detection library (vendored Sigma + MITRE metadata rules)"""

    def __init__(self):
        import os
        service_key = os.getenv('MITRE_DEFAULT_LOADER_KEY', 'mitre-default-loader-service-key')
        self.database = DatabaseLayer("MitreDefaultLoader", service_key)
        self._condition_evaluator = None

    # ------------------------------------------------------------------
    # Detection evaluation helpers (shared gate for every candidate rule)
    # ------------------------------------------------------------------

    def _get_condition_evaluator(self):
        """Lazily import the real engine evaluator (keeps module importable offline)."""
        if self._condition_evaluator is None:
            from sigma_engine import SigmaConditionEvaluator
            self._condition_evaluator = SigmaConditionEvaluator()
        return self._condition_evaluator

    def _rule_matches(self, detection: Dict[str, Any], event: Dict[str, Any]) -> bool:
        """Evaluate a detection block against an event with the REAL engine logic."""
        from sigma_condition import SigmaConditionError, evaluate_condition

        evaluator = self._get_condition_evaluator()
        blocks = {
            name: block for name, block in detection.items()
            if name != "condition" and isinstance(block, dict)
        }
        if not blocks:
            return False

        results = {
            name: evaluator.evaluate_selection(event, block)[0]
            for name, block in blocks.items()
        }
        try:
            return evaluate_condition(detection.get("condition", "selection"), results)
        except SigmaConditionError:
            return False

    def _synthesize_true_positive(self, detection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build an event that satisfies the rule's own detection logic.

        Best-effort construction over combinations of the rule's positive
        selection blocks; the REAL engine evaluation is the arbiter, so an
        event is only returned if the full condition actually fires on it.
        Returns None when no verifiable true positive can be built — the
        caller must then refuse to ship the rule.
        """
        blocks = {
            name: block for name, block in detection.items()
            if name != "condition" and isinstance(block, dict)
        }
        positive = [name for name in blocks if not name.startswith("filter")]
        if not positive:
            return None

        candidates: List[List[str]] = []
        if len(positive) > 1:
            candidates.append(positive)
        candidates.extend([[name] for name in positive])
        if 2 < len(positive) <= 8:
            candidates.extend(list(combo) for combo in combinations(positive, 2))

        for combo in candidates:
            event = self._build_event_for_blocks([blocks[name] for name in combo])
            if event is not None and self._rule_matches(detection, event):
                return event
        return None

    def _build_event_for_blocks(self, selected_blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Merge the field constraints of the given blocks into one candidate event."""
        # base field -> {"eq": v, "startswith": [..], "contains": [..], "endswith": [..], "numeric": v}
        constraints: Dict[str, Dict[str, Any]] = {}

        for block in selected_blocks:
            for field_expr, value in block.items():
                parts = str(field_expr).split("|")
                base, modifiers = parts[0], parts[1:]
                require_all = "all" in modifiers
                operator = next(
                    (m for m in modifiers if m != "all"), "eq"
                )
                values = value if isinstance(value, list) else [value]
                if not values:
                    return None
                chosen = values if require_all else values[:1]

                slot = constraints.setdefault(
                    base, {"eq": None, "startswith": [], "contains": [], "endswith": [], "numeric": None}
                )
                for v in chosen:
                    if operator == "eq":
                        if slot["eq"] is not None and slot["eq"] != v:
                            return None  # conflicting exact values
                        slot["eq"] = v
                    elif operator in ("startswith", "contains", "endswith"):
                        slot[operator].append(str(v))
                    elif operator in ("regex",):
                        # Best effort: treat the pattern as a literal; the
                        # engine check decides whether it actually matches.
                        slot["contains"].append(str(v))
                    elif operator in ("gt", "gte", "lt", "lte"):
                        try:
                            n = float(v)
                        except (TypeError, ValueError):
                            return None
                        if operator == "gt":
                            n += 1
                        elif operator == "lt":
                            n -= 1
                        slot["numeric"] = n
                    else:
                        return None

        event: Dict[str, Any] = {}
        for base, slot in constraints.items():
            if slot["eq"] is not None:
                event[base] = slot["eq"]
            elif slot["numeric"] is not None:
                numeric = slot["numeric"]
                event[base] = int(numeric) if float(numeric).is_integer() else numeric
            else:
                prefix = slot["startswith"][0] if slot["startswith"] else ""
                suffix = slot["endswith"][0] if slot["endswith"] else ""
                middle = " ".join(slot["contains"])
                composed = " ".join(part for part in (prefix, middle) if part)
                event[base] = (composed + " " + suffix).strip() if suffix else composed
                if not event[base]:
                    return None
        return event or None

    def _validate_detection(self, detection: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        The LF-005 shipping gate.

        Returns (fixtures, None) when the rule fires on a synthesised true
        positive and stays silent on the benign corpus; (None, reason)
        otherwise. Rules without verified fixtures are never inserted.
        """
        true_positive = self._synthesize_true_positive(detection)
        if true_positive is None:
            return None, "no verifiable true-positive fixture could be synthesised"

        for benign in BENIGN_EVENTS:
            if self._rule_matches(detection, benign):
                return None, "fires on the benign event corpus"

        return {
            "true_positive": true_positive,
            "true_negative": BENIGN_EVENTS[0],
        }, None

    # ------------------------------------------------------------------
    # Vendored SigmaHQ content (LF-005)
    # ------------------------------------------------------------------

    def _translate_detection(self, detection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Translate a vendored Sigma detection block to the engine's vocabulary.

        Returns None when any field or modifier cannot be represented
        faithfully — a partially-translated rule would silently change
        semantics, which is worse than not loading it.
        """
        translated: Dict[str, Any] = {}
        for name, block in detection.items():
            if name == "condition":
                translated[name] = block
                continue
            if not isinstance(block, dict) or not block:
                return None
            new_block: Dict[str, Any] = {}
            for field_expr, value in block.items():
                parts = str(field_expr).split("|")
                base = SIGMA_FIELD_TRANSLATION.get(parts[0])
                if base is None:
                    return None
                modifiers = parts[1:]
                if any(m not in SUPPORTED_SIGMA_MODIFIERS for m in modifiers):
                    return None
                modifiers = ["regex" if m == "re" else m for m in modifiers]
                if value is None or isinstance(value, dict):
                    return None
                if isinstance(value, list) and any(
                    v is None or isinstance(v, (dict, list)) for v in value
                ):
                    return None
                new_expr = "|".join([base] + modifiers)
                if new_expr in new_block:
                    # Two source fields collapse onto one normalized field
                    # inside a single AND block; merging would corrupt the
                    # logic, so the rule is rejected.
                    return None
                new_block[new_expr] = value
            translated[name] = new_block
        if "condition" not in translated:
            translated["condition"] = "selection"
        return translated

    def _content_rule_to_row(self, rule: Any, path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Convert one vendored rule file into a validated sigma_rules_mt row."""
        if not isinstance(rule, dict):
            return None, "not a mapping"
        title = rule.get("title")
        detection = rule.get("detection")
        level = rule.get("level")
        if not title or not isinstance(detection, dict):
            return None, "missing title or detection"
        if level not in ("low", "medium", "high", "critical"):
            return None, f"unsupported level {level!r}"

        tags = [str(t) for t in (rule.get("tags") or [])]
        techniques = [
            m.group(1).upper()
            for m in (_TECHNIQUE_TAG_RE.match(t) for t in tags)
            if m
        ]
        if not techniques:
            return None, "no MITRE technique tag"
        tactics = [
            t.split(".", 1)[1]
            for t in tags
            if t.lower().startswith("attack.") and not _TECHNIQUE_TAG_RE.match(t)
        ]

        translated = self._translate_detection(detection)
        if translated is None:
            return None, "untranslatable field or modifier"

        fixtures, reason = self._validate_detection(translated)
        if fixtures is None:
            return None, reason

        upstream_id = rule.get("id") or hashlib.sha1(path.name.encode()).hexdigest()[:32]
        rule_content = {
            "detection": translated,
            "logsource": rule.get("logsource", {}),
            "tags": tags,
            "kill_chain_phases": tactics,
            "references": rule.get("references", []),
            "falsepositives": rule.get("falsepositives", []),
            "author": rule.get("author", "SigmaHQ"),
            "date": str(rule.get("date", "")),
            "fixtures": fixtures,
            "source": {
                "origin": "SigmaHQ",
                "commit": SIGMAHQ_PINNED_COMMIT,
                "file": str(path.relative_to(CONTENT_RULES_DIR)),
            },
        }
        return {
            "id": f"sigma_default_{upstream_id}",
            "customer_id": DEFAULT_RULE_TENANT,
            "name": str(title),
            "description": str(rule.get("description", "")),
            "rule_content": json.dumps(rule_content),
            "mitre_techniques": techniques,
            "severity": level,
            "is_enabled": True,
            "created_by": "system",
        }, None

    def _load_content_rules(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Parse, translate and validate every vendored rule file."""
        import yaml

        rows: List[Dict[str, Any]] = []
        awaiting: List[str] = []

        if not CONTENT_RULES_DIR.exists():
            logger.warning(f"Content rules directory not found: {CONTENT_RULES_DIR}")
            return rows, awaiting

        for path in sorted(CONTENT_RULES_DIR.rglob("*.yml")):
            try:
                rule = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                logger.error(f"Invalid YAML in vendored rule {path.name}: {exc}")
                awaiting.append(f"{path.name}: invalid YAML")
                continue
            row, reason = self._content_rule_to_row(rule, path)
            if row is None:
                logger.warning(f"Vendored rule not loadable ({reason}): {path.name}")
                awaiting.append(f"{path.name}: {reason}")
                continue
            rows.append(row)

        return rows, awaiting

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def load_default_mitre_rules(self) -> Dict[str, Any]:
        """
        Load the default detection library idempotently.

        Returns:
            Dict with loading results
        """
        try:
            logger.info("🚀 Loading default detection library into database...")

            # 1. Vendored SigmaHQ content (the real detection library, LF-005).
            content_rows, awaiting_content = self._load_content_rules()
            logger.info(
                f"📦 Vendored content: {len(content_rows)} rules validated, "
                f"{len(awaiting_content)} awaiting content"
            )

            # 2. Metadata-synthesised technique rules (ENH-038) — same gate.
            metadata = generate_production_metadata()
            generated_rows: List[Dict[str, Any]] = []
            for technique_id, meta in metadata.items():
                try:
                    rule_id = f"mitre_default_{technique_id.lower()}"
                    sigma_rule = self._create_default_sigma_rule(rule_id, technique_id, meta)
                    if sigma_rule is None:
                        # No synthesisable detection logic for this technique.
                        awaiting_content.append(technique_id)
                        continue

                    rule_content = json.loads(sigma_rule["rule_content"])
                    fixtures, reason = self._validate_detection(rule_content["detection"])
                    if fixtures is None:
                        # Generated logic that cannot prove a true positive or
                        # that fires on benign traffic is noise, not coverage.
                        awaiting_content.append(f"{technique_id}: {reason}")
                        continue
                    rule_content["fixtures"] = fixtures
                    sigma_rule["rule_content"] = json.dumps(rule_content)
                    generated_rows.append(sigma_rule)
                except Exception as e:
                    logger.error(f"Failed to build rule for {technique_id}: {e}")
                    awaiting_content.append(f"{technique_id}: {e}")
                    continue

            all_rows = content_rows + generated_rows
            total_candidates = len(all_rows) + len(awaiting_content)

            # 3. Idempotent reconciliation (LF-004): fetch existing ids once,
            #    insert only what is missing.
            existing_ids = await self._existing_default_rule_ids()

            loaded_count = 0
            inserted_count = 0
            failed_count = 0
            for row in all_rows:
                if row["id"] in existing_ids:
                    loaded_count += 1
                    continue
                if await self._insert_default_sigma_rule(row):
                    loaded_count += 1
                    inserted_count += 1
                    if inserted_count % 50 == 0:
                        logger.info(f"📈 Inserted {inserted_count} new default rules...")
                else:
                    failed_count += 1

            # 4. Refresh Redis cache with the current default rule set.
            logger.info("💾 Refreshing Redis cache with default rules...")
            cache_success = await self._refresh_default_cache()

            result = {
                "status": "success",
                "total_techniques": total_candidates,
                "rules_loaded": loaded_count,
                "rules_inserted": inserted_count,
                "rules_failed": failed_count,
                # Techniques/files with no fixture-verified detection are
                # reported explicitly, so coverage numbers stay honest and the
                # content gap is visible rather than disguised by placeholders.
                "awaiting_content": len(awaiting_content),
                "awaiting_content_techniques": awaiting_content,
                "cache_refreshed": cache_success,
                "success_rate": (loaded_count / total_candidates) * 100 if total_candidates else 0
            }

            logger.info(
                f"✅ Default detection library loading complete: {loaded_count} rules present "
                f"({inserted_count} newly inserted, {failed_count} failed, "
                f"{len(awaiting_content)} awaiting content)"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Failed to load default detection library: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "rules_loaded": 0,
                "rules_failed": 0
            }

    # ------------------------------------------------------------------
    # Metadata-synthesised rules (ENH-038 — public API pinned by tests)
    # ------------------------------------------------------------------

    def _create_default_sigma_rule(self, rule_id: str, technique_id: str, metadata) -> Optional[Dict[str, Any]]:
        """
        Create a default sigma rule from MITRE metadata.

        Returns None when the technique has no synthesisable detection logic
        (ENH-038). The caller skips it and counts it as awaiting content, rather
        than shipping a rule that cannot discriminate.
        """
        # Generate detection logic
        detection_logic = self._generate_detection_logic(metadata)
        if detection_logic is None:
            return None

        # Create rule dictionary matching sigma_rules_mt schema
        rule_content = {
            "detection": detection_logic,
            "tags": self._generate_tags(metadata),
            "logsource": self._generate_logsource(metadata.platforms),
            "kill_chain_phases": metadata.kill_chain_phases,
            "data_sources": metadata.data_sources,
            "log_fields": metadata.log_fields,
            "detection_patterns": metadata.detection_patterns
        }

        rule = {
            "id": rule_id,
            # LF-003: one sentinel for platform rules — the string 'default'.
            "customer_id": DEFAULT_RULE_TENANT,
            "name": f"MITRE {technique_id}: {metadata.name}",
            "description": metadata.description,
            "rule_content": json.dumps(rule_content),
            "mitre_techniques": [technique_id],
            "severity": metadata.severity,
            "is_enabled": True,
            "created_by": "system",
        }

        return rule

    def _generate_detection_logic(self, metadata) -> Optional[Dict[str, Any]]:
        """
        Synthesise sigma detection logic from technique metadata, if possible.

        Returns None when the metadata does not support a discriminating
        selection -- which, measured across the current catalogue, is every
        technique. That is the honest answer: a technique NAME and a generic
        "Activity pattern associated with X" string do not contain enough
        information to build a detection.

        Real detection content lives in `content/rules/` (vendored SigmaHQ)
        and `packages/rules/`, written and fixture-tested by hand. This
        generator's job is coverage METADATA (tactics, platforms, data
        sources), not detections.
        """
        selection = {}

        # Generate selection based on log fields and detection patterns
        if "process_name" in metadata.log_fields:
            # Look for suspicious process names from detection patterns
            process_patterns = []
            for pattern in metadata.detection_patterns:
                if "powershell" in pattern.lower():
                    process_patterns.extend(["powershell.exe", "pwsh.exe"])
                elif "wmi" in pattern.lower():
                    process_patterns.extend(["wmic.exe", "wmiprvse.exe"])
                elif "cmd" in pattern.lower():
                    process_patterns.append("cmd.exe")

            if process_patterns:
                selection["process_name"] = process_patterns[:3]  # Limit to 3

        if "command_line" in metadata.log_fields:
            # Add command line patterns
            cmd_patterns = []
            for pattern in metadata.detection_patterns:
                if "powershell" in pattern.lower():
                    cmd_patterns.extend(["-enc", "-command", "DownloadString", "IEX"])
                elif "wmi" in pattern.lower():
                    cmd_patterns.extend(["Get-WmiObject", "Invoke-WmiMethod"])
                elif "registry" in pattern.lower():
                    cmd_patterns.extend(["reg add", "Set-ItemProperty"])

            if cmd_patterns:
                selection["command_line|contains"] = cmd_patterns[:3]

        # ENH-038: the generic fallbacks that used to live here produced rules
        # with NO discriminating power, and measurement showed how bad it was:
        #
        #   * 92 rules selected only `event_id in [4688,4624,4625,1]`. Those
        #     fired on an ordinary user logon AND on real malicious PowerShell
        #     identically -- 92 alerts per benign event, zero information.
        #   * 194 rules selected `process_name contains "suspicious"`, which
        #     matches essentially nothing, so they were dead content.
        #
        # A technique NAME does not contain enough information to synthesise
        # real detection logic. Emitting a rule anyway is worse than emitting
        # none: it inflates a coverage number while generating alert fatigue,
        # which is precisely how customers learn to ignore a SIEM.
        #
        # We now return None when there is no discriminating selection. The
        # caller records the technique as AWAITING CONTENT, so coverage
        # reporting stays honest and the gap is visible instead of disguised.
        if not selection:
            return None

        return {
            "selection": selection,
            "condition": "selection"
        }

    def _generate_tags(self, metadata) -> List[str]:
        """Generate tags for the sigma rule"""
        tags = ["mitre_attack", "default_rule"]
        tags.extend(metadata.tactics)
        tags.extend(metadata.platforms)
        tags.append(f"severity_{metadata.severity}")
        return tags

    def _generate_logsource(self, platforms: List[str]) -> Dict[str, Any]:
        """Generate logsource configuration"""
        if "Windows" in platforms:
            return {"product": "windows", "service": "security"}
        elif "Linux" in platforms:
            return {"product": "linux", "service": "syslog"}
        elif "Cloud" in platforms:
            return {"product": "aws", "service": "cloudtrail"}
        else:
            return {"product": "generic", "service": "system"}

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------

    async def _existing_default_rule_ids(self) -> set:
        """Ids of platform-default rules already present (LF-004 idempotency)."""
        result = await self.database.execute_query(
            """
            SELECT id FROM sigma_rules_mt
            WHERE customer_id = %(customer_id)s AND created_by = 'system'
            """,
            {"customer_id": DEFAULT_RULE_TENANT},
        )
        return {row["id"] for row in result or []}

    async def _insert_default_sigma_rule(self, rule: Dict[str, Any]) -> bool:
        """Insert a default sigma rule into the database (parameterized)."""
        try:
            now = datetime.now(timezone.utc)
            await self.database.execute_update(
                """
                INSERT INTO sigma_rules_mt (
                    id, customer_id, name, description, rule_content, mitre_techniques,
                    severity, is_enabled, created_by, created_at, updated_at
                ) VALUES (
                    %(id)s, %(customer_id)s, %(name)s, %(description)s, %(rule_content)s,
                    %(mitre_techniques)s, %(severity)s, %(is_enabled)s, %(created_by)s,
                    %(created_at)s, %(updated_at)s
                )
                """,
                {
                    "id": rule["id"],
                    "customer_id": rule["customer_id"],
                    "name": rule["name"],
                    "description": rule["description"],
                    "rule_content": rule["rule_content"],
                    "mitre_techniques": rule["mitre_techniques"],
                    "severity": rule["severity"],
                    "is_enabled": 1 if rule["is_enabled"] else 0,
                    "created_by": rule["created_by"],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            return True

        except Exception as e:
            logger.error(f"Error inserting default rule {rule['id']}: {e}")
            return False

    async def _refresh_default_cache(self) -> bool:
        """Refresh Redis cache with default rules"""
        try:
            from dependencies import get_sigma_rule_cache

            sigma_cache = get_sigma_rule_cache()
            if not sigma_cache:
                logger.warning("Sigma rule cache not available")
                return False

            # Force refresh of default rules cache
            await sigma_cache.invalidate_default_cache()

            # Get default rules from database and cache them
            default_rules = await self._get_default_rules_from_db()
            if default_rules:
                await sigma_cache._cache_default_rules(default_rules)
                logger.info(f"✅ Cached {len(default_rules)} default rules in Redis")
                return True
            else:
                logger.warning("No default rules found to cache")
                return False

        except Exception as e:
            logger.error(f"Error refreshing default cache: {e}")
            return False

    async def _get_default_rules_from_db(self) -> List[Dict[str, Any]]:
        """Get default rules from database"""
        try:
            result = await self.database.execute_query(
                """
                SELECT id, customer_id, name, description, rule_content, mitre_techniques,
                       severity, is_enabled, false_positive_rate, created_by, created_at, updated_at
                FROM sigma_rules_mt
                WHERE customer_id = %(customer_id)s
                AND is_enabled = 1
                ORDER BY id
                """,
                {"customer_id": DEFAULT_RULE_TENANT},
            )

            # Convert result to list of dictionaries
            rules = []
            for row in result:
                rule_dict = dict(row)

                # Parse JSON fields for new schema
                try:
                    # Parse the rule_content JSON which contains the sigma rule definition
                    if rule_dict["rule_content"]:
                        content = json.loads(rule_dict["rule_content"])
                        rule_dict["detection"] = content.get("detection", {})
                        rule_dict["tags"] = content.get("tags", [])
                        rule_dict["logsource"] = content.get("logsource", {})
                        rule_dict["kill_chain_phases"] = content.get("kill_chain_phases", [])
                        rule_dict["data_sources"] = content.get("data_sources", [])
                        rule_dict["log_fields"] = content.get("log_fields", [])
                        rule_dict["detection_patterns"] = content.get("detection_patterns", [])

                    # Map new schema fields to expected format
                    rule_dict["title"] = rule_dict["name"]  # For backward compatibility
                    rule_dict["attack_techniques"] = rule_dict["mitre_techniques"]
                    rule_dict["enabled"] = bool(rule_dict["is_enabled"])
                    # The platform owns default rules; expose no tenant owner
                    # so cache bucketing treats them as defaults.
                    rule_dict["customer_id"] = ""

                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON fields for rule {rule_dict['id']}: {e}")
                    continue

                rules.append(rule_dict)

            return rules

        except Exception as e:
            logger.error(f"Error getting default rules from database: {e}")
            return []

    async def verify_default_rules(self) -> Dict[str, Any]:
        """Verify that default rules are properly loaded"""
        try:
            # What the content directory can actually provide right now.
            content_rows, awaiting = self._load_content_rules()
            expected = len(content_rows)

            # Check database
            db_count = await self.database.execute_query(
                """
                SELECT count(*) as count FROM sigma_rules_mt
                WHERE customer_id = %(customer_id)s AND created_by = 'system'
                """,
                {"customer_id": DEFAULT_RULE_TENANT},
            )
            db_rules_count = db_count[0]["count"] if db_count else 0

            # Check Redis cache
            cache_count = 0
            try:
                from dependencies import get_sigma_rule_cache
                sigma_cache = get_sigma_rule_cache()
                if sigma_cache:
                    default_rules = await sigma_cache.get_default_rules()
                    cache_count = len(default_rules)
            except Exception as e:
                logger.error(f"Error checking cache: {e}")

            return {
                "database_rules": db_rules_count,
                "cached_rules": cache_count,
                "expected_rules": expected,
                "awaiting_content": len(awaiting),
                "database_complete": db_rules_count >= expected,
                "cache_complete": cache_count >= expected,
                "system_ready": db_rules_count >= expected and cache_count >= expected
            }

        except Exception as e:
            logger.error(f"Error verifying default rules: {e}")
            return {
                "error": str(e),
                "system_ready": False
            }


# Singleton instance
# ENH-010: `MitreDefaultLoader()` opens a database connection in its constructor, so
# building it here connected during import and made this module untestable
# offline. Built on first use; the PEP 562 hook preserves the `mitre_default_loader` name.
_mitre_default_loader_instance = None


def get_mitre_default_loader() -> "MitreDefaultLoader":
    """Get the shared MitreDefaultLoader, constructing it on first use."""
    global _mitre_default_loader_instance
    if _mitre_default_loader_instance is None:
        _mitre_default_loader_instance = MitreDefaultLoader()
    return _mitre_default_loader_instance


def __getattr__(name: str):
    if name == "mitre_default_loader":
        return get_mitre_default_loader()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def load_mitre_default_rules() -> Dict[str, Any]:
    """
    Main entry point to load default MITRE rules

    Returns:
        Dict with loading results
    """
    return await get_mitre_default_loader().load_default_mitre_rules()


async def verify_mitre_default_rules() -> Dict[str, Any]:
    """
    Verify that default MITRE rules are loaded

    Returns:
        Dict with verification results
    """
    return await get_mitre_default_loader().verify_default_rules()


if __name__ == "__main__":
    # Test loading default rules
    async def test_default_loading():
        print("🧪 Testing default detection library loader...")

        # Load default rules
        result = await load_mitre_default_rules()
        print(f"✅ Loading result: {result}")

        # Verify rules
        verification = await verify_mitre_default_rules()
        print(f"📊 Verification: {verification}")

        print("🎉 Test complete!")

    # Run test
    asyncio.run(test_default_loading())
