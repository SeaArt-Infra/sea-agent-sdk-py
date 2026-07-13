from __future__ import annotations

import json
from typing import Any

from .errors import StreamProcessingError
from .types import (
    STREAM_TRANSPORT_SSE,
    ChatStreamEvent,
    ChatStreamHandlers,
)

_TERMINAL_EVENTS = {
    "response.completed",
    "response.failed",
    "response.canceled",
    "response.cancelled",
    "chat.response",
    "chat.completed",
    "chat.failed",
    "chat.cancelled",
}


class ChatStreamProcessor:
    def __init__(self, handlers: ChatStreamHandlers | dict[str, Any] | None = None) -> None:
        self.handlers = _normalize_handlers(handlers)
        self._buffer = ""
        self._text: list[str] = []
        self._last_seq = 0
        self._run_id = ""
        self._terminal = False

    @property
    def last_seq(self) -> int:
        return self._last_seq

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def terminal(self) -> bool:
        return self._terminal

    def resume_from(self, run_id: str, after_seq: int = 0) -> None:
        self._run_id = run_id
        self._last_seq = max(0, after_seq)

    def discard_incomplete(self) -> None:
        self._buffer = ""

    def write_sse_chunk(self, chunk: str) -> None:
        if self._terminal:
            return
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
                if self._terminal:
                    self.discard_incomplete()
                    return

    def write_websocket_message(self, message: str) -> None:
        if self._terminal:
            return
        self._handle_event(parse_websocket_event(message))

    def end(self) -> str:
        self.discard_incomplete()
        return "".join(self._text)

    def _handle_event(self, event: ChatStreamEvent) -> None:
        if self._terminal:
            return
        if event.seq > 0 and event.seq <= self._last_seq:
            return
        self._capture_run_id(event)
        try:
            if self.handlers.on_event is not None:
                self.handlers.on_event(event)
            delta = text_from_stream_event(event)
            if delta != "":
                self._text.append(delta)
                if self.handlers.on_text_delta is not None:
                    self.handlers.on_text_delta(delta, event)
        except Exception as exc:
            raise StreamProcessingError(f"stream callback failed: {exc}") from exc

        if event.seq > 0:
            self._last_seq = event.seq
        if event.event in _TERMINAL_EVENTS:
            self._terminal = True

    def _capture_run_id(self, event: ChatStreamEvent) -> None:
        if self._run_id or not isinstance(event.data, dict):
            return
        run_id = event.data.get("run_id")
        if isinstance(run_id, str) and run_id:
            self._run_id = run_id


def parse_sse(text: str) -> list[ChatStreamEvent]:
    events: list[ChatStreamEvent] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        block = block.strip()
        if not block:
            continue

        event_name = "message"
        event_id = ""
        data_lines: list[str] = []
        for line in block.split("\n"):
            line = line.removesuffix("\r")
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("id:"):
                event_id = line.removeprefix("id:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").lstrip(" "))

        if not data_lines:
            continue

        data_text = "\n".join(data_lines)
        try:
            data: Any = json.loads(data_text)
        except json.JSONDecodeError:
            data = data_text
        events.append(
            ChatStreamEvent(
                event=event_name,
                data=data,
                id=event_id,
                seq=_event_seq(event_id),
            )
        )
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

    event_id = str(parsed.get("id") or "")
    return ChatStreamEvent(
        event=str(event_name),
        data=parsed.get("data"),
        id=event_id,
        seq=_event_seq(event_id),
    )


def text_from_stream_event(event: ChatStreamEvent) -> str:
    if event.event in {"response.text.delta", "response.output_text.delta"}:
        return _string_field(event.data, "delta")
    if event.event in {"chat.delta", "chat.response", "message.delta"}:
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


def _event_seq(event_id: str) -> int:
    try:
        value = int(event_id)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


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
        auto_resume=handlers.get("auto_resume", handlers.get("autoResume", True)),
        max_reconnects=handlers.get("max_reconnects", handlers.get("maxReconnects", 3)),
        reconnect_delay=handlers.get("reconnect_delay", handlers.get("reconnectDelay", 0.25)),
        max_reconnect_delay=handlers.get(
            "max_reconnect_delay", handlers.get("maxReconnectDelay", 5.0)
        ),
        on_reconnect=handlers.get("on_reconnect") or handlers.get("onReconnect"),
    )


NewChatStreamProcessor = ChatStreamProcessor
ParseSSE = parse_sse
ParseWebSocketEvent = parse_websocket_event
TextFromStreamEvent = text_from_stream_event
