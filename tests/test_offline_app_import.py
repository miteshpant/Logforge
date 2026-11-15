"""
Tests for ENH-010 -- the application must import without live infrastructure.

Originally, `import apps.api.main` opened a ClickHouse connection. The chain was:

    tenant_service.py:9        tenant_service = TenantService()
    services/tenant_service.py TenantDAO()
    dao/tenant_dao.py          DatabaseLayer(...)
    database_layer.py:151      clickhouse_connect.get_client(...)   <-- connects

Because `tenant_dependencies` imports that module and every router imports
`tenant_dependencies` for `MiddlewareTenant`, one line made the entire
application un-importable -- and therefore untestable -- without a database.
About 30 further module-level singletons had the same shape.

Services are now constructed on first use, with PEP 562 module `__getattr__`
hooks preserving every existing import spelling.
"""

import importlib

import pytest


def test_full_app_imports_without_a_database():
    """
    The headline property. If this fails, every endpoint test is once again
    gated on running infrastructure.
    """
    main = importlib.import_module("main")
    assert main.app is not None


def test_app_has_routes_registered():
    """Importing must build the real router set, not a degraded subset."""
    main = importlib.import_module("main")
    # Count endpoints via the OpenAPI schema: since FastAPI 0.15x,
    # `app.routes` holds one entry per included router rather than a flat
    # list of endpoints, so its length no longer reflects what is served.
    assert len(main.app.openapi()["paths"]) > 100


@pytest.mark.parametrize(
    "module_name",
    [
        "authn_authz_middleware",
        "tenant_service",
        "subscription_service",
        "sigma_engine",
        "query_engine",
        "routers.query",
        "routers.auth_api",
        "routers.user_api",
        "routers.role_api",
        "routers.usage_api",
        "routers.ingestion",
        "routers.alerts",
        "routers.dashboard",
        "routers.storage",
        "routers.security_api",
        "routers.subscription_api",
        "routers.alert_correlation_api",
        "feature_access_middleware",
    ],
)
def test_module_imports_without_a_database(module_name):
    module = importlib.import_module(module_name)
    assert module is not None


@pytest.mark.parametrize(
    "module_name,attribute",
    [
        ("tenant_service", "tenant_service"),
        ("subscription_service", "subscription_service"),
        ("authn_authz_middleware", "user_service"),
        ("authn_authz_middleware", "setup_token_manager"),
        ("sigma_engine", "sigma_engine"),
    ],
)
def test_legacy_singleton_names_are_still_resolvable(module_name, attribute):
    """
    Backward compatibility: the lazy conversion must not break the historical
    `from module import singleton` spelling. Accessing the attribute is what
    triggers construction, which will fail without a database -- the contract
    under test is that the NAME still exists, not that it can connect.
    """
    module = importlib.import_module(module_name)

    # PEP 562 module-level __getattr__ lives in the module's own namespace.
    has_hook = callable(module.__dict__.get("__getattr__"))
    assert has_hook or attribute in module.__dict__, (
        f"{module_name}.{attribute} is no longer resolvable: the module has "
        "neither the attribute nor a PEP 562 __getattr__ hook."
    )

    try:
        getattr(module, attribute)
    except AttributeError:
        pytest.fail(
            f"{module_name}.{attribute} raised AttributeError -- the lazy "
            "accessor hook is missing or misnamed."
        )
    except Exception:
        # Any other error means the name resolved and construction was
        # attempted, which is the expected behaviour with no database.
        pass


def test_no_router_constructs_services_at_module_scope():
    """
    Guards against the pattern returning. A new router doing
    `svc = SomeService()` at module scope would silently re-break offline
    importability for the whole application.
    """
    import ast
    from pathlib import Path

    routers = Path(__file__).resolve().parent.parent / "apps" / "api" / "routers"
    offenders = []

    for path in sorted(routers.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:  # module scope only
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            func = value.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name and name.endswith(("Service", "DAO")):
                offenders.append(f"{path.name}:{node.lineno} -> {name}()")

    assert not offenders, (
        "Routers constructing services at import time (ENH-010): " f"{offenders}"
    )
