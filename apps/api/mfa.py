"""
Multi-factor authentication with TOTP (RFC 6238: SHA-1, 6 digits, 30 s).

- Enrolling stores a sealed secret; confirming it with a code turns MFA on
  and returns eight one-time backup codes (stored as SHA-256 hashes).
- With MFA on, a correct password returns only a short-lived signed
  challenge; POST /v1/auth/login/mfa with the challenge and a code (or a
  backup code) completes the sign-in.
- A code is accepted one step either side of now, and never twice (the last
  step used is kept).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import jwt

STEP = 30
DIGITS = 6
CHALLENGE_AUDIENCE = "logforge-mfa-challenge"


class MFAError(Exception):
    pass


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def totp(secret: str, now: Optional[float] = None, step_offset: int = 0) -> str:
    counter = int((time.time() if now is None else now) // STEP) + step_offset
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def check(secret: str, code: str, last_step: int, now: Optional[float] = None) -> Optional[int]:
    """The time step `code` belongs to, if it's valid now and newer than `last_step`; else None."""
    code = (code or "").strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = time.time() if now is None else now
    current = int(now // STEP)
    for offset in (0, -1, 1):
        step = current + offset
        if step > last_step and hmac.compare_digest(totp(secret, now, offset), code):
            return step
    return None


def otpauth_url(secret: str, account: str) -> str:
    return f"otpauth://totp/Logforge:{quote(account)}?secret={secret}&issuer=Logforge&digits={DIGITS}&period={STEP}"


def _normalise_backup(code: str) -> str:
    return (code or "").strip().replace("-", "").replace(" ", "").upper()


def _hash_backup(code: str) -> str:
    return hashlib.sha256(_normalise_backup(code).encode()).hexdigest()


def new_backup_codes(n: int = 8) -> Tuple[List[str], List[str]]:
    codes = []
    for _ in range(n):
        raw = secrets.token_hex(5).upper()
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes, [_hash_backup(c) for c in codes]


def use_backup_code(hashes: List[str], code: str) -> Optional[List[str]]:
    """The remaining hashes if `code` is one of them (it's used up), else None."""
    h = _hash_backup(code)
    if not _normalise_backup(code) or not any(hmac.compare_digest(h, x) for x in hashes):
        return None
    return [x for x in hashes if x != h]


def _challenge_key() -> str:
    from authn_authz_middleware import JWT_SECRET

    return "mfa-challenge:" + JWT_SECRET


def challenge(user_id: str, ttl: int = 300) -> str:
    return jwt.encode({"sub": user_id, "aud": CHALLENGE_AUDIENCE, "exp": int(time.time()) + ttl},
                      _challenge_key(), algorithm="HS256")


def open_challenge(token: str) -> str:
    try:
        return jwt.decode(token or "", _challenge_key(), algorithms=["HS256"], audience=CHALLENGE_AUDIENCE)["sub"]
    except jwt.PyJWTError as e:
        raise MFAError(f"the sign-in expired; start again ({e})")


class MFAStore:
    """user_mfa_mt, with the secret sealed (integrations/secrets.py)."""

    def __init__(self, client, box=None):
        from integrations.secrets import SecretBox

        self.client = client
        self.box = box or SecretBox.from_env()

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        rows = self.client.query(
            "SELECT argMax(secret, updated_at), argMax(confirmed, updated_at), argMax(backup_hashes, updated_at), "
            "argMax(last_step, updated_at), argMax(deleted, updated_at) FROM user_mfa_mt "
            "WHERE user_id = {user:String} GROUP BY user_id", parameters={"user": user_id}).result_rows
        if not rows or rows[0][4]:
            return None
        sealed, confirmed, hashes, last_step, _ = rows[0]
        return {"secret": self.box.open(sealed).get("secret", ""), "confirmed": bool(confirmed),
                "backup_hashes": list(hashes), "last_step": int(last_step)}

    def save(self, user_id: str, record: Dict[str, Any], deleted: bool = False) -> None:
        self.client.insert("user_mfa_mt", [[
            user_id, self.box.seal({"secret": record.get("secret", "")}), int(record.get("confirmed", False)),
            list(record.get("backup_hashes") or []), int(record.get("last_step", 0)), int(deleted)]],
            column_names=["user_id", "secret", "confirmed", "backup_hashes", "last_step", "deleted"])

    def delete(self, user_id: str) -> None:
        self.save(user_id, {}, deleted=True)
