"""
Startup security configuration validation (ENH-005).

Logforge ships with development defaults for every secret -- including the JWT
signing key, which is published in this repository. A deployment that forgets to
set `JWT_SECRET` therefore accepts tokens signed with a value any reader of the
source can compute, allowing anyone to mint a token for any tenant.

This module fails the process closed at startup when a known-default or absent
secret is detected outside development. Insecure-by-default is disqualifying for
SOC 2 / ISO 27001 / FedRAMP, and a loud boot failure is far safer than a silent
authentication bypass.

Design notes
------------
* Secret VALUES are never logged -- only variable names.
* Development (`ENVIRONMENT=development`, the default) stays frictionless: it
  warns rather than raising, so local work is unaffected.
* Enforcement covers every secret in one place, so adding a new one means adding
  a row here rather than remembering to guard it at each use site.
"""

import logging
import os
from typing import Dict, List, NamedTuple, Optional

logger = logging.getLogger(__name__)

# Environments that must never run with development defaults.
ENFORCED_ENVIRONMENTS = frozenset({
    "production", "prod", "staging", "stage", "test", "uat", "preprod",
})

# Minimum acceptable length for a symmetric signing key. 32 bytes matches the
# HMAC-SHA256 output size used by the default HS256 algorithm.
MIN_SECRET_LENGTH = 32


class SecretSpec(NamedTuple):
    """A secret that must be explicitly configured outside development."""

    env_var: str
    insecure_defaults: frozenset
    min_length: int
    description: str


# Every value here is a development default that appears in the source tree.
MANAGED_SECRETS: List[SecretSpec] = [
    SecretSpec(
        env_var="JWT_SECRET",
        insecure_defaults=frozenset({
            "logforge-jwt-secret-key-change-in-production",
        }),
        min_length=MIN_SECRET_LENGTH,
        description="Signs all session tokens; a known value allows token forgery.",
    ),
    SecretSpec(
        env_var="CLICKHOUSE_PASSWORD",
        insecure_defaults=frozenset({"logforge123", ""}),
        min_length=0,  # length policy is the operator's choice; default-ness is not
        description="Primary datastore credential.",
    ),
    SecretSpec(
        env_var="MINIO_SECRET_KEY",
        insecure_defaults=frozenset({"minio123", ""}),
        min_length=0,
        description="Object storage credential for archived logs.",
    ),
]


class InsecureConfigurationError(RuntimeError):
    """Raised when the process is configured with known-insecure secrets."""


def is_enforced(environment: Optional[str] = None) -> bool:
    """Whether secret policy is enforced for the given environment."""
    env = (environment or os.getenv("ENVIRONMENT", "development")).strip().lower()
    return env in ENFORCED_ENVIRONMENTS


def _problems_for(spec: SecretSpec) -> Optional[str]:
    """Return a description of the problem with this secret, or None if fine."""
    value = os.getenv(spec.env_var)

    if value is None or value == "":
        return f"{spec.env_var} is not set. {spec.description}"

    if value in spec.insecure_defaults:
        return (
            f"{spec.env_var} is set to a well-known development default that is "
            f"published in this repository. {spec.description}"
        )

    if spec.min_length and len(value) < spec.min_length:
        return (
            f"{spec.env_var} is shorter than the required {spec.min_length} "
            f"characters. {spec.description}"
        )

    return None


def validate_security_configuration(
    environment: Optional[str] = None,
    raise_on_error: Optional[bool] = None,
) -> Dict[str, List[str]]:
    """
    Validate all managed secrets.

    Args:
        environment: override for `ENVIRONMENT` (mainly for tests).
        raise_on_error: override enforcement. Defaults to enforcing whenever the
            environment is not development.

    Returns:
        {"errors": [...], "warnings": [...]} -- messages contain variable NAMES
        and never secret values.

    Raises:
        InsecureConfigurationError: when enforcing and problems were found.
    """
    env = (environment or os.getenv("ENVIRONMENT", "development")).strip().lower()
    enforce = is_enforced(env) if raise_on_error is None else raise_on_error

    problems = [msg for spec in MANAGED_SECRETS if (msg := _problems_for(spec))]

    # LF-021: a wildcard CORS origin silently disables the browser's
    # cross-origin protection for every authenticated endpoint. Individual
    # handlers must never hardcode ACAO headers either — the CORSMiddleware
    # allowlist in main.py is the single source of truth.
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if "*" in cors_origins:
        problems.append(
            "CORS_ORIGINS contains '*' — set an explicit comma-separated "
            "origin allowlist (e.g. https://app.example.com)"
        )

    result: Dict[str, List[str]] = {"errors": [], "warnings": []}

    if not problems:
        logger.info("Security configuration validated", extra={"environment": env})
        return result

    if enforce:
        result["errors"] = problems
        detail = "\n  - ".join(problems)
        message = (
            f"Refusing to start in environment '{env}' with insecure secrets:\n"
            f"  - {detail}\n"
            "Set each variable to a strong, unique value. "
            "See docs/ENHANCEMENTS.md ENH-005."
        )
        # Log names only -- never the offending values.
        logger.critical(
            "Insecure security configuration detected",
            extra={"environment": env, "problem_count": len(problems)},
        )
        raise InsecureConfigurationError(message)

    result["warnings"] = problems
    for problem in problems:
        logger.warning(
            "Insecure default in use (allowed in development only): %s", problem
        )
    return result
