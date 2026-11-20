"""Field-level masking: a custom role can mask fields (password, email, ...) for
its holders. JSON responses have those keys' values replaced at any depth, also
inside JSON-encoded strings such as a log's attrs; requests that name a masked
field are refused (a query could otherwise rename it); responses that aren't
JSON (streams, CSV, PDF) are refused because they can't be masked."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import custom_roles  # noqa: E402
import field_masking as fm  # noqa: E402

FIELDS = fm.normalise_fields(["password", "attrs.Email"])


def test_names_are_normalised_to_their_last_segment():
    assert FIELDS == frozenset({"password", "email"})


def test_values_are_masked_at_any_depth():
    body = {"logs": [{"msg": "login", "attrs": {"email": "a@b.c", "nested": {"Password": "s3cret"}}, "level": "info"}],
            "total": 1}
    out = fm.mask(body, FIELDS)
    assert out["logs"][0]["attrs"]["email"] == fm.MASK
    assert out["logs"][0]["attrs"]["nested"]["Password"] == fm.MASK
    assert out["logs"][0]["msg"] == "login" and out["total"] == 1


def test_json_encoded_strings_are_masked_too():
    out = fm.mask({"attrs": json.dumps({"email": "a@b.c", "ok": 1})}, FIELDS)
    assert json.loads(out["attrs"]) == {"email": fm.MASK, "ok": 1}


def test_tabular_results_mask_columns_by_name():
    out = fm.mask({"columns": ["service", "email"], "rows": [["auth", "a@b.c"]]}, FIELDS)
    assert out["rows"] == [["auth", fm.MASK]]


def test_requests_naming_a_masked_field_are_found():
    assert fm.mentions({"query": "| eval e = attrs.email | stats count() by e"}, FIELDS) == "email"
    assert fm.mentions({"query": "| stats count() by service"}, FIELDS) is None
    assert fm.mentions({"q": ["x", {"deep": "PASSWORD reset"}]}, FIELDS) == "password"
    assert fm.mentions({"query": "emails sent"}, FIELDS) is None  # whole words only


def test_roles_union_their_masked_fields():
    roles = [custom_roles.CustomRole(id="1", tenant_id="t", name="a", masked_fields=["email"]),
             custom_roles.CustomRole(id="2", tenant_id="t", name="b", masked_fields=["password"]),
             custom_roles.CustomRole(id="3", tenant_id="t", name="c")]
    assert custom_roles.masked_fields(roles) == frozenset({"email", "password"})


# -- the middleware's two steps -------------------------------------------------------------

import asyncio  # noqa: E402

from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, PlainTextResponse, StreamingResponse  # noqa: E402


def _request(path, body=b"", query=b"", method="POST"):
    sent = {"done": False}

    async def receive():
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({"type": "http", "method": method, "path": path, "query_string": query,
                    "headers": [(b"content-type", b"application/json")]}, receive)


def test_requests_naming_a_masked_field_are_refused():
    from authn_authz_middleware import _masking_refusal

    refused = asyncio.run(_masking_refusal(_request("/v1/query/logql", b'{"query": "| stats count() by email"}'),
                                           FIELDS))
    assert refused.status_code == 403 and b"email" in refused.body
    assert asyncio.run(_masking_refusal(_request("/v1/query/logql", b'{"query": "| stats count() by service"}'),
                                        FIELDS)) is None
    assert asyncio.run(_masking_refusal(_request("/v1/logs", query=b"q=password", method="GET"), FIELDS)) is not None
    assert asyncio.run(_masking_refusal(_request("/v1/auth/password/change", b'{"new_password": "x"}'),
                                        FIELDS)) is None  # own account


def test_json_answers_are_masked_and_others_refused():
    from authn_authz_middleware import _masked_response

    masked = asyncio.run(_masked_response(JSONResponse({"logs": [{"attrs": {"email": "a@b.c"}}]}), FIELDS))
    assert json.loads(masked.body) == {"logs": [{"attrs": {"email": fm.MASK}}]}

    async def lines():
        yield b"data: {}\n\n"

    assert asyncio.run(_masked_response(StreamingResponse(lines(), media_type="text/event-stream"),
                                        FIELDS)).status_code == 403
    assert asyncio.run(_masked_response(PlainTextResponse("a,b"), FIELDS)).status_code == 403
    assert asyncio.run(_masked_response(JSONResponse({"detail": "x"}, status_code=404), FIELDS)).status_code == 404


def test_ai_tools_redact_masked_fields():
    from ai import assistant

    token = fm.set_fields(frozenset({"email"}))
    try:
        assert assistant._redact_fields(["token"]) == ["email", "token"]
    finally:
        fm.reset(token)
