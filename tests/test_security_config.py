"""
Tests for ENH-005 -- fail closed on missing or default secrets.

The JWT signing default (`logforge-jwt-secret-key-change-in-production`) is
published in this repository. A deployment that does not override it accepts
tokens that anyone can forge, for any tenant. These tests pin the rule that such
a configuration cannot start outside development.
"""

import pytest

from security_config import (
    MANAGED_SECRETS,
    InsecureConfigurationError,
    is_enforced,
    validate_security_configuration,
)

PUBLISHED_JWT_DEFAULT = "logforge-jwt-secret-key-change-in-production"
STRONG_SECRET = "K7x!pQ2m-Zt9Rw4LbN6vY8sD3fH5jG1c"  # 32 chars, test-only


@pytest.fixture
def clean_env(monkeypatch):
    """Start from a known state: every managed secret unset."""
    for spec in MANAGED_SECRETS:
        monkeypatch.delenv(spec.env_var, raising=False)
    return monkeypatch


def _set_all_secure(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", STRONG_SECRET)
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "a-strong-db-password")
    monkeypatch.setenv("MINIO_SECRET_KEY", "a-strong-object-store-key")


# ---------------------------------------------------------------------------
# Enforcement boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "environment", ["production", "prod", "staging", "stage", "uat", "preprod"]
)
def test_non_development_environments_are_enforced(environment):
    assert is_enforced(environment) is True


@pytest.mark.parametrize("environment", ["development", "dev", "local", ""])
def test_development_is_not_enforced(environment):
    assert is_enforced(environment) is False


def test_enforcement_is_case_insensitive():
    assert is_enforced("PRODUCTION") is True


# ---------------------------------------------------------------------------
# The core rule: production must not boot with the published default
# ---------------------------------------------------------------------------


def test_production_refuses_published_jwt_default(clean_env):
    clean_env.setenv("JWT_SECRET", PUBLISHED_JWT_DEFAULT)

    with pytest.raises(InsecureConfigurationError) as exc:
        validate_security_configuration(environment="production")

    assert "JWT_SECRET" in str(exc.value)


def test_production_refuses_missing_jwt_secret(clean_env):
    with pytest.raises(InsecureConfigurationError) as exc:
        validate_security_configuration(environment="production")

    assert "JWT_SECRET" in str(exc.value)


def test_production_refuses_short_jwt_secret(clean_env):
    clean_env.setenv("JWT_SECRET", "tooshort")
    clean_env.setenv("CLICKHOUSE_PASSWORD", "fine")
    clean_env.setenv("MINIO_SECRET_KEY", "fine")

    with pytest.raises(InsecureConfigurationError):
        validate_security_configuration(environment="production")


def test_production_refuses_default_clickhouse_password(clean_env):
    clean_env.setenv("JWT_SECRET", STRONG_SECRET)
    clean_env.setenv("CLICKHOUSE_PASSWORD", "logforge123")
    clean_env.setenv("MINIO_SECRET_KEY", "fine")

    with pytest.raises(InsecureConfigurationError) as exc:
        validate_security_configuration(environment="production")

    assert "CLICKHOUSE_PASSWORD" in str(exc.value)


def test_production_starts_with_strong_secrets(clean_env):
    _set_all_secure(clean_env)

    result = validate_security_configuration(environment="production")

    assert result["errors"] == []
    assert result["warnings"] == []


# ---------------------------------------------------------------------------
# Development must stay frictionless
# ---------------------------------------------------------------------------


def test_development_warns_but_does_not_raise(clean_env):
    clean_env.setenv("JWT_SECRET", PUBLISHED_JWT_DEFAULT)

    result = validate_security_configuration(environment="development")

    assert result["errors"] == []
    assert any("JWT_SECRET" in w for w in result["warnings"])


def test_development_with_no_secrets_still_starts(clean_env):
    result = validate_security_configuration(environment="development")
    assert result["errors"] == []
    assert result["warnings"], "Developers should still be told what is insecure."


# ---------------------------------------------------------------------------
# Secrets must never leak into messages or logs
# ---------------------------------------------------------------------------


def test_error_message_never_contains_the_secret_value(clean_env):
    """
    The failure is loud, but it must not print the secret. Startup errors are
    routinely pasted into tickets and chat.
    """
    leaky_value = "SuperSecretValueThatMustNotAppearAnywhere123456"
    clean_env.setenv("JWT_SECRET", leaky_value[:8])  # too short -> triggers error
    clean_env.setenv("CLICKHOUSE_PASSWORD", leaky_value)
    clean_env.setenv("MINIO_SECRET_KEY", leaky_value)

    with pytest.raises(InsecureConfigurationError) as exc:
        validate_security_configuration(environment="production")

    assert leaky_value not in str(exc.value)
    assert leaky_value[:8] not in str(exc.value)


def test_all_problems_reported_together(clean_env):
    """
    Operators should see every misconfiguration at once, not fix-one-restart-repeat.
    """
    with pytest.raises(InsecureConfigurationError) as exc:
        validate_security_configuration(environment="production")

    message = str(exc.value)
    for spec in MANAGED_SECRETS:
        assert spec.env_var in message


# ---------------------------------------------------------------------------
# Explicit override
# ---------------------------------------------------------------------------


def test_raise_on_error_override_forces_enforcement(clean_env):
    clean_env.setenv("JWT_SECRET", PUBLISHED_JWT_DEFAULT)

    with pytest.raises(InsecureConfigurationError):
        validate_security_configuration(
            environment="development", raise_on_error=True
        )


def test_startup_calls_validation_before_serving():
    """The check must run in the app lifespan, not merely exist."""
    import inspect

    import dependencies

    source = inspect.getsource(dependencies.lifespan)
    assert "validate_security_configuration" in source, (
        "Startup must validate security configuration before serving traffic."
    )
