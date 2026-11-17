"""
Decode gzip-compressed request bodies, with a bound on the decompressed size.

Log shippers compress batches (Fluent Bit `Compress gzip`, Vector
`compression = "gzip"`, Fluentd `compress gzip`). Without this, the API handed
the compressed bytes to JSON parsing and every compressed batch failed with
400 "There was an error parsing the body".

This is a pure ASGI middleware, so it can replace the body before routing and
works with streaming bodies.

* `Content-Encoding: gzip` (or `x-gzip`) bodies are inflated incrementally and
  passed on with the header removed and `Content-Length` set to the
  decompressed size, so handlers see an ordinary request.
* The decompressed size is capped (by default at the request body limit,
  `LOGFORGE_MAX_BODY_BYTES`): a few KB of compressed zeros can inflate to
  gigabytes, so exceeding the cap returns 413 without inflating further.
* A corrupt stream returns 400; any other encoding returns 415.
* The compressed size on the wire is still checked against `Content-Length`
  by `RequestLimitsMiddleware`.
"""

from __future__ import annotations

import json
import os
import zlib
from typing import Optional

from request_limits import DEFAULT_MAX_BODY_BYTES

_GZIP_ENCODINGS = {"gzip", "x-gzip"}
_READ_CHUNK = 64 * 1024


def default_max_decompressed_bytes() -> int:
    return int(os.getenv("LOGFORGE_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES))


class _TooLarge(Exception):
    pass


class RequestDecompressionMiddleware:
    def __init__(self, app, max_decompressed_bytes: Optional[int] = None):
        self.app = app
        self.max_bytes = max_decompressed_bytes or default_max_decompressed_bytes()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = scope.get("headers") or []
        encoding = None
        for name, value in headers:
            if name.lower() == b"content-encoding":
                encoding = value.decode("latin-1").strip().lower()
                break
        if not encoding or encoding == "identity":
            return await self.app(scope, receive, send)

        if encoding not in _GZIP_ENCODINGS:
            return await self._error(send, 415, "unsupported_content_encoding",
                                     f"Content-Encoding {encoding!r} is not supported; use gzip.")

        try:
            body = await self._inflate(receive)
        except _TooLarge:
            return await self._error(send, 413, "request_entity_too_large",
                                     f"Decompressed body exceeds the {self.max_bytes} byte limit.",
                                     max_bytes=self.max_bytes)
        except zlib.error:
            return await self._error(send, 400, "invalid_content_encoding",
                                     "Request body is not valid gzip.")

        new_headers = [
            (name, value) for name, value in headers
            if name.lower() not in (b"content-encoding", b"content-length")
        ]
        new_headers.append((b"content-length", str(len(body)).encode()))
        scope = dict(scope, headers=new_headers)

        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()  # e.g. http.disconnect

        return await self.app(scope, replay, send)

    async def _inflate(self, receive) -> bytes:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)  # gzip framing
        out = bytearray()
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            chunk = message.get("body", b"")
            more = message.get("more_body", False)
            while chunk:
                # Bound each step so a bomb can't allocate past the cap.
                room = self.max_bytes - len(out) + 1
                out += decoder.decompress(chunk, max(room, 1))
                if len(out) > self.max_bytes:
                    raise _TooLarge()
                chunk = decoder.unconsumed_tail
        out += decoder.flush()
        if len(out) > self.max_bytes:
            raise _TooLarge()
        if not decoder.eof:
            raise zlib.error("truncated gzip stream")
        return bytes(out)

    @staticmethod
    async def _error(send, status: int, error: str, message: str, **extra) -> None:
        body = json.dumps({"error": error, "message": message, **extra}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
