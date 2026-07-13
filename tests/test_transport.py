from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from sea_agent_sdk import APIError, Transport, normalize_agent_gateway_endpoint


class TransportTests(unittest.TestCase):
    def test_normalize_agent_gateway_endpoint(self) -> None:
        cases = [
            ("http://127.0.0.1:8080", "http://127.0.0.1:8080/agent-v2"),
            ("http://127.0.0.1:8080/", "http://127.0.0.1:8080/agent-v2"),
            ("http://127.0.0.1:8080/agent-v2", "http://127.0.0.1:8080/agent-v2"),
            ("http://127.0.0.1:8080/agent-v2/", "http://127.0.0.1:8080/agent-v2/"),
            ("https://example.com/api", "https://example.com/api/agent-v2"),
            ("https://example.com?debug=1", "https://example.com/agent-v2?debug=1"),
            ("", ""),
        ]
        for endpoint, expected in cases:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(normalize_agent_gateway_endpoint(endpoint), expected)

    def test_build_url_adds_agent_v2_fallback(self) -> None:
        transport = Transport("http://127.0.0.1:8080")
        self.assertEqual(
            transport.build_url("/v1/tools", {"limit": 20}),
            "http://127.0.0.1:8080/agent-v2/v1/tools?limit=20",
        )

        transport = Transport("http://127.0.0.1:8080/agent-v2")
        self.assertEqual(
            transport.build_url("/v1/tools"),
            "http://127.0.0.1:8080/agent-v2/v1/tools",
        )

    def test_query_zero_values_match_go_sdk(self) -> None:
        transport = Transport("http://127.0.0.1:8080")
        self.assertEqual(
            transport.build_url(
                "/v1/tools",
                {
                    "search": "",
                    "limit": 0,
                    "include_deleted": False,
                    "public": None,
                    "status": "active",
                },
            ),
            "http://127.0.0.1:8080/agent-v2/v1/tools?include_deleted=false&status=active",
        )

    def test_headers_include_authorization_unless_overridden(self) -> None:
        transport = Transport(
            "http://127.0.0.1:8080",
            api_key="secret",
            headers={"X-User-ID": "user_1"},
        )
        headers = transport.build_headers("application/json", True, {"X-Trace-ID": "trace_1"})
        self.assertEqual(headers["Authorization"], "Bearer secret")
        self.assertEqual(headers["X-User-ID"], "user_1")
        self.assertEqual(headers["X-Trace-ID"], "trace_1")

        headers = transport.build_headers("*/*", False, {"authorization": "Bearer other"})
        self.assertEqual(headers["authorization"], "Bearer other")
        self.assertNotIn("Authorization", headers)

    def test_stream_decodes_utf8_across_read_boundaries(self) -> None:
        encoded = "data: 你\n\n".encode("utf-8")
        split = encoded.index("你".encode("utf-8")) + 1
        response = _ChunkedResponse([encoded[:split], encoded[split:], b""])
        chunks: list[str] = []

        with patch("sea_agent_sdk.transport.request.urlopen", return_value=response):
            Transport("http://127.0.0.1:8080").get_stream("/v1/test", None, chunks.append)

        self.assertEqual("".join(chunks), "data: 你\n\n")

    def test_websocket_handshake_status_is_reported_as_api_error(self) -> None:
        class BadStatusError(Exception):
            def __init__(self, status_code: int, resp_body: bytes) -> None:
                self.status_code = status_code
                self.resp_body = resp_body

        fake_websocket = types.SimpleNamespace(
            WebSocketBadStatusException=BadStatusError,
            create_connection=lambda *args, **kwargs: (_ for _ in ()).throw(
                BadStatusError(401, b'{"error":"unauthorized"}')
            ),
        )

        with patch.dict(sys.modules, {"websocket": fake_websocket}):
            with self.assertRaises(APIError) as raised:
                Transport("http://127.0.0.1:8080").websocket(
                    "/v1/chat/completions/ws", None, None, lambda message: None
                )

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.message, "unauthorized")


class _ChunkedResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = iter(chunks)

    def read(self, size: int = -1) -> bytes:
        return next(self.chunks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
