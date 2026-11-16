#!/usr/bin/env python3
"""Export the Logforge API's OpenAPI spec to docs/api/openapi.json and .yaml.

Both files hold the same document; YAML is the form most API tooling and
reviewers expect, JSON is what Redoc (docs/api/index.html) loads.

The FastAPI app imports without live infrastructure (see
tests/test_offline_app_import.py), so this runs anywhere the API's Python
dependencies are installed:

    pip install -r apps/api/requirements.txt
    python scripts/export_openapi.py          # write the spec
    python scripts/export_openapi.py --check  # fail if a committed spec is stale
"""

import json
import logging
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "api" / "openapi.json"
OUT_YAML = OUT.with_suffix(".yaml")


def build_spec() -> dict:
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    import main  # noqa: E402  (path set above)

    spec = main.app.openapi()
    spec["servers"] = [{"url": "http://localhost:7080", "description": "Local Docker Compose stack"}]
    return spec


def render(spec: dict) -> dict:
    """The committed files, keyed by path."""
    import yaml

    as_json = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    # Dump the JSON round-trip so both files describe exactly the same data.
    # Nested keys stay sorted (stable diffs); top-level keys follow the usual
    # OpenAPI order so the file opens with `openapi` and `info`.
    data = json.loads(as_json)
    first = ["openapi", "info", "servers", "tags", "paths", "components"]
    ordered = {k: data[k] for k in first if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    as_yaml = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, width=100)
    return {OUT: as_json, OUT_YAML: as_yaml}


def main_cli() -> int:
    spec = build_spec()
    files = render(spec)
    if "--check" in sys.argv:
        stale = [p for p, text in files.items() if not p.exists() or p.read_text() != text]
        if stale:
            names = ", ".join(str(p.relative_to(ROOT)) for p in stale)
            print(f"{names} out of date. Run: python scripts/export_openapi.py")
            return 1
        print("OpenAPI spec is up to date.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for path, text in files.items():
        path.write_text(text)
    ops = sum(len(v) for v in spec["paths"].values())
    print(
        f"Wrote {OUT.relative_to(ROOT)} and {OUT_YAML.relative_to(ROOT)} "
        f"({len(spec['paths'])} paths, {ops} operations)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
