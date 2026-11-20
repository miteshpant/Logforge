"""
Account emails (Phase 14): password reset, invitations, email
verification. Links point at LOGFORGE_PUBLIC_URL (the UI's address).

Sent through the email integration's SMTP path (LOGFORGE_SMTP_HOST, _PORT,
_FROM; integrations/actions.py). If SMTP isn't configured the email isn't
sent and a warning is logged; the API answers the same either way, so a
failure doesn't reveal whether an account exists.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def public_url() -> str:
    return os.getenv("LOGFORGE_PUBLIC_URL", "http://localhost:3000").rstrip("/")


def _link(path: str, **query: str) -> str:
    return f"{public_url()}{path}?{urlencode(query)}"


def reset_message(email: str, token: str) -> Dict[str, Any]:
    return {"to": [email], "subject": "Reset your Logforge password",
            "body": "Someone asked to reset the password of your Logforge account.\n\n"
                    f"To choose a new one, open {_link('/reset-password', token=token)} within an hour.\n\n"
                    "If it wasn't you, ignore this email: your password hasn't changed."}


def invite_message(email: str, token: str, tenant_id: str, role: str, inviter: str) -> Dict[str, Any]:
    link = _link("/accept-invite", token=token, email=email, tenant=tenant_id)
    return {"to": [email], "subject": "You're invited to Logforge",
            "body": f"{inviter} invited you to Logforge as {role.replace('_', ' ')}.\n\n"
                    f"To create your account, open {link} within 7 days."}


def verify_message(email: str, token: str) -> Dict[str, Any]:
    return {"to": [email], "subject": "Confirm your email address for Logforge",
            "body": f"To confirm this address, open {_link('/verify-email', token=token)} within 24 hours."}


async def send(message: Dict[str, Any]) -> bool:
    from integrations import actions

    result = await actions.run("email", {}, {}, message, {}, render=False)
    if not result.ok:
        logger.warning("Account email to %s not sent: %s", ", ".join(message["to"]), result.error)
    return result.ok
