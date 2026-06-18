from __future__ import annotations

import json
from typing import Any

from .types import (
    STREAM_TRANSPORT_SSE,
    ChatStreamEvent,
    ChatStreamHandlers,
)


class ChatStreamProcessor:
    def __init__(self, handlers: ChatStreamHandlers | dict[str, Any] | None = None) -> None:
        self.handlers = _normalize_handlers(handlers)
        self._buffer = ""
        self._text: list[str] = []

    def write_sse_chunk(self, chunk: str) -> None:
        self._buffer += chunk
        parts = _split_sse_blocks(self._buffer)
        if not parts:
            return

        self._buffer = ""
        last = parts[-1]
        complete = parts[:-1]
        if not last.endswith("\n\n") and not last.endswith("\r\n\r\n"):
            self._buffer = last
        else:
            complete = parts

        for block in complete:
            for event in parse_sse(block):
                self._handle_event(event)

    def write_websocket_message(self, message: str) -> None:
        self._handle_event(parse_websocket_event(message))

    def end(self) -> str:
        if self._buffer:
            for event in parse_sse(self._buffer):
                self._handle_event(event)
            self._buffer = ""
        return "".join(self._text)

    def _handle_event(self, event: ChatStreamEvent) -> None:
        if self.handlers.on_event is not None:
            self.handlers.on_event(event)
        delta = text_from_stream_event(event)
        if delta == "":
            return
        self._text.append(delta)
        if self.handlers.on_text_delta is not None:
            self.handlers.on_text_delta(delta, event)


def parse_sse(text: str) -> list[ChatStreamEvent]:
    events: list[ChatStreamEvent] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        block = block.strip()
        if not block:
            continue

        event_name = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            line = line.removesuffix("\r")
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").lstrip(" "))

        if not data_lines:
            continue

        data_text = "\n".join(data_lines)
        try:
            data: Any = json.loads(data_text)
        except json.JSONDecodeError:
            data = data_text
        events.append(ChatStreamEvent(event=event_name, data=data))
    return events


def parse_websocket_event(message: str) -> ChatStreamEvent:
    try:
        parsed: Any = json.loads(message)
    except json.JSONDecodeError:
        return ChatStreamEvent(event="message", data=message)

    if not isinstance(parsed, dict):
        return ChatStreamEvent(event="message", data=parsed)

    event_name = parsed.get("event") or "message"
    if event_name == "error":
        code = parsed.get("code") or ""
        error_text = parsed.get("error") or str(parsed)
        if code:
            raise ValueError(f"{code}: {error_text}")
        raise ValueError(str(error_text))

    return ChatStreamEvent(event=str(event_name), data=parsed.get("data"))


def text_from_stream_event(event: ChatStreamEvent) -> str:
    if event.event in {"response.text.delta", "response.output_text.delta"}:
        return _string_field(event.data, "delta")
    if event.event in {"chat.response", "message.delta"}:
        for field in ("content", "text", "delta"):
            value = _string_field(event.data, field)
            if value:
                return value
    return ""


def _string_field(data: Any, field: str) -> str:
    if not isinstance(data, dict):
        return ""
    value = data.get(field)
    return value if isinstance(value, str) else ""


def _split_sse_blocks(text: str) -> list[str]:
    if text == "":
        return []

    normalized = text.replace("\r\n", "\n")
    blocks: list[str] = []
    start = 0
    while True:
        idx = normalized.find("\n\n", start)
        if idx < 0:
            blocks.append(normalized[start:])
            break
        end = idx + 2
        blocks.append(normalized[start:end])
        start = end
        if start >= len(normalized):
            break
    return blocks


def _normalize_handlers(handlers: ChatStreamHandlers | dict[str, Any] | None) -> ChatStreamHandlers:
    if handlers is None:
        return ChatStreamHandlers()
    if isinstance(handlers, ChatStreamHandlers):
        return handlers
    return ChatStreamHandlers(
        transport=handlers.get("transport", STREAM_TRANSPORT_SSE),
        on_event=handlers.get("on_event") or handlers.get("OnEvent"),
        on_text_delta=handlers.get("on_text_delta") or handlers.get("OnTextDelta"),
    )


NewChatStreamProcessor = ChatStreamProcessor
ParseSSE = parse_sse
ParseWebSocketEvent = parse_websocket_event
TextFromStreamEvent = text_from_stream_event
