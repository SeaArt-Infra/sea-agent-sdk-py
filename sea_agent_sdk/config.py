from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .types import Config


def default_config_path() -> str:
    return str(Path.home() / ".seaagent" / "config.yaml")


def load_config(path: str = "") -> Config:
    config_path = Path(path or default_config_path())
    if not config_path.exists():
        return Config()

    raw = config_path.read_text(encoding="utf-8")
    data = _parse_config_text(raw)
    return Config(
        endpoint=str(data.get("endpoint") or ""),
        api_key=str(data.get("apiKey") or data.get("api_key") or ""),
        user_id=str(data.get("userId") or data.get("user_id") or ""),
    )


def save_config(path: str, config: Config) -> None:
    config_path = Path(path or default_config_path())
    os.makedirs(config_path.parent, exist_ok=True)
    raw = _dump_config(config)
    config_path.write_text(raw, encoding="utf-8")


def _parse_config_text(raw: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(raw)
        return parsed if isinstance(parsed, dict) else {}
    except ModuleNotFoundError:
        return _parse_flat_yaml(raw)


def _parse_flat_yaml(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        value = value.strip().strip('"').strip("'")
        result[key.strip()] = value
    return result


def _dump_config(config: Config) -> str:
    data = {
        "endpoint": config.endpoint,
        "apiKey": config.api_key,
        "userId": config.user_id,
    }
    try:
        import yaml  # type: ignore

        return yaml.safe_dump(data, sort_keys=False)
    except ModuleNotFoundError:
        return (
            f"endpoint: {config.endpoint}\n"
            f"apiKey: {config.api_key}\n"
            f"userId: {config.user_id}\n"
        )


DefaultConfigPath = default_config_path
LoadConfig = load_config
SaveConfig = save_config
