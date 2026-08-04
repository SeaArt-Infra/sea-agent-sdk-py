from __future__ import annotations

import unittest

from sea_agent_sdk.resources import McpsResource
from sea_agent_sdk.types import MCPListOptions


class McpsResourceTests(unittest.TestCase):
    def test_methods_use_mcp_management_routes(self) -> None:
        transport = _RecordingTransport()
        mcps = McpsResource(transport)
        server = {"name": "sea-search", "server_url": "https://mcp.example.com/mcp"}
        call = {"name": "search", "arguments": {"query": "hello"}}

        mcps.register(server)
        mcps.list(MCPListOptions(status="active", include_deleted=True, limit=10))
        mcps.get("mcp/1")
        mcps.update("mcp-1", server)
        mcps.delete("mcp-1")
        mcps.tools("mcp-1")
        mcps.call("mcp-1", call)

        self.assertEqual(
            transport.requests,
            [
                ("POST", "/v1/mcps/register", server),
                (
                    "GET",
                    "/v1/mcps",
                    {
                        "search": "",
                        "status": "active",
                        "public": None,
                        "provider": "",
                        "include_deleted": True,
                        "limit": 10,
                        "offset": 0,
                    },
                ),
                ("GET", "/v1/mcps/mcp%2F1", None),
                ("PUT", "/v1/mcps/mcp-1", server),
                ("DELETE", "/v1/mcps/mcp-1", None),
                ("GET", "/v1/mcps/mcp-1/tools", None),
                ("POST", "/v1/mcps/mcp-1/call", call),
            ],
        )


class _RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, object]] = []

    def get_json(self, path: str, query=None):
        self.requests.append(("GET", path, query))

    def post_json(self, path: str, payload):
        self.requests.append(("POST", path, payload))

    def put_json(self, path: str, payload):
        self.requests.append(("PUT", path, payload))

    def delete_json(self, path: str):
        self.requests.append(("DELETE", path, None))


if __name__ == "__main__":
    unittest.main()
