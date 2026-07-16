from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import load_config
from .resources import (
    AgentsResource,
    CatalogResource,
    ChatResource,
    HooksResource,
    SkillsResource,
    SystemResource,
    ToolsResource,
)
from .transport import Transport, normalize_agent_gateway_endpoint
from .types import DEFAULT_TIMEOUT_SECONDS, ClientOptions, Config


class Client:
    def __init__(
        self,
        options: ClientOptions | Mapping[str, Any] | None = None,
        *,
        endpoint: str = "",
        api_key: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        resolved = _resolve_options(options, endpoint, api_key, headers, timeout)
        self.endpoint = normalize_agent_gateway_endpoint(resolved.endpoint)
        self.api_key = resolved.api_key
        self.transport = Transport(
            endpoint=self.endpoint,
            api_key=resolved.api_key,
            headers=resolved.headers,
            timeout=resolved.timeout,
        )

        self.system = SystemResource(self.transport)
        self.catalog = CatalogResource(self.transport)
        self.tools = ToolsResource(self.transport)
        self.skills = SkillsResource(self.transport)
        self.agents = AgentsResource(self.transport)
        self.hooks = HooksResource(self.transport)
        self.chat = ChatResource(self.transport)

        self.System = self.system
        self.Catalog = self.catalog
        self.Tools = self.tools
        self.Skills = self.skills
        self.Agents = self.agents
        self.Hooks = self.hooks
        self.Chat = self.chat


def new_client(options: ClientOptions | Mapping[str, Any] | None = None) -> Client:
    return Client(options)


def new_client_from_config(path: str = "") -> Client:
    config = load_config(path)
    if config.endpoint == "":
        raise ValueError("endpoint is not configured. Expected ~/.seaagent/config.yaml or a custom config path")
    return Client(
        ClientOptions(
            endpoint=config.endpoint,
            api_key=config.api_key,
            headers=_headers_from_config(config),
        )
    )


def _headers_from_config(config: Config) -> dict[str, str] | None:
    if config.user_id == "":
        return None
    return {"X-User-ID": config.user_id}


def _resolve_options(
    options: ClientOptions | Mapping[str, Any] | None,
    endpoint: str,
    api_key: str,
    headers: dict[str, str] | None,
    timeout: float,
) -> ClientOptions:
    if options is None:
        return ClientOptions(endpoint=endpoint, api_key=api_key, headers=headers, timeout=timeout)
    if isinstance(options, ClientOptions):
        return options
    return ClientOptions(
        endpoint=str(options.get("endpoint", endpoint) or ""),
        api_key=str(options.get("api_key", options.get("apiKey", api_key)) or ""),
        headers=options.get("headers", headers),
        timeout=float(options.get("timeout", timeout) or DEFAULT_TIMEOUT_SECONDS),
    )


NewClient = new_client
NewClientFromConfig = new_client_from_config
