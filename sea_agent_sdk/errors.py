from __future__ import annotations


class SeaAgentError(Exception):
    """Base exception raised by sea-agent-sdk."""


class APIError(SeaAgentError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"{status_code}: {message}")
        self.status_code = status_code
        self.message = message


class WebSocketDependencyError(SeaAgentError):
    def __init__(self) -> None:
        super().__init__(
            "WebSocket streaming requires the optional dependency: "
            "pip install 'sea-agent-sdk[ws]'"
        )
