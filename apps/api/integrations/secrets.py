"""
Integration secrets (Phase 13): API tokens, webhook URLs with embedded
credentials, routing keys. Sealed with Fernet (AES-128-CBC + HMAC-SHA256)
under LOGFORGE_SECRETS_KEY before they are stored; the API never returns
them, only which names are set.

Outside development a key is required. In development, without one, a key
is derived from JWT_SECRET so the compose stack works out of the box.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Dict

from cryptography.fernet import Fernet, InvalidToken


class SecretError(RuntimeError):
    pass


def new_key() -> str:
    return Fernet.generate_key().decode()


class SecretBox:
    def __init__(self, key: str):
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError) as e:
            raise SecretError(f"LOGFORGE_SECRETS_KEY is not a valid key: {e}") from None

    @classmethod
    def from_env(cls) -> "SecretBox":
        key = os.getenv("LOGFORGE_SECRETS_KEY", "")
        if key:
            return cls(key)
        from security_config import is_enforced

        if is_enforced():
            raise SecretError("LOGFORGE_SECRETS_KEY is required to store integration secrets "
                              "(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')")
        seed = os.getenv("JWT_SECRET", "logforge-development")
        derived = base64.urlsafe_b64encode(hashlib.sha256(("integrations:" + seed).encode()).digest())
        return cls(derived.decode())

    def seal(self, values: Dict[str, str]) -> str:
        return self._fernet.encrypt(json.dumps(values).encode()).decode() if values else ""

    def open(self, sealed: str) -> Dict[str, str]:
        if not sealed:
            return {}
        try:
            return json.loads(self._fernet.decrypt(sealed.encode()))
        except InvalidToken:
            raise SecretError("integration secrets can't be decrypted: LOGFORGE_SECRETS_KEY changed?") from None
