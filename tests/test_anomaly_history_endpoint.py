"""
Tests for ENH-035 -- `/anomalies/history` must not 500 on a missing import.

The endpoint did `from dao.anomaly_dao import AnomalyDAO` inside its handler.
That module does not exist (`apps/api/dao/` has no `anomaly_dao.py`), so every
request raised `ModuleNotFoundError` and returned 500. It also called
`get_anomalies()` / `count_anomalies()`, which have no implementation anywhere.

It now queries `multi_metric_anomalies_mt` through `AIDAO` -- the same table the
dismiss handler updates.

These tests check the handler's structure and query construction without a
database, since the point is that the code path no longer references a
non-existent module.
"""

import ast
import inspect
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
AI_API = API_ROOT / "routers" / "ai_api.py"


# ---------------------------------------------------------------------------
# The missing module must be gone
# ---------------------------------------------------------------------------


def test_anomaly_dao_module_still_does_not_exist():
    """Pins the premise: there is no `dao.anomaly_dao` to import."""
    assert not (API_ROOT / "dao" / "anomaly_dao.py").exists()


def test_no_module_imports_the_missing_anomaly_dao():
    """
    No handler may import `dao.anomaly_dao`. Any that does returns 500 on every
    request.
    """
    # Checked against the AST so that comments and docstrings explaining the old
    # bug do not count as references. Only real import statements matter.
    offenders = []
    for path in API_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "anomaly_dao" in node.module:
                    offenders.append(f"{path.relative_to(API_ROOT)}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "anomaly_dao" in alias.name:
                        offenders.append(
                            f"{path.relative_to(API_ROOT)}:{node.lineno}"
                        )

    assert not offenders, (
        f"These import the non-existent `dao.anomaly_dao`: {offenders}"
    )


# ---------------------------------------------------------------------------
# The handler uses the real DAO and table
# ---------------------------------------------------------------------------


def _handler_source(name):
    from routers import ai_api

    return inspect.getsource(getattr(ai_api, name))


def test_history_handler_uses_ai_dao():
    source = _handler_source("get_anomaly_history")
    assert "from dao.ai_dao import AIDAO" in source


def test_history_handler_queries_the_real_table():
    source = _handler_source("get_anomaly_history")
    assert "multi_metric_anomalies_mt" in source, (
        "History must read the same table the dismiss handler writes."
    )


def test_history_handler_is_syntactically_valid():
    tree = ast.parse(AI_API.read_text(encoding="utf-8"))
    handlers = [
        n for n in tree.body
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
        and n.name == "get_anomaly_history"
    ]
    assert len(handlers) == 1


# ---------------------------------------------------------------------------
# Tenant isolation and injection safety
# ---------------------------------------------------------------------------


def test_customer_id_is_bound_not_interpolated():
    source = _handler_source("get_anomaly_history")
    assert "customer_id = %(customer_id)s" in source, (
        "Tenant predicate must be a bound parameter."
    )
    assert 'customer_id = \'{' not in source


def test_filters_are_bound_parameters():
    source = _handler_source("get_anomaly_history")
    assert "severity = %(severity)s" in source
    assert "service = %(service)s" in source


def test_every_query_is_tenant_scoped():
    """Both the page query and the count query must carry the tenant filter."""
    source = _handler_source("get_anomaly_history")
    assert source.count("where_clause") >= 2


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_invalid_severity_is_rejected_as_client_error():
    """
    `severity` is an Enum8 column; an unknown value is a ClickHouse error. It
    must be caught as a 400 rather than surfacing as a 500.
    """
    source = _handler_source("get_anomaly_history")
    assert "status_code=400" in source
    assert "Invalid severity" in source


def test_http_exceptions_are_not_relabelled_as_500():
    source = _handler_source("get_anomaly_history")
    assert "except HTTPException:" in source, (
        "A deliberate 400 must not be converted into a 500 by the broad handler."
    )


def test_category_parameter_was_replaced_with_service():
    """
    The old `category` filter had no backing column in
    multi_metric_anomalies_mt, so it could never have worked.
    """
    from routers import ai_api

    params = inspect.signature(ai_api.get_anomaly_history).parameters
    assert "service" in params
    assert "category" not in params


def test_limit_and_offset_are_bounded():
    from routers import ai_api

    params = inspect.signature(ai_api.get_anomaly_history).parameters

    def constraints(param):
        """FastAPI stores ge/le in `metadata` as annotated-types objects."""
        return {
            type(item).__name__: getattr(item, type(item).__name__.lower(), None)
            for item in params[param].default.metadata
        }

    limit = constraints("limit")
    assert limit.get("Le") == 500, "limit must be capped to bound scan cost"
    assert limit.get("Ge") == 1

    assert constraints("offset").get("Ge") == 0
