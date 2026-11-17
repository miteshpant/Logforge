"""
The API accepts gzip-compressed request bodies.

Shippers (Fluent Bit `Compress gzip`, Vector `compression = "gzip"`, Fluentd
`compress gzip`) compress batches, but the API passed the compressed bytes
straight to JSON parsing and returned 400 "There was an error parsing the
body", so the shipper recipes had to leave compression off.

Decoding is bounded: the decompressed size is capped at the request body
limit, so a small "zip bomb" cannot exhaust memory.
"""

import gzip
import json
import zlib

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from request_decompression import RequestDecompressionMiddleware


def _app(max_bytes=1024 * 1024):
    app = FastAPI()
    app.add_middleware(RequestDecompressionMiddleware, max_decompressed_bytes=max_bytes)

    @app.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        return {
            "body": json.loads(body),
            "content_encoding": request.headers.get("content-encoding"),
            "content_length": request.headers.get("content-length"),
        }

    return app


PAYLOAD = [{"service": "svc", "msg": f"line {i}"} for i in range(50)]


def test_gzip_body_is_decoded_before_the_handler():
    raw = json.dumps(PAYLOAD).encode()
    response = TestClient(_app()).post(
        "/echo", content=gzip.compress(raw),
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )

    assert response.status_code == 200
    out = response.json()
    assert out["body"] == PAYLOAD
    # The handler sees an ordinary, uncompressed request.
    assert out["content_encoding"] is None
    assert out["content_length"] == str(len(raw))


def test_x_gzip_alias_is_accepted():
    response = TestClient(_app()).post(
        "/echo", content=gzip.compress(b'{"a": 1}'),
        headers={"Content-Type": "application/json", "Content-Encoding": "x-gzip"},
    )
    assert response.status_code == 200
    assert response.json()["body"] == {"a": 1}


def test_uncompressed_requests_are_untouched():
    response = TestClient(_app()).post("/echo", json={"a": 1})
    assert response.status_code == 200
    assert response.json()["body"] == {"a": 1}


def test_decompression_bomb_is_rejected_with_413():
    bomb = gzip.compress(b"0" * (5 * 1024 * 1024))  # ~5 KB compressed, 5 MiB inflated
    response = TestClient(_app(max_bytes=1024 * 1024)).post(
        "/echo", content=bomb,
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )
    assert response.status_code == 413
    assert response.json()["error"] == "request_entity_too_large"


def test_corrupt_gzip_is_rejected_with_400():
    response = TestClient(_app()).post(
        "/echo", content=b"\x1f\x8b\x08\x00not really gzip",
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_content_encoding"


def test_unsupported_encoding_is_rejected_with_415():
    response = TestClient(_app()).post(
        "/echo", content=zlib.compress(b'{"a": 1}'),
        headers={"Content-Type": "application/json", "Content-Encoding": "br"},
    )
    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_content_encoding"


def test_middleware_is_installed_on_the_api():
    import main

    installed = [m.cls for m in main.app.user_middleware]
    assert RequestDecompressionMiddleware in installed


def test_default_cap_matches_the_request_body_limit(monkeypatch):
    from request_decompression import default_max_decompressed_bytes
    from request_limits import DEFAULT_MAX_BODY_BYTES

    monkeypatch.delenv("LOGFORGE_MAX_BODY_BYTES", raising=False)
    assert default_max_decompressed_bytes() == DEFAULT_MAX_BODY_BYTES
    monkeypatch.setenv("LOGFORGE_MAX_BODY_BYTES", "2048")
    assert default_max_decompressed_bytes() == 2048
