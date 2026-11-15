#!/usr/bin/env python3
"""Export the Logforge API's OpenAPI spec to docs/api/openapi.json.

The FastAPI app imports without live infrastructure (see
tests/test_offline_app_import.py), so this runs anywhere the API's Python
dependencies are installed:

    pip install -r apps/api/requirements.txt
    python scripts/export_openapi.py          # write the spec
    python scripts/export_openapi.py --check  # fail if the committed spec is stale
"""

import json
import logging
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "api" / "openapi.json"


def build_spec() -> dict:
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    import main  # noqa: E402  (path set above)

    spec = main.app.openapi()
    spec["servers"] = [{"url": "http://localhost:7080", "description": "Local Docker Compose stack"}]
    return spec


def main_cli() -> int:
    rendered = json.dumps(build_spec(), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != rendered:
            print(f"{OUT.relative_to(ROOT)} is out of date. Run: python scripts/export_openapi.py")
            return 1
        print("OpenAPI spec is up to date.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered)
    spec = json.loads(rendered)
    ops = sum(len(v) for v in spec["paths"].values())
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(spec['paths'])} paths, {ops} operations)")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
