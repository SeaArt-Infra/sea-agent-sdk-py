from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sea_agent_sdk import Client, ClientOptions, Config, load_config, new_client_from_config, save_config


class ConfigClientTests(unittest.TestCase):
    def test_load_flat_yaml_config_without_pyyaml_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "endpoint: http://127.0.0.1:8080\n"
                "apiKey: sa-key\n"
                "userId: user_1\n",
                encoding="utf-8",
            )
            cfg = load_config(str(path))
            self.assertEqual(cfg.endpoint, "http://127.0.0.1:8080")
            self.assertEqual(cfg.api_key, "sa-key")
            self.assertEqual(cfg.user_id, "user_1")

    def test_save_and_load_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            save_config(str(path), Config(endpoint="http://127.0.0.1:8080", api_key="key", user_id="user"))
            cfg = load_config(str(path))
            self.assertEqual(cfg.endpoint, "http://127.0.0.1:8080")
            self.assertEqual(cfg.api_key, "key")
            self.assertEqual(cfg.user_id, "user")

    def test_client_initializes_resources_and_aliases(self) -> None:
        client = Client(ClientOptions(endpoint="http://127.0.0.1:8080", api_key="key"))
        self.assertEqual(client.endpoint, "http://127.0.0.1:8080/agent-v2")
        self.assertEqual(client.transport.timeout, 180.0)
        self.assertIs(client.chat, client.Chat)
        self.assertIs(client.tools, client.Tools)

    def test_client_timeout_can_be_overridden(self) -> None:
        client = Client(endpoint="http://127.0.0.1:8080", timeout=30.0)

        self.assertEqual(client.transport.timeout, 30.0)

    def test_new_client_from_config_maps_user_id_to_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "endpoint: http://127.0.0.1:8080\n"
                "apiKey: sa-key\n"
                "userId: user_1\n",
                encoding="utf-8",
            )
            client = new_client_from_config(str(path))
            self.assertEqual(client.api_key, "sa-key")
            self.assertEqual(client.transport.headers, {"X-User-ID": "user_1"})


if __name__ == "__main__":
    unittest.main()
