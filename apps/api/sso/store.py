"""OIDC providers per tenant (sso_providers_mt), with the client secret sealed."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from integrations.secrets import SecretBox

from .oidc import Provider

COLUMNS = ["customer_id", "id", "name", "issuer", "client_id", "client_secret", "scopes", "groups_claim",
           "role_mapping", "default_role", "allowed_domains", "enabled", "deleted", "updated_by"]


class ProviderStore:
    def __init__(self, client, box: Optional[SecretBox] = None):
        self.client = client
        self.box = box or SecretBox.from_env()

    def _rows(self, where: str, params: Dict[str, Any]) -> List[Provider]:
        latest = ", ".join(f"argMax({c}, updated_at)" for c in COLUMNS[2:])
        rows = self.client.query(
            f"SELECT customer_id, id, {latest} FROM sso_providers_mt {where} GROUP BY customer_id, id",
            parameters=params).result_rows
        out = []
        for r in rows:
            row = dict(zip(COLUMNS, r))
            if row["deleted"]:
                continue
            secret = self.box.open(row["client_secret"]).get("client_secret", "") if row["client_secret"] else ""
            out.append(Provider(id=row["id"], tenant_id=row["customer_id"], name=row["name"], issuer=row["issuer"],
                                client_id=row["client_id"], client_secret=secret, scopes=row["scopes"],
                                groups_claim=row["groups_claim"], role_mapping=json.loads(row["role_mapping"] or "{}"),
                                default_role=row["default_role"] or None, allowed_domains=list(row["allowed_domains"]),
                                enabled=bool(row["enabled"])))
        return out

    def list(self, tenant_id: str) -> List[Provider]:
        return self._rows("WHERE customer_id = {tenant:String}", {"tenant": tenant_id})

    def get(self, provider_id: str, tenant_id: Optional[str] = None) -> Optional[Provider]:
        where = "WHERE id = {id:String}" + (" AND customer_id = {tenant:String}" if tenant_id else "")
        found = self._rows(where, {"id": provider_id, "tenant": tenant_id or ""})
        return found[0] if found else None

    def for_domain(self, domain: str) -> List[Provider]:
        return [p for p in self._rows("WHERE has(allowed_domains, {domain:String})", {"domain": domain.lower()})
                if p.enabled]

    def save(self, provider: Provider, user_id: str, deleted: bool = False) -> Provider:
        provider.id = provider.id or uuid.uuid4().hex
        sealed = self.box.seal({"client_secret": provider.client_secret}) if provider.client_secret else ""
        self.client.insert("sso_providers_mt", [[
            provider.tenant_id, provider.id, provider.name, provider.issuer, provider.client_id, sealed,
            provider.scopes, provider.groups_claim, json.dumps(provider.role_mapping), provider.default_role or "",
            [d.lower().lstrip("@") for d in provider.allowed_domains], int(provider.enabled), int(deleted),
            user_id or ""]], column_names=COLUMNS)
        return provider


def public(provider: Provider) -> Dict[str, Any]:
    out = {k: v for k, v in provider.__dict__.items() if k != "client_secret"}
    out["client_secret_set"] = bool(provider.client_secret)
    return out
