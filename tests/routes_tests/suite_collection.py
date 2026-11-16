"""
Collect the route-test suites as individual pytest tests.

The route tests are classes derived from ``BaseTestSuite`` with an
``__init__`` and ``async def test_*`` methods, driven by each class's own
``run_all_tests()`` (which sets up an isolated user/tenant, calls the methods
in a deliberate order, then cleans up). pytest never collects classes with an
``__init__``, so ``pytest tests/routes_tests`` found 4 tests out of ~220.

They also cannot simply be collected as-is: every method catches its own
exceptions and records ``"ERROR: ..."`` in ``self.test_results`` instead of
raising, so a naive conversion would turn every failure green.

This plugin keeps the author's execution model and makes the outcome honest:

* each ``test_*`` method becomes its own pytest item;
* the first item of a class runs the suite once via ``run_all_tests()``, with
  every method wrapped to record which ``test_results`` entries it wrote;
* an item passes only if all entries its method wrote are ``"PASS"`` (or a
  ``"SKIP..."`` marker); any other value fails the item with that value;
* a method that ``run_all_tests()`` never calls is reported as skipped, not
  silently green;
* every item is marked ``integration`` and skips when the API at
  ``LOGFORGE_API_URL`` (default http://localhost:7080) is not reachable.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import os
from typing import Dict, List, Optional

import httpx
import pytest

API_URL = os.getenv("LOGFORGE_API_URL", "http://localhost:7080")

_api_available: Optional[bool] = None


def _api_is_up() -> bool:
    global _api_available
    if _api_available is None:
        try:
            _api_available = httpx.get(f"{API_URL}/health", timeout=3).status_code == 200
        except httpx.HTTPError:
            _api_available = False
    return _api_available


def _reset_login_throttle() -> None:
    """Clear login brute-force counters in the test stack's Redis.

    The throttle (5 failures per account, 20 per IP, 15-minute windows) works
    as intended, so repeated local or CI runs from one IP would otherwise start
    returning 429 to suites that deliberately test bad credentials. Only the
    `login:fail:*` keys are touched, and only when Redis is reachable.
    """
    try:
        import redis

        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            socket_connect_timeout=2,
        )
        keys = list(client.scan_iter("login:fail:*"))
        if keys:
            client.delete(*keys)
    except Exception:  # noqa: BLE001 - best effort; suites still run
        pass


def _is_suite_class(obj) -> bool:
    try:
        from base_test import BaseTestSuite
    except ImportError:
        return False
    return inspect.isclass(obj) and issubclass(obj, BaseTestSuite) and obj is not BaseTestSuite


class _SuiteRun:
    """Runs one suite class once and remembers what each method recorded."""

    def __init__(self, cls):
        self.cls = cls
        self.ran = False
        self.error: Optional[BaseException] = None
        self.called: set = set()
        self.recorded: Dict[str, Dict[str, str]] = {}

    def ensure_ran(self) -> None:
        if self.ran:
            return
        self.ran = True
        names = [n for n, _ in inspect.getmembers(self.cls, inspect.iscoroutinefunction) if n.startswith("test_")]
        originals = {n: self.cls.__dict__[n] for n in names if n in self.cls.__dict__}
        # Wrap at class level so suites whose entry point builds its own
        # instance (module-level run_*_tests()) are recorded too.
        for n in names:
            setattr(self.cls, n, self._wrap(n, getattr(self.cls, n)))
        _reset_login_throttle()
        try:
            asyncio.run(self._entry_point()())
        except BaseException as exc:  # noqa: BLE001 - reported per item below
            self.error = exc
        finally:
            for n in names:
                if n in originals:
                    setattr(self.cls, n, originals[n])
                else:
                    delattr(self.cls, n)

    def _entry_point(self):
        """The suite's own runner: the module's run_*_tests() if it has one,
        else the class's run_all_tests()."""
        module = inspect.getmodule(self.cls)
        runners = [
            fn for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction)
            if name.startswith("run_") and name.endswith("_tests") and fn.__module__ == module.__name__
        ]
        if len(runners) == 1:
            return runners[0]
        return lambda: self.cls().run_all_tests()

    def _wrap(self, name, method):
        run = self

        @functools.wraps(method)
        async def recorder(suite, *args, **kwargs):
            run.called.add(name)
            before = dict(suite.test_results)
            try:
                return await method(suite, *args, **kwargs)
            except BaseException as exc:  # recorded here: callers log it after we return
                run.recorded.setdefault(name, {})[name] = f"ERROR: {exc!r}"
                raise
            finally:
                changed = {
                    key: str(value)
                    for key, value in suite.test_results.items()
                    if before.get(key) != value
                }
                run.recorded.setdefault(name, {}).update(changed)

        return recorder


class RouteSuite(pytest.Class):
    """A BaseTestSuite subclass, yielding one item per ``test_*`` method."""

    def collect(self):
        run = _SuiteRun(self.obj)
        for name, _ in inspect.getmembers(self.obj, inspect.iscoroutinefunction):
            if name.startswith("test_"):
                item = RouteSuiteMethod.from_parent(self, name=name)
                item.suite_run = run
                item.add_marker(pytest.mark.integration)
                yield item


class RouteSuiteMethod(pytest.Item):
    suite_run: _SuiteRun

    def runtest(self) -> None:
        if not _api_is_up():
            pytest.skip(f"API not reachable at {API_URL} (start the stack with ./deploy.sh)")

        run = self.suite_run
        run.ensure_ran()
        if run.error is not None and not run.called:
            raise RuntimeError(f"{run.cls.__name__}.run_all_tests() failed before any test ran: {run.error!r}")
        if self.name not in run.called:
            pytest.skip(f"{run.cls.__name__}.run_all_tests() does not call {self.name}")

        recorded = run.recorded.get(self.name, {})
        failures: List[str] = [
            f"{key}: {value}"
            for key, value in recorded.items()
            if value != "PASS" and not value.upper().startswith("SKIP")
        ]
        if failures:
            raise AssertionError("; ".join(failures))

    def reportinfo(self):
        return self.path, None, f"{self.parent.name}::{self.name}"

    def repr_failure(self, excinfo, style=None):
        if isinstance(excinfo.value, AssertionError):
            return f"{self.parent.name}.{self.name} recorded: {excinfo.value}"
        return super().repr_failure(excinfo, style=style)


def pytest_pycollect_makeitem(collector, name, obj):
    if _is_suite_class(obj) and obj.__module__ == getattr(collector.obj, "__name__", None):
        return RouteSuite.from_parent(collector, name=name, obj=obj)
    return None
