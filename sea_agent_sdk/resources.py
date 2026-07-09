from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .stream import ChatStreamProcessor
from .transport import Transport
from .types import (
    STREAM_TRANSPORT_WS,
    AgentListOptions,
    CatalogListOptions,
    ChatCompletionRequest,
    ChatEventsOptions,
    ChatMessage,
    ChatRunOptions,
    ChatStreamHandlers,
    HookListOptions,
    SkillListOptions,
    ToolListOptions,
    option_value,
    options_to_query,
    to_jsonable,
)


class SystemResource:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def health(self) -> str:
        return self.transport.get_text("/health")

    def metrics(self) -> str:
        return self.transport.get_text("/metrics")

    Health = health
    Metrics = metrics


class CatalogResource:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def list(self, options: CatalogListOptions | dict[str, Any] | None = None) -> Any:
        return self.transport.get_json(
            "/v1/catalog",
            options_to_query(
                options,
                [
                    "capability_type",
                    "search",
                    "status",
                    "source_kind",
                    "owner_id",
                    "public",
                    "provider",
                    "category",
                    "limit",
                    "offset",
                ],
            ),
        )

    List = list


class ToolsResource:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def register(self, payload: Any) -> Any:
        return self.transport.post_json("/v1/tools/register", payload)

    def list(self, options: ToolListOptions | dict[str, Any] | None = None) -> Any:
        return self.transport.get_json(
            "/v1/tools",
            options_to_query(
                options,
                [
                    "search",
                    "status",
                    "source_kind",
                    "owner_id",
                    "public",
                    "provider",
                    "category",
                    "include_deleted",
                    "limit",
                    "offset",
                ],
            ),
        )

    def get(self, tool_id: str) -> Any:
        return self.transport.get_json(f"/v1/tools/{_url_escape(tool_id)}")

    def update(self, tool_id: str, payload: Any) -> Any:
        return self.transport.put_json(f"/v1/tools/{_url_escape(tool_id)}", payload)

    def delete(self, tool_id: str) -> Any:
        return self.transport.delete_json(f"/v1/tools/{_url_escape(tool_id)}")

    def resolve(self, tool_id: str) -> Any:
        return self.transport.get_json(f"/v1/tools/{_url_escape(tool_id)}/resolve")

    Register = register
    List = list
    Get = get
    Update = update
    Delete = delete
    Resolve = resolve


class SkillsResource:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def register(self, payload: Any) -> Any:
        return self.transport.post_json("/v1/skills/register", payload)

    def list(self, options: SkillListOptions | dict[str, Any] | None = None) -> Any:
        return self.transport.get_json(
            "/v1/skills",
            options_to_query(
                options,
                [
                    "search",
                    "status",
                    "source_kind",
                    "owner_id",
                    "public",
                    "provider",
                    "category",
                    "include_deleted",
                    "limit",
                    "offset",
                ],
            ),
        )

    def get(self, skill_id: str) -> Any:
        return self.transport.get_json(f"/v1/skills/{_url_escape(skill_id)}")

    def update(self, skill_id: str, payload: Any) -> Any:
        return self.transport.put_json(f"/v1/skills/{_url_escape(skill_id)}", payload)

    def delete(self, skill_id: str) -> Any:
        return self.transport.delete_json(f"/v1/skills/{_url_escape(skill_id)}")

    Register = register
    List = list
    Get = get
    Update = update
    Delete = delete


class AgentsResource:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def register(self, payload: Any) -> Any:
        return self.transport.post_json("/v1/agents/register", payload)

    def update(self, agent_id: str, payload: Any) -> Any:
        return self.transport.put_json(f"/v1/agents/{_url_escape(agent_id)}", payload)

    def list(self, options: AgentListOptions | dict[str, Any] | None = None) -> Any:
        return self.transport.get_json(
            "/v1/agents",
            options_to_query(
                options,
                [
                    "search",
                    "status",
                    "owner_id",
                    "category",
                    "include_deleted",
                    "limit",
                    "offset",
                ],
            ),
        )

    def get(self, agent_id: str) -> Any:
        return self.transport.get_json(f"/v1/agents/{_url_escape(agent_id)}")

    def delete(self, agent_id: str) -> Any:
        return self.transport.delete_json(f"/v1/agents/{_url_escape(agent_id)}")

    def capabilities(self, agent_id: str) -> Any:
        return self.transport.get_json(f"/v1/agents/{_url_escape(agent_id)}/capabilities")

    Register = register
    Update = update
    List = list
    Get = get
    Delete = delete
    Capabilities = capabilities


class HooksResource:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def register(self, payload: Any) -> Any:
        return self.transport.post_json("/v1/hooks/register", payload)

    def list(self, options: HookListOptions | dict[str, Any] | None = None) -> Any:
        return self.transport.get_json(
            "/v1/hooks",
            options_to_query(options, ["search", "limit", "offset"]),
        )

    def get(self, hook_id: str) -> Any:
        return self.transport.get_json(f"/v1/hooks/{_url_escape(hook_id)}")

    def update(self, hook_id: str, payload: Any) -> Any:
        return self.transport.put_json(f"/v1/hooks/{_url_escape(hook_id)}", payload)

    def delete(self, hook_id: str) -> Any:
        return self.transport.delete_json(f"/v1/hooks/{_url_escape(hook_id)}")

    Register = register
    List = list
    Get = get
    Update = update
    Delete = delete


class ChatResource:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def create_completion(self, payload: ChatCompletionRequest | dict[str, Any]) -> Any:
        return self.transport.post_json(
            "/v1/chat/completions",
            chat_completion_body(payload),
            _payload_headers(payload),
        )

    def stream_completion(
        self,
        payload: ChatCompletionRequest | dict[str, Any],
        handlers: ChatStreamHandlers | dict[str, Any] | None = None,
    ) -> str:
        processor = ChatStreamProcessor(handlers)
        body = chat_completion_body(payload)
        body["stream"] = True

        if processor.handlers.transport == STREAM_TRANSPORT_WS:
            self.transport.websocket(
                "/v1/chat/completions/ws",
                None,
                body,
                processor.write_websocket_message,
                _payload_headers(payload),
            )
        else:
            self.transport.post_stream(
                "/v1/chat/completions",
                body,
                processor.write_sse_chunk,
                _payload_headers(payload),
            )
        return processor.end()

    def run(self, options: ChatRunOptions | dict[str, Any]) -> Any:
        return self.create_completion(build_run_payload(options, stream=False))

    def run_stream(
        self,
        options: ChatRunOptions | dict[str, Any],
        handlers: ChatStreamHandlers | dict[str, Any] | None = None,
    ) -> str:
        return self.stream_completion(build_run_payload(options, stream=True), handlers)

    def get(self, chat_id: str) -> Any:
        return self.transport.get_json(f"/v1/chats/{_url_escape(chat_id)}")

    def events(
        self,
        chat_id: str,
        options: ChatEventsOptions | dict[str, Any] | None = None,
    ) -> Any:
        limit = option_value(options, "limit", 0)
        if limit == 0:
            limit = 100
        return self.transport.get_json(
            f"/v1/chats/{_url_escape(chat_id)}/events",
            {
                "after_seq": option_value(options, "after_seq", 0),
                "limit": limit,
            },
        )

    def stream(
        self,
        chat_id: str,
        handlers: ChatStreamHandlers | dict[str, Any] | None = None,
        options: ChatEventsOptions | dict[str, Any] | None = None,
    ) -> str:
        processor = ChatStreamProcessor(handlers)
        query = {"after_seq": option_value(options, "after_seq", 0)}

        if processor.handlers.transport == STREAM_TRANSPORT_WS:
            self.transport.websocket(
                f"/v1/chats/{_url_escape(chat_id)}/ws",
                query,
                None,
                processor.write_websocket_message,
            )
        else:
            self.transport.get_stream(
                f"/v1/chats/{_url_escape(chat_id)}/stream",
                query,
                processor.write_sse_chunk,
            )
        return processor.end()

    def cancel(self, chat_id: str) -> Any:
        return self.transport.post_json(f"/v1/chats/{_url_escape(chat_id)}/cancel", None)

    CreateCompletion = create_completion
    StreamCompletion = stream_completion
    Run = run
    RunStream = run_stream
    Get = get
    Events = events
    Stream = stream
    Cancel = cancel


def build_run_payload(options: ChatRunOptions | dict[str, Any], stream: bool) -> ChatCompletionRequest:
    messages = option_value(options, "messages")
    if not messages:
        messages = [ChatMessage(role="user", content=option_value(options, "message", ""))]

    return ChatCompletionRequest(
        request_id=option_value(options, "request_id", ""),
        agent_id=option_value(options, "agent_id", ""),
        category=option_value(options, "category", ""),
        agent_config=option_value(options, "agent_config"),
        skill_ids=option_value(options, "skill_ids"),
        messages=messages,
        metadata=option_value(options, "metadata"),
        stream=stream,
        headers=option_value(options, "headers"),
        extra_body=option_value(options, "extra_body"),
    )


def chat_completion_body(payload: ChatCompletionRequest | dict[str, Any]) -> dict[str, Any]:
    messages = option_value(payload, "messages", [])
    body: dict[str, Any] = {
        "messages": to_jsonable(messages),
        "stream": bool(option_value(payload, "stream", False)),
    }

    for field in ("request_id", "agent_id", "category"):
        value = option_value(payload, field, "")
        if value:
            body[field] = value

    agent_config = option_value(payload, "agent_config")
    if agent_config is not None:
        body["agent_config"] = to_jsonable(agent_config)

    skill_ids = option_value(payload, "skill_ids")
    if skill_ids:
        body["skill_ids"] = to_jsonable(skill_ids)

    metadata = option_value(payload, "metadata")
    if metadata is not None:
        body["metadata"] = to_jsonable(metadata)

    extra_body = option_value(payload, "extra_body")
    if extra_body:
        body.update(to_jsonable(extra_body))

    return body


def _payload_headers(payload: ChatCompletionRequest | dict[str, Any]) -> dict[str, str] | None:
    return option_value(payload, "headers")


def _url_escape(value: str) -> str:
    return quote(value, safe="")


BuildRunPayload = build_run_payload
ChatCompletionBody = chat_completion_body
