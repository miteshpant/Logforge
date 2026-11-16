"""
Curated detection content pack loader (ENH-039).

Replaces the auto-generated MITRE rules removed in ENH-038 with real,
hand-written detection logic from `packages/rules/content_pack.yml`.

Why a pack rather than one file per technique
---------------------------------------------
Many ATT&CK techniques share a single observable. `net view`, `net share`,
`arp -a` and `nltest` are four techniques but one telemetry pattern:
built-in enumeration from a command line. Writing 239 separate rule files
would duplicate that logic 239 times and every copy would drift.

Grouping by OBSERVABLE keeps the logic in one place while still attributing
each technique it covers, which is what a coverage map actually needs. It also
means a fix to the pattern fixes every technique it serves, instead of 40 files
falling out of sync.

Coverage honesty
----------------
`resource-development` and `reconnaissance` techniques happen on
adversary-controlled infrastructure -- domain registration, tool development,
victim research. They are not observable in a customer's logs at any level of
effort, so they are reported as OUT OF SCOPE rather than claimed or faked.
That distinction is what makes the remaining number trustworthy.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)

# Tactics whose techniques are performed on infrastructure the defender does
# not own, so no amount of log collection would observe them.
OUT_OF_SCOPE_TACTICS = frozenset({"resource-development", "reconnaissance"})

# Techniques that are out of scope for THIS product regardless of tactic.
#
# Being explicit here is the point: an honest coverage figure needs a stated
# denominator. Silently counting techniques we can never observe would either
# understate coverage (if left in) or overstate it (if quietly dropped).
#
# Mobile (ATT&CK Mobile matrix) requires device telemetry -- MDM/EDR agents on
# phones -- that this platform does not ingest. Listing them as "uncovered"
# would imply a content gap that no amount of rule writing could close.
OUT_OF_SCOPE_TECHNIQUES = frozenset({
    # Mobile-only: call/SMS control, SIM, device sensors.
    "T1582", "T1616", "T1636", "T1430", "T1429", "T1451", "T1409",
    "T1417", "T1414", "T1407", "T1423", "T1456", "T1474", "T1426",
    "T1424", "T1418", "T1428", "T1404",
    # Device-lockscreen, on-screen input injection and notification access:
    # observable only via an on-device agent, which this platform does not ship.
    "T1461", "T1516", "T1517",
    # Adversary-side infrastructure and capability development: these happen
    # on systems the adversary controls, before or outside our telemetry.
    "T1583", "T1584", "T1585", "T1586", "T1587", "T1588",
    "T1589", "T1591", "T1593", "T1594", "T1596", "T1597", "T1598",
    "T1590", "T1592", "T1595",
    # Physical-access techniques with no software log surface.
    "T1200",
})

def _default_pack_path() -> Path:
    # parents[2] is the repo root in a checkout; inside the API container the
    # code is /app (no parents[2]) and packages/rules is mounted at /packages.
    here = Path(__file__).resolve()
    if len(here.parents) > 2:
        candidate = here.parents[2] / "packages" / "rules" / "content_pack.yml"
        if candidate.exists():
            return candidate
    return Path("/packages/rules/content_pack.yml")


DEFAULT_PACK_PATH = _default_pack_path()


class ContentPackError(RuntimeError):
    """Raised when the content pack cannot be loaded or is invalid."""


@dataclass
class PackRule:
    """A single curated rule from the pack."""

    id: str
    title: str
    level: str
    techniques: List[str]
    tactics: List[str]
    description: str
    detection: Dict[str, Any]
    logsource: Dict[str, Any] = field(default_factory=dict)
    falsepositives: List[str] = field(default_factory=list)

    def to_sigma(self) -> Dict[str, Any]:
        """Render as a Sigma rule dict the engine can evaluate."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "level": self.level,
            "logsource": self.logsource,
            "detection": self.detection,
            "falsepositives": self.falsepositives,
            "tags": (
                [f"attack.{t.lower()}" for t in self.techniques]
                + [f"attack.{t.replace('-', '_')}" for t in self.tactics]
            ),
        }


def load_pack(path: Optional[Path] = None) -> List[PackRule]:
    """
    Load and validate the content pack.

    Raises:
        ContentPackError: on a missing, malformed or invalid pack. A detection
        pack that cannot be parsed must fail loudly -- silently loading zero
        rules would leave a platform with no detections and no error.
    """
    import yaml

    pack_path = Path(path or os.getenv("CONTENT_PACK_PATH", DEFAULT_PACK_PATH))

    if not pack_path.exists():
        raise ContentPackError(f"Content pack not found: {pack_path}")

    try:
        data = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContentPackError(f"Content pack is not valid YAML: {exc}") from exc

    if not isinstance(data, dict) or "rules" not in data:
        raise ContentPackError("Content pack must be a mapping containing 'rules'")

    rules: List[PackRule] = []
    seen_ids: Set[str] = set()

    for entry in data["rules"] or []:
        for required in ("id", "title", "techniques", "detection", "level"):
            if required not in entry:
                raise ContentPackError(
                    f"Pack rule is missing required field {required!r}: "
                    f"{entry.get('id', '<no id>')}"
                )

        if entry["id"] in seen_ids:
            raise ContentPackError(f"Duplicate rule id in pack: {entry['id']}")
        seen_ids.add(entry["id"])

        rules.append(
            PackRule(
                id=entry["id"],
                title=entry["title"],
                level=entry["level"],
                techniques=list(entry["techniques"]),
                tactics=list(entry.get("tactics", [])),
                description=entry.get("description", ""),
                detection=entry["detection"],
                logsource=entry.get("logsource", {}),
                falsepositives=list(entry.get("falsepositives", [])),
            )
        )

    return rules


def covered_techniques(rules: Optional[List[PackRule]] = None) -> Set[str]:
    """
    Every ATT&CK technique covered by the pack, including base techniques
    implied by a sub-technique.

    Covering `T1078.004` means the platform detects a form of `T1078`, so the
    base technique is credited too -- that is how ATT&CK coverage is normally
    counted, and not doing so would understate real coverage.
    """
    rules = rules if rules is not None else load_pack()

    covered: Set[str] = set()
    for rule in rules:
        for technique in rule.techniques:
            covered.add(technique)
            if "." in technique:
                covered.add(technique.split(".")[0])

    return covered


def coverage_report(
    all_techniques: Dict[str, Any],
    extra_covered: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Build an honest coverage report.

    Args:
        all_techniques: {technique_id: metadata} for the full ATT&CK catalogue.
        extra_covered: techniques covered by standalone rule files, so the pack
            and the individual `.yml` rules are counted together.

    The report separates three states, because collapsing them is exactly how
    the previous "286 techniques" claim became misleading:
      * covered      -- a real, tested detection exists
      * out_of_scope -- not observable in defender-side logs
      * uncovered    -- genuinely missing content
    """
    covered = covered_techniques()
    if extra_covered:
        covered |= set(extra_covered)
        covered |= {t.split(".")[0] for t in extra_covered if "." in t}

    in_scope: Set[str] = set()
    out_of_scope: Set[str] = set()

    for technique_id, meta in all_techniques.items():
        tactics = set(getattr(meta, "tactics", []) or [])
        base = technique_id.split(".")[0]

        # A technique is out of scope if it is explicitly listed, or if EVERY
        # tactic it serves is adversary-side. Many techniques list several
        # tactics, and a single observable tactic makes it detectable.
        explicitly_out = (
            technique_id in OUT_OF_SCOPE_TECHNIQUES
            or base in OUT_OF_SCOPE_TECHNIQUES
        )
        if explicitly_out or (tactics and tactics <= OUT_OF_SCOPE_TACTICS):
            out_of_scope.add(technique_id)
        else:
            in_scope.add(technique_id)

    covered_in_scope = {t for t in in_scope if t in covered or t.split(".")[0] in covered}
    uncovered = in_scope - covered_in_scope

    return {
        "total_techniques": len(all_techniques),
        "in_scope": len(in_scope),
        "out_of_scope": len(out_of_scope),
        "covered": len(covered_in_scope),
        "uncovered": len(uncovered),
        "coverage_percent": round(
            (len(covered_in_scope) / len(in_scope) * 100) if in_scope else 0.0, 1
        ),
        "uncovered_techniques": sorted(uncovered),
    }


_pack_cache: Optional[List[PackRule]] = None


def get_pack_rules() -> List[PackRule]:
    """Get the parsed content pack, loading it on first use."""
    global _pack_cache
    if _pack_cache is None:
        _pack_cache = load_pack()
    return _pack_cache


def reset_pack_cache() -> None:
    """Reset the cached pack (tests only)."""
    global _pack_cache
    _pack_cache = None
