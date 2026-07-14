from __future__ import annotations

import unittest

from sea_agent_sdk import HookRequest
from sea_agent_sdk.resources import HooksResource


class HooksResourceTests(unittest.TestCase):
    def test_methods_use_api_key_scoped_routes_without_hook_ids(self) -> None:
        transport = _RecordingTransport()
        hooks = HooksResource(transport)  # type: ignore[arg-type]
        payload = HookRequest(
            name="production-line-hook",
            endpoint="https://example.com/agent-hook",
            description="Receives multimodal charge reservation events.",
        )

        hooks.register(payload)
        hooks.update(payload)
        hooks.delete()

        self.assertEqual(
            transport.requests,
            [
                ("POST", "/v1/hooks/register", payload),
                ("PUT", "/v1/hooks", payload),
                ("DELETE", "/v1/hooks", None),
            ],
        )


class _RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, object | None]] = []

    def post_json(self, path: str, body: object) -> dict[str, bool]:
        self.requests.append(("POST", path, body))
        return {"ok": True}

    def put_json(self, path: str, body: object) -> dict[str, bool]:
        self.requests.append(("PUT", path, body))
        return {"ok": True}

    def delete_json(self, path: str) -> dict[str, bool]:
        self.requests.append(("DELETE", path, None))
        return {"ok": True}


if __name__ == "__main__":
    unittest.main()
