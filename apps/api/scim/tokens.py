"""SCIM bearer tokens: one or more per tenant, shown once, stored as SHA-256 hashes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from typing import Any, Dict, List, Optional, Tuple

PREFIX = "lfscim_"


def new_token() -> Tuple[str, str]:
    plain = PREFIX + secrets.token_urlsafe(32)
    return plain, digest(plain)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class TokenStore:
    def __init__(self, client):
        self.client = client

    def _rows(self, where: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = self.client.query(
            "SELECT customer_id, id, argMax(name, updated_at), argMax(token_hash, updated_at), "
            "argMax(revoked, updated_at), argMax(created_by, updated_at), min(updated_at) "
            f"FROM scim_tokens_mt {where} GROUP BY customer_id, id", parameters=params).result_rows
        keys = ["tenant_id", "id", "name", "token_hash", "revoked", "created_by", "created_at"]
        return [dict(zip(keys, r)) for r in rows]

    def create(self, tenant_id: str, name: str, user_id: str) -> Dict[str, Any]:
        plain, hashed = new_token()
        tid = uuid.uuid4().hex
        self.client.insert("scim_tokens_mt", [[tenant_id, tid, name, hashed, 0, user_id or ""]],
                           column_names=["customer_id", "id", "name", "token_hash", "revoked", "created_by"])
        return {"id": tid, "name": name, "token": plain}

    def list(self, tenant_id: str) -> List[Dict[str, Any]]:
        return [{k: (str(v) if k == "created_at" else v) for k, v in r.items() if k != "token_hash"}
                for r in self._rows("WHERE customer_id = {tenant:String}", {"tenant": tenant_id}) if not r["revoked"]]

    def revoke(self, tenant_id: str, token_id: str) -> bool:
        found = [r for r in self._rows("WHERE customer_id = {tenant:String} AND id = {id:String}",
                                       {"tenant": tenant_id, "id": token_id}) if not r["revoked"]]
        if not found:
            return False
        r = found[0]
        self.client.insert("scim_tokens_mt", [[tenant_id, token_id, r["name"], r["token_hash"], 1, r["created_by"]]],
                           column_names=["customer_id", "id", "name", "token_hash", "revoked", "created_by"])
        return True

    def resolve(self, token: str) -> Optional[str]:
        if not token.startswith(PREFIX):
            return None
        hashed = digest(token)
        for r in self._rows("WHERE token_hash = {hash:String}", {"hash": hashed}):
            if not r["revoked"] and hmac.compare_digest(r["token_hash"], hashed):
                return r["tenant_id"]
        return None


class LinkStore:
    """The IdP's externalId for each provisioned user, per tenant."""

    def __init__(self, client):
        self.client = client

    def get(self, tenant_id: str, user_id: str) -> Optional[str]:
        rows = self.client.query(
            "SELECT argMax(external_id, updated_at) FROM scim_links_mt WHERE customer_id = {tenant:String} "
            "AND user_id = {user:String}", parameters={"tenant": tenant_id, "user": user_id}).result_rows
        return rows[0][0] or None if rows else None

    def set(self, tenant_id: str, user_id: str, external_id: Optional[str]) -> None:
        self.client.insert("scim_links_mt", [[tenant_id, user_id, external_id or ""]],
                           column_names=["customer_id", "user_id", "external_id"])
