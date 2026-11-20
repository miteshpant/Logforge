"""
Signed, expiring account tokens (Phase 14), for links that don't need a
stored token: email verification.

A token is "<expiry>.<signature>". The signature is an HMAC over the
purpose, the user id, the lower-cased address and the expiry, keyed from
JWT_SECRET. So it is only valid for that user and that address (changing
the address invalidates it), for that purpose, until it expires. It names
no user itself.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional


def _key(purpose: str) -> bytes:
    from authn_authz_middleware import JWT_SECRET

    return hashlib.sha256(f"logforge-account-token:{purpose}:{JWT_SECRET}".encode()).digest()


def _sign(user_id: str, email: str, purpose: str, expires: int) -> str:
    message = f"{purpose}|{user_id}|{email.strip().lower()}|{expires}".encode()
    return hmac.new(_key(purpose), message, hashlib.sha256).hexdigest()


def issue(user_id: str, email: str, purpose: str, ttl: timedelta, now: Optional[datetime] = None) -> str:
    expires = int(((now or datetime.now(timezone.utc)) + ttl).timestamp())
    return f"{expires}.{_sign(user_id, email, purpose, expires)}"


def check(token: str, user_id: str, email: str, purpose: str, now: Optional[datetime] = None) -> bool:
    parts = (token or "").split(".")
    if len(parts) != 2 or not parts[0].isdigit():
        return False
    expires = int(parts[0])
    if expires < (now or datetime.now(timezone.utc)).timestamp():
        return False
    return hmac.compare_digest(parts[1], _sign(user_id, email, purpose, expires))
