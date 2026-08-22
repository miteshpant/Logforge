"""
Login brute-force and credential-stuffing defence (ENH-013).

`POST /v1/auth/login` is a public endpoint with no attempt counter, no lockout,
and no IP throttle, so an attacker could guess passwords indefinitely against a
known email list. Worse, password verification uses bcrypt with 12 rounds --
deliberately expensive -- so unlimited attempts are also a cheap CPU-exhaustion
vector against our own servers.

Design
------
* Two independent counters: per **account** (email) and per **source IP**. The
  account counter stops targeted guessing; the IP counter stops spraying across
  many accounts, which an account-only counter completely misses.
* Backed by Redis so limits hold across replicas and survive restarts.
* **Fails closed** when Redis is unavailable. That is a deliberate trade:
  an outage in the throttle store must not silently reopen unlimited password
  guessing. `LOGIN_THROTTLE_REQUIRED=false` lets an operator opt out for
  single-node/dev deployments where Redis is not provisioned.
* Counters are keyed by a **hash** of the identifier, so the store never holds
  plaintext user emails.
* Successful login clears the account counter, so a legitimate user who
  mistypes a few times is not penalised afterwards.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class LoginThrottleError(RuntimeError):
    """Raised when the throttle store cannot be consulted."""


@dataclass(frozen=True)
class ThrottlePolicy:
    """Thresholds for login throttling."""

    max_attempts_per_account: int = 5
    account_window_seconds: int = 900  # 15 minutes
    max_attempts_per_ip: int = 20
    ip_window_seconds: int = 900

    @classmethod
    def from_env(cls) -> "ThrottlePolicy":
        return cls(
            max_attempts_per_account=int(
                os.getenv("LOGIN_MAX_ATTEMPTS_PER_ACCOUNT", "5")
            ),
            account_window_seconds=int(
                os.getenv("LOGIN_ACCOUNT_WINDOW_SECONDS", "900")
            ),
            max_attempts_per_ip=int(os.getenv("LOGIN_MAX_ATTEMPTS_PER_IP", "20")),
            ip_window_seconds=int(os.getenv("LOGIN_IP_WINDOW_SECONDS", "900")),
        )


@dataclass(frozen=True)
class ThrottleDecision:
    """Outcome of a throttle check."""

    allowed: bool
    retry_after_seconds: int = 0
    scope: str = ""  # 'account' | 'ip'


def _hash_identifier(value: str) -> str:
    """
    Hash an identifier before it becomes a cache key.

    Emails are personal data; a Redis instance (or its backups, or an operator
    running KEYS) should not expose the list of accounts being attacked.
    """
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:32]


class LoginThrottle:
    """Redis-backed login attempt throttle."""

    def __init__(self, redis_manager=None, policy: Optional[ThrottlePolicy] = None):
        self._redis = redis_manager
        self.policy = policy or ThrottlePolicy.from_env()

    @staticmethod
    def is_required() -> bool:
        """
        Whether a working throttle store is mandatory.

        Defaults to True: losing the throttle must not silently reopen
        unlimited password guessing.
        """
        return os.getenv("LOGIN_THROTTLE_REQUIRED", "true").strip().lower() not in {
            "false", "0", "no"
        }

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        from events.management.cache.redis_manager import get_redis_manager

        self._redis = await get_redis_manager()
        return self._redis

    async def _bump(self, key: str, window_seconds: int) -> int:
        """Increment a counter and return its new value, setting a TTL."""
        redis = await self._get_redis()
        client = getattr(redis, "client", None) or redis

        count = await client.incr(key)
        if int(count) == 1:
            # First attempt in this window -- start the expiry clock.
            await client.expire(key, window_seconds)
        return int(count)

    async def _peek(self, key: str) -> int:
        redis = await self._get_redis()
        client = getattr(redis, "client", None) or redis
        value = await client.get(key)
        if value is None:
            return 0
        if isinstance(value, bytes):
            value = value.decode()
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _account_key(self, email: str) -> str:
        return f"login:fail:account:{_hash_identifier(email)}"

    def _ip_key(self, ip_address: str) -> str:
        return f"login:fail:ip:{_hash_identifier(ip_address)}"

    async def check(self, email: str, ip_address: str) -> ThrottleDecision:
        """
        Check whether a login attempt may proceed.

        Raises:
            LoginThrottleError: if the store cannot be reached and a throttle is
            required. The caller must turn this into a 503 -- never allow the
            attempt through.
        """
        try:
            account_count = await self._peek(self._account_key(email))
            if account_count >= self.policy.max_attempts_per_account:
                return ThrottleDecision(
                    allowed=False,
                    retry_after_seconds=self.policy.account_window_seconds,
                    scope="account",
                )

            ip_count = await self._peek(self._ip_key(ip_address))
            if ip_count >= self.policy.max_attempts_per_ip:
                return ThrottleDecision(
                    allowed=False,
                    retry_after_seconds=self.policy.ip_window_seconds,
                    scope="ip",
                )

            return ThrottleDecision(allowed=True)

        except Exception as exc:
            if self.is_required():
                logger.error(
                    "Login throttle store unavailable -- refusing login",
                    error=str(exc),
                )
                raise LoginThrottleError(
                    "Login throttling is unavailable"
                ) from exc

            # Explicitly opted out. Logged loudly: this is a weakened posture.
            logger.warning(
                "Login throttle store unavailable and throttling is not "
                "required; proceeding WITHOUT brute-force protection",
                error=str(exc),
            )
            return ThrottleDecision(allowed=True)

    async def record_failure(self, email: str, ip_address: str) -> None:
        """Record a failed attempt against both the account and the source IP."""
        try:
            await self._bump(
                self._account_key(email), self.policy.account_window_seconds
            )
            await self._bump(self._ip_key(ip_address), self.policy.ip_window_seconds)
        except Exception as exc:
            # Never break the login response because bookkeeping failed, but do
            # make it visible -- a throttle that is not counting is not
            # protecting anything.
            logger.error("Failed to record login failure", error=str(exc))

    async def record_success(self, email: str) -> None:
        """Clear the account counter after a successful login."""
        try:
            redis = await self._get_redis()
            client = getattr(redis, "client", None) or redis
            await client.delete(self._account_key(email))
        except Exception as exc:
            logger.warning("Failed to reset login failure counter", error=str(exc))


_throttle_instance: Optional[LoginThrottle] = None


def get_login_throttle() -> LoginThrottle:
    """Get the shared LoginThrottle, constructing it on first use."""
    global _throttle_instance
    if _throttle_instance is None:
        _throttle_instance = LoginThrottle()
    return _throttle_instance
