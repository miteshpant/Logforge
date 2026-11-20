"""
API key scopes. A key lists permissions such as `logs:write` or
`metrics:read` when it's created; a request made with the key must fit
within them as well as within the key's service-account role.

Keys created without permissions (before scopes were enforced) keep full
access to their tenant, so existing ingest keys don't break; create a key
with permissions to restrict it.
"""

from __future__ import annotations

from typing import Iterable

# The endpoint map files metrics and traces under `observability`.
ALIASES = {"metrics": "observability", "traces": "observability"}


def allows(key_permissions: Iterable[str], required: str) -> bool:
    permissions = list(key_permissions or [])
    if not permissions:
        return True
    resource, action, scope = required.split(":")
    if scope == "platform":
        return False
    if resource == "queries":  # running searches and saved queries reads logs
        resource, action = "logs", "read"
    for p in permissions:
        r, _, a = p.partition(":")
        r = ALIASES.get(r, r)
        if r == resource and (a == "*" or action in a.split(",")):
            return True
    return False
