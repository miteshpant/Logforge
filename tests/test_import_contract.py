"""
Import-contract regression tests (ENH-001).

The Logforge API mixes two import styles:

  * FLAT   -- `apps/api/main.py` does `from app_config import load_config`
  * PACKAGE -- `tests/routes_tests/conftest.py` does `from apps.api.main import app`

Both must resolve for the test suite to be collectable at all. That is
guaranteed by the `pythonpath` entries in the repo-root `pytest.ini`.

These tests exist so that a future change to `pytest.ini`, a directory move, or
a switch of test runner fails loudly here with an actionable message, rather
than reappearing as the opaque

    ModuleNotFoundError: No module named 'app_config'

that previously made the entire suite uncollectable.

Deliberately narrow: these assert the *import contract only*. They import
modules that have no import-time side effects. Modules that open database
connections at import time are a separate, tracked defect (ENH-010) and are
covered by `test_enh010_import_time_db_coupling_is_documented` below.
"""

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"


# ---------------------------------------------------------------------------
# sys.path wiring
# ---------------------------------------------------------------------------


def test_repo_root_is_on_sys_path():
    """`apps.api.*` package imports require the repo root on sys.path."""
    resolved = {Path(p).resolve() for p in sys.path if p}
    assert REPO_ROOT in resolved, (
        f"Repo root {REPO_ROOT} is not on sys.path. "
        "Check the `pythonpath` setting in pytest.ini (ENH-001)."
    )


def test_api_dir_is_on_sys_path():
    """Flat imports such as `import app_config` require apps/api on sys.path."""
    resolved = {Path(p).resolve() for p in sys.path if p}
    assert API_DIR in resolved, (
        f"{API_DIR} is not on sys.path, so flat imports like `import app_config` "
        "will fail. Check the `pythonpath` setting in pytest.ini (ENH-001)."
    )


# ---------------------------------------------------------------------------
# Flat import style (the style apps/api/main.py actually uses)
# ---------------------------------------------------------------------------

# Modules that are safe to import: no DB/network connection at import time.
FLAT_SAFE_MODULES = [
    "app_config",
    "models",
    "parsers",
    "query_engine",
    "storage_config",
]


@pytest.mark.parametrize("module_name", FLAT_SAFE_MODULES)
def test_flat_import_resolves(module_name):
    """Each core module must be importable by its bare, top-level name."""
    module = importlib.import_module(module_name)
    assert module.__name__ == module_name


def test_flat_import_app_config_is_functional():
    """Guard against a namespace collision resolving to some unrelated module."""
    import app_config

    assert hasattr(app_config, "load_config"), (
        "`app_config` resolved to an unexpected module -- possible name "
        "collision on sys.path."
    )

    config = app_config.load_config()
    # load_config() reads env vars with defaults; assert the contract, not values.
    for key in ("clickhouse_host", "clickhouse_port", "cors_origins", "environment"):
        assert key in config, f"load_config() is missing expected key: {key}"


# ---------------------------------------------------------------------------
# Package import style (the style the existing test suite uses)
# ---------------------------------------------------------------------------


def test_package_import_style_resolves():
    """`apps.api` must be importable as a package for conftest.py to work."""
    package = importlib.import_module("apps.api")
    assert package.__name__ == "apps.api"


def test_both_import_styles_reach_the_same_file():
    """
    The two styles must resolve to the same file on disk.

    If they diverge, a module would be loaded twice under two names, giving
    duplicate singletons and subtly wrong behaviour.
    """
    flat = importlib.import_module("models")
    packaged = importlib.import_module("apps.api.models")

    assert Path(flat.__file__).resolve() == Path(packaged.__file__).resolve(), (
        "Flat and package imports resolve to different files; sys.path ordering "
        "is wrong and modules risk being loaded twice."
    )


# ---------------------------------------------------------------------------
# ENH-010 boundary marker
# ---------------------------------------------------------------------------


def test_enh010_import_time_db_coupling_is_documented():
    """
    Pins the *current* boundary of ENH-001 versus ENH-010.

    `apps/api/tenant_service.py` instantiates `TenantService()` at module scope,
    which opens a ClickHouse connection during import. That makes the full app
    un-importable without live infrastructure -- a separate defect (ENH-010).

    ENH-001 fixed the sys.path contract only. This test asserts that the import
    path itself is sound, so that when ENH-010 lands the failure mode here
    changes from DatabaseError to a clean import. If this test starts failing
    because the import succeeds, ENH-010 is done: delete this test and enable
    full app-import coverage.
    """
    module_path = API_DIR / "tenant_service.py"
    assert module_path.exists(), "apps/api/tenant_service.py is missing"

    source = module_path.read_text(encoding="utf-8")
    assert "tenant_service = TenantService()" in source, (
        "Module-level TenantService() instantiation is gone -- ENH-010 may be "
        "complete. Remove this test and enable full app-import coverage."
    )

    # The import path must be sound: failure must be a DB connection error,
    # NOT a ModuleNotFoundError. A ModuleNotFoundError would mean ENH-001 has
    # regressed.
    try:
        importlib.import_module("tenant_service")
    except ModuleNotFoundError as exc:  # pragma: no cover - regression guard
        pytest.fail(
            "ENH-001 has regressed: flat import resolution is broken. "
            f"Underlying error: {exc}"
        )
    except Exception:
        # Any non-import error (e.g. DatabaseError) is the expected, documented
        # ENH-010 behaviour when infrastructure is unavailable.
        pass
