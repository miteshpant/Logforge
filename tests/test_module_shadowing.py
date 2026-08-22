"""
Tests for ENH-025 -- no module may be shadowed by a same-named package.

`apps/api/events/` contained BOTH `handlers.py` and `handlers/`. Python resolves
a package before a module of the same name, so `handlers.py` was unreachable
dead code -- and `events/manager.py` imported `log_ingestion_handler` from it,
a name the winning package does not define. `events/manager.py` was therefore
broken (`ImportError: attempted relative import beyond top-level package`) and
had no importers at all.

This is a nasty class of bug because the shadowed file looks live: it is
syntactically valid, it is in the right directory, and grep finds it.
"""

import ast
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"


def _shadowed_modules():
    """Any `x.py` sitting beside a directory `x/` containing `__init__.py`."""
    conflicts = []
    for directory in API_ROOT.rglob("*"):
        if not directory.is_dir():
            continue
        if not (directory / "__init__.py").exists():
            continue
        sibling = directory.with_suffix(".py")
        if sibling.exists():
            conflicts.append(
                f"{sibling.relative_to(API_ROOT)} shadowed by "
                f"{directory.relative_to(API_ROOT)}/"
            )
    return conflicts


def test_no_module_is_shadowed_by_a_package():
    conflicts = _shadowed_modules()
    assert not conflicts, (
        "A module is shadowed by a same-named package, so its code is "
        f"unreachable: {conflicts}"
    )


def test_removed_dead_modules_are_gone():
    assert not (API_ROOT / "events" / "handlers.py").exists()
    assert not (API_ROOT / "events" / "manager.py").exists()


def test_handlers_package_is_the_one_that_resolves():
    import events.handlers

    assert events.handlers.__file__.endswith("handlers/__init__.py")


def test_events_package_still_exports_its_handlers():
    """Removing the shadowed file must not have taken real exports with it."""
    import events.handlers as handlers

    exported = [n for n in dir(handlers) if n.endswith("Handler")]
    assert exported, "events.handlers exports no handler classes"


def test_application_still_imports():
    """The removal must not break the app."""
    import main

    assert len(main.app.routes) > 100


@pytest.mark.parametrize(
    "shim,target",
    [
        ("tenant_service", "services.tenant_service"),
        ("subscription_service", "services.subscription_service"),
    ],
)
def test_compatibility_shims_delegate_rather_than_duplicate(shim, target):
    """
    `apps/api/tenant_service.py` and `apps/api/subscription_service.py` are
    intentionally KEPT. They are ~40-line lazy accessors that delegate to the
    real implementation in `services/`, not second copies of it. This test pins
    that distinction so a future edit does not turn a shim into a fork.
    """
    source = (API_ROOT / f"{shim}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports_target = any(
        isinstance(node, ast.ImportFrom) and node.module == target
        for node in ast.walk(tree)
    )
    assert imports_target, f"{shim}.py no longer delegates to {target}"

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    assert not classes, (
        f"{shim}.py defines classes; it must remain a thin shim, not a fork "
        "of the real service."
    )

    assert len(source.splitlines()) < 100, (
        f"{shim}.py has grown beyond a shim ({len(source.splitlines())} lines)."
    )
