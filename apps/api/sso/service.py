"""
Who an OIDC sign-in becomes (Phase 14).

- A new address gets an account (active, its email verified by the IdP,
  with a random password nobody knows) and the role its groups map to.
- An existing account may sign in through a tenant's IdP only if all its
  roles are in that tenant. Otherwise an IdP set up by one tenant's admin
  could sign in as another tenant's user by asserting their address.
- The IdP is the source of the role: the mapped role is granted and any
  other role in the tenant removed, so removing someone from a group
  takes effect at their next sign-in. With no role mapped and none held,
  the sign-in is refused.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from .oidc import OIDCError, Provider, email_of, resolve_role


class SignInRefused(OIDCError):
    pass


def _role_value(r) -> str:
    role = r.role if hasattr(r, "role") else r["role"]
    return getattr(role, "value", role)


def _tenant(r) -> str:
    return r.tenant_id if hasattr(r, "tenant_id") else r["tenant_id"]


async def complete_sign_in(provider: Provider, claims: Dict[str, Any], users, roles) -> Tuple[Any, str]:
    from models import UserRole, UserStatus

    email = email_of(claims, provider)
    mapped = resolve_role(claims, provider)
    user = await users.get_user_by_email(email)
    if user is None:
        if not mapped:
            raise SignInRefused("your groups don't give you a role in Logforge; ask your administrator")
        user = await users.create_user({
            "email": email, "name": str(claims.get("name") or email.split("@")[0]),
            "password": secrets.token_urlsafe(32) + "Aa1!", "status": UserStatus.ACTIVE})
        await users.update_user(user.id, {"email_verified_at": datetime.now(timezone.utc)})
        held = []
    else:
        if getattr(user.status, "value", user.status) != UserStatus.ACTIVE.value:
            raise SignInRefused("this account isn't active")
        held = await roles.get_user_roles(user.id)
        if any(_tenant(r) != provider.tenant_id for r in held):
            raise SignInRefused("this account has access outside this organisation; sign in with its password")
    current = {_role_value(r) for r in held if _tenant(r) == provider.tenant_id}
    if mapped:
        if mapped not in current:
            await roles.assign_role(user_id=user.id, tenant_id=provider.tenant_id, role=UserRole(mapped),
                                    granted_by=f"sso:{provider.id}")
        for other in current - {mapped}:
            await roles.remove_role(user.id, provider.tenant_id, UserRole(other))
        return user, mapped
    if not current:
        raise SignInRefused("your groups don't give you a role in Logforge; ask your administrator")
    return user, sorted(current)[0]
