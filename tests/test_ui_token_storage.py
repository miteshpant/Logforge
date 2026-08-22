"""
Tests for ENH-018 (partial) -- browser token storage hardening.

The tenant UI keeps its JWT in a JS-readable cookie and the admin UI keeps the
PLATFORM ADMIN token in `localStorage`. Either means one XSS anywhere in the
application yields full account takeover -- and in the admin case, platform-wide
administrative takeover.

The complete fix (httpOnly cookies issued by the API plus CSRF protection) is an
auth-flow change spanning the API and both UIs, so it is deliberately NOT done
here. What this ticket did deliver is checked below:

* `Secure` is no longer conditional on the current page protocol, which
  previously let a plain-HTTP deployment send bearer tokens in the clear.
* The refresh-token lifetime is reduced from 30 days to 7.
* The remaining weakness is documented in-source rather than left silent.

These are text assertions over the TypeScript sources; there is no JS toolchain
in this test environment.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
UI_CLIENT = REPO / "apps" / "ui" / "lib" / "api" / "client.ts"
ADMIN_AUTH = REPO / "apps" / "admin-ui" / "src" / "lib" / "auth.ts"


@pytest.fixture(scope="module")
def ui_source():
    return UI_CLIENT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def admin_source():
    return ADMIN_AUTH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Secure flag
# ---------------------------------------------------------------------------


def test_secure_flag_is_not_tied_to_current_page_protocol(ui_source):
    """
    `secure: window.location.protocol === 'https:'` meant a deployment served
    over plain HTTP silently omitted Secure and leaked tokens in the clear.
    """
    assert "const isSecure = window.location.protocol === 'https:'" not in ui_source, (
        "Secure must not be derived from the current page protocol."
    )


def test_secure_is_disabled_only_for_localhost(ui_source):
    """HTTPS is impractical for local development; everywhere else gets Secure."""
    assert "isLocalhost" in ui_source
    assert "const secure = !isLocalhost" in ui_source


def test_all_auth_cookies_use_the_secure_flag(ui_source):
    for key in ("AUTH_TOKEN_KEY", "TENANT_ID_KEY", "REFRESH_TOKEN_KEY"):
        index = ui_source.index(f"Cookies.set({key}")
        statement = ui_source[index:index + 220]
        assert "secure" in statement, f"{key} cookie is set without Secure"


def test_all_auth_cookies_use_samesite_strict(ui_source):
    for key in ("AUTH_TOKEN_KEY", "TENANT_ID_KEY", "REFRESH_TOKEN_KEY"):
        index = ui_source.index(f"Cookies.set({key}")
        statement = ui_source[index:index + 220]
        assert "sameSite: 'strict'" in statement, f"{key} lacks SameSite=strict"


# ---------------------------------------------------------------------------
# Token lifetime
# ---------------------------------------------------------------------------


def test_refresh_token_lifetime_is_reduced(ui_source):
    """
    A 30-day refresh token in a JS-readable cookie is a 30-day takeover window.
    Reduced to 7 days until httpOnly lands.
    """
    index = ui_source.index("Cookies.set(REFRESH_TOKEN_KEY")
    statement = ui_source[index:index + 220]

    assert "expires: 7" in statement
    assert "expires: 30" not in statement


def test_access_token_lifetime_is_short(ui_source):
    index = ui_source.index("Cookies.set(AUTH_TOKEN_KEY")
    statement = ui_source[index:index + 220]
    assert "expires: 1" in statement


# ---------------------------------------------------------------------------
# The remaining weakness must stay visible
# ---------------------------------------------------------------------------


def test_ui_documents_the_remaining_xss_exposure(ui_source):
    assert "ENH-018" in ui_source
    assert "httpOnly" in ui_source, (
        "The residual risk and its fix must be documented at the call site."
    )


def test_admin_ui_localstorage_weakness_is_documented(admin_source):
    """
    The admin token is the highest-value credential in the system. Storing it in
    localStorage is worse than the tenant UI's cookies, and that must not sit
    silently in the code.
    """
    assert "ENH-018" in admin_source
    assert "localStorage" in admin_source
    assert "takeover" in admin_source.lower()


def test_admin_ui_still_uses_localstorage_as_documented(admin_source):
    """
    Pins the current state. When ENH-018 completes, this test should fail and be
    replaced by one asserting the token is no longer JS-readable.
    """
    assert "localStorage.setItem('admin_token'" in admin_source
