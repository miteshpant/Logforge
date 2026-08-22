"""
Refresh Token Service (LF-015)

Rotating refresh tokens for transparent session renewal:

- Tokens are opaque random strings (``secrets.token_urlsafe(48)``); only a
  SHA-256 hash is stored server-side, in ``user_sessions_mt`` rows whose
  ``session_token`` carries a ``refresh:`` prefix so they are distinguishable
  from JWT access-token session rows without a schema change.
- ``POST /v1/auth/refresh`` validates the presented token, revokes it and
  issues a new refresh + access token pair (rotation).
- Presenting a token that was already rotated/revoked is treated as theft:
  every refresh token belonging to that user is revoked, forcing re-login
  (standard stolen-token defence).

No fabricated success anywhere: every failure raises and surfaces as 401.
"""

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

import structlog

logger = structlog.get_logger()

# Refresh tokens outlive the 8h access token but are capped at 7 days to
# bound the exposure window of the JS-readable store (see ENH-018 notes in
# apps/ui/lib/api/client.ts).
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7"))

_REFRESH_PREFIX = "refresh:"


class RefreshTokenError(Exception):
    """Presented refresh token is unknown, expired, or malformed."""


class RefreshTokenReuseError(RefreshTokenError):
    """A rotated/revoked token was presented again — possible theft."""


def _hash_token(token: str) -> str:
    return _REFRESH_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


class RefreshTokenService:
    """Issues, validates and rotates refresh tokens in user_sessions_mt.

    Takes the UserDAO-scoped DatabaseLayer, which is already authorised for
    reads, inserts and ALTER..UPDATE on ``user_sessions_mt``.
    """

    def __init__(self, db):
        self.db = db

    async def issue(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        user_agent: str,
    ) -> Dict[str, Any]:
        """Create and persist a new refresh token for the user."""
        token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_token": _hash_token(token),
            "ip_address": ip_address or "unknown",
            "user_agent": user_agent or "",
            "expires_at": expires_at,
            "status": "active",
            "customer_id": tenant_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
        }
        await self.db.execute_insert("user_sessions_mt", [record])

        logger.info(
            "Refresh token issued",
            user_id=user_id,
            tenant_id=tenant_id,
            expires_at=expires_at.isoformat(),
        )
        return {"refresh_token": token, "expires_at": expires_at}

    async def validate_and_rotate(self, refresh_token: str) -> Dict[str, Any]:
        """Validate a presented refresh token and revoke it (rotation).

        Returns the stored row (``user_id``, ``customer_id``) on success.
        Raises RefreshTokenReuseError when an already-rotated token is
        replayed — after revoking the user's whole refresh-token chain.
        """
        if not refresh_token or not isinstance(refresh_token, str):
            raise RefreshTokenError("Missing refresh token")

        token_hash = _hash_token(refresh_token)
        rows = await self.db.execute_query(
            """
            SELECT id, user_id, session_token, expires_at, status, customer_id
            FROM user_sessions_mt
            WHERE session_token = %(token_hash)s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"token_hash": token_hash},
        )

        if not rows:
            raise RefreshTokenError("Unknown refresh token")

        row = rows[0]
        status = str(row.get("status"))

        if status != "active":
            # Reuse of a rotated or revoked token: assume the token was
            # stolen and revoke every refresh token for this user.
            logger.warning(
                "Refresh token reuse detected — revoking all refresh tokens",
                user_id=row["user_id"],
            )
            await self.revoke_all_for_user(row["user_id"])
            raise RefreshTokenReuseError("Refresh token reuse detected")

        expires_at = row.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at <= datetime.utcnow():
            await self._revoke_hash(token_hash)
            raise RefreshTokenError("Refresh token expired")

        # Rotate: the presented token is single-use.
        await self._revoke_hash(token_hash)
        return row

    async def revoke(self, refresh_token: str) -> None:
        """Revoke a specific refresh token (logout)."""
        if not refresh_token:
            return
        await self._revoke_hash(_hash_token(refresh_token))

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke every refresh token belonging to a user (chain revocation)."""
        await self.db.execute_update(
            """
            ALTER TABLE user_sessions_mt UPDATE status = 'revoked'
            WHERE user_id = %(user_id)s
              AND session_token LIKE 'refresh:%%'
              AND status = 'active'
            SETTINGS mutations_sync = 1
            """,
            {"user_id": user_id},
        )

    async def _revoke_hash(self, token_hash: str) -> None:
        # mutations_sync=1 so an immediately replayed token observes the
        # revocation — reuse detection depends on it.
        await self.db.execute_update(
            """
            ALTER TABLE user_sessions_mt UPDATE status = 'revoked'
            WHERE session_token = %(token_hash)s
            SETTINGS mutations_sync = 1
            """,
            {"token_hash": token_hash},
        )
