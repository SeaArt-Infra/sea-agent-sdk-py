from __future__ import annotations

import copy
import unittest

from sea_agent_sdk.resources import SkillsResource


class SkillsResourceTests(unittest.TestCase):
    def test_register_and_update_preserve_mcp_server_bindings(self) -> None:
        transport = _RecordingTransport()
        skills = SkillsResource(transport)
        payload = {
            "name": "mcp-research",
            "config": {
                "mcp_servers": ["11111111-1111-4111-8111-111111111111"],
            },
        }
        expected_payload = copy.deepcopy(payload)

        skills.register(payload)
        skills.update("skill-1", payload)

        self.assertEqual(
            transport.requests,
            [
                ("POST", "/v1/skills/register", expected_payload),
                ("PUT", "/v1/skills/skill-1", expected_payload),
            ],
        )
        self.assertEqual(payload, expected_payload)


class _RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, object]] = []

    def post_json(self, path: str, payload):
        self.requests.append(("POST", path, payload))

    def put_json(self, path: str, payload):
        self.requests.append(("PUT", path, payload))


if __name__ == "__main__":
    unittest.main()
