from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import patch

from sea_agent_sdk import (
    APIError,
    ChatCompletionBody,
    ChatCompletionRequest,
    ChatMessage,
    ChatReconnectInfo,
    ChatRunOptions,
    ChatStreamEvent,
    ChatStreamHandlers,
    ImageURLChatContent,
    SeaAgentError,
    STREAM_TRANSPORT_WS,
    TextChatContent,
    Transport,
    build_run_payload,
    parse_sse,
    parse_websocket_event,
    text_from_stream_event,
)
from sea_agent_sdk.stream import ChatStreamProcessor


class ChatTests(unittest.TestCase):
    def test_chat_completion_body_supports_multimodal_messages(self) -> None:
        body = ChatCompletionBody(
            ChatCompletionRequest(
                agent_id="agent_1",
                messages=[
                    ChatMessage(
                        role="user",
                        content=[
                            TextChatContent("描述这张图片"),
                            ImageURLChatContent("https://image.cdn2.seaart.me/a.png"),
                        ],
                    )
                ],
            )
        )

        raw = json.dumps(body, ensure_ascii=False)
        self.assertIn('"content": [', raw)
        self.assertIn('"text": "描述这张图片"', raw)
        self.assertIn('"image_url": {"url": "https://image.cdn2.seaart.me/a.png"}', raw)

    def test_chat_completion_body_keeps_string_messages(self) -> None:
        body = ChatCompletionBody(
            ChatCompletionRequest(
                agent_id="agent_1",
                messages=[ChatMessage(role="user", content="hello")],
            )
        )

        raw = json.dumps(body)
        self.assertIn('"content": "hello"', raw)

    def test_build_run_payload_uses_message_when_messages_missing(self) -> None:
        payload = build_run_payload(
            ChatRunOptions(agent_id="agent_1", message="hello"),
            stream=False,
        )
        body = ChatCompletionBody(payload)
        self.assertEqual(body["messages"], [{"role": "user", "content": "hello"}])
        self.assertFalse(body["stream"])

    def test_chat_completion_body_includes_skill_ids(self) -> None:
        body = ChatCompletionBody(
            ChatCompletionRequest(
                agent_id="agent_1",
                skill_ids=["11111111-1111-1111-1111-111111111111"],
                messages=[ChatMessage(role="user", content="hello")],
            )
        )

        self.assertEqual(body["skill_ids"], ["11111111-1111-1111-1111-111111111111"])

    def test_build_run_payload_forwards_skill_ids(self) -> None:
        payload = build_run_payload(
            ChatRunOptions(
                agent_id="agent_1",
                skill_ids=["11111111-1111-1111-1111-111111111111"],
                message="hello",
            ),
            stream=True,
        )
        body = ChatCompletionBody(payload)
        self.assertEqual(body["skill_ids"], ["11111111-1111-1111-1111-111111111111"])

    def test_extra_body_overrides_body_fields(self) -> None:
        body = ChatCompletionBody(
            ChatCompletionRequest(
                agent_id="agent_1",
                messages=[ChatMessage(role="user", content="hello")],
                extra_body={"model": "custom", "stream": True},
            )
        )
        self.assertEqual(body["model"], "custom")
        self.assertTrue(body["stream"])

    def test_parse_sse(self) -> None:
        events = parse_sse(
            'event: response.text.delta\n'
            'data: {"delta":"hello"}\n'
            'id: 12\n\n'
            'data: plain text\n\n'
        )
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event, "response.text.delta")
        self.assertEqual(events[0].data, {"delta": "hello"})
        self.assertEqual(events[0].id, "12")
        self.assertEqual(events[0].seq, 12)
        self.assertEqual(events[1].event, "message")
        self.assertEqual(events[1].data, "plain text")
        self.assertEqual(events[1].seq, 0)

    def test_parse_websocket_event(self) -> None:
        event = parse_websocket_event(
            '{"id":"7","event":"message.delta","data":{"content":"hi"}}'
        )
        self.assertEqual(event.event, "message.delta")
        self.assertEqual(event.id, "7")
        self.assertEqual(event.seq, 7)
        self.assertEqual(text_from_stream_event(event), "hi")

        with self.assertRaises(ValueError):
            parse_websocket_event('{"event":"error","code":"bad","error":"failed"}')

    def test_stream_processor_accumulates_text(self) -> None:
        deltas: list[str] = []
        processor = ChatStreamProcessor(
            ChatStreamHandlers(on_text_delta=lambda delta, event: deltas.append(delta))
        )
        processor.write_sse_chunk('event: response.text.delta\ndata: {"delta":"he"}\n')
        self.assertEqual(deltas, [])
        processor.write_sse_chunk('\n')
        processor.write_sse_chunk('event: message.delta\ndata: {"content":"llo"}\n\n')
        self.assertEqual(processor.end(), "hello")
        self.assertEqual(deltas, ["he", "llo"])

    def test_stream_processor_deduplicates_seq_and_tracks_run(self) -> None:
        events: list[ChatStreamEvent] = []
        processor = ChatStreamProcessor(ChatStreamHandlers(on_event=events.append))
        processor.write_sse_chunk(
            'event: chat.created\ndata: {"run_id":"run_1"}\nid: 1\n\n'
            'event: chat.delta\ndata: {"content":"he"}\nid: 2\n\n'
        )
        processor.write_sse_chunk('event: chat.delta\ndata: {"content":"partial')
        processor.discard_incomplete()
        processor.write_sse_chunk(
            'event: chat.delta\ndata: {"content":"duplicate"}\nid: 2\n\n'
            'event: response.text.delta\ndata: {"delta":"llo"}\nid: 3\n\n'
            'event: response.completed\ndata: {}\nid: 4\n\n'
        )

        self.assertEqual(processor.end(), "hello")
        self.assertEqual([event.seq for event in events], [1, 2, 3, 4])
        self.assertEqual(processor.run_id, "run_1")
        self.assertEqual(processor.last_seq, 4)
        self.assertTrue(processor.terminal)

    def test_response_canceled_is_terminal(self) -> None:
        transport = _CanceledTransport()
        chat = _chat_resource(transport)

        text = chat.run_stream(
            ChatRunOptions(agent_id="agent_1", message="hello"),
            ChatStreamHandlers(reconnect_delay=0),
        )

        self.assertEqual(text, "before cancel")
        self.assertEqual(transport.calls, 1)

    def test_terminal_event_wins_over_connection_error(self) -> None:
        transport = _TerminalThenFailTransport()
        reconnects: list[ChatReconnectInfo] = []
        chat = _chat_resource(transport)

        text = chat.run_stream(
            ChatRunOptions(agent_id="agent_1", message="hello"),
            ChatStreamHandlers(reconnect_delay=0, on_reconnect=reconnects.append),
        )

        self.assertEqual(text, "done")
        self.assertEqual(transport.calls, 1)
        self.assertFalse(transport.continued_after_terminal)
        self.assertEqual(reconnects, [])

    def test_terminal_exit_discards_incomplete_sse_frame(self) -> None:
        events: list[ChatStreamEvent] = []
        chat = _chat_resource(_TerminalThenIncompleteTransport())

        text = chat.run_stream(
            ChatRunOptions(agent_id="agent_1", message="hello"),
            ChatStreamHandlers(on_event=events.append),
        )

        self.assertEqual(text, "done")
        self.assertEqual([event.event for event in events], ["chat.delta", "response.completed"])

    def test_disabled_resume_discards_incomplete_sse_frame(self) -> None:
        events: list[ChatStreamEvent] = []
        chat = _chat_resource(_IncompleteCleanCloseTransport())

        text = chat.run_stream(
            ChatRunOptions(agent_id="agent_1", message="hello"),
            ChatStreamHandlers(auto_resume=False, on_event=events.append),
        )

        self.assertEqual(text, "")
        self.assertEqual(events, [])

    def test_run_stream_resumes_from_last_delivered_seq(self) -> None:
        transport = _ResumeAfterRunIDTransport()
        reconnects: list[ChatReconnectInfo] = []
        chat = _chat_resource(transport)

        text = chat.run_stream(
            ChatRunOptions(agent_id="agent_1", message="hello"),
            ChatStreamHandlers(
                reconnect_delay=0,
                on_reconnect=reconnects.append,
            ),
        )

        self.assertEqual(text, "hello")
        self.assertEqual(transport.replay_queries, [{"after_seq": 2}])
        self.assertEqual(reconnects[0].run_id, "run_1")
        self.assertEqual(reconnects[0].after_seq, 2)

    def test_run_stream_retries_create_with_stable_request_id(self) -> None:
        transport = _ResumeBeforeRunIDTransport()
        chat = _chat_resource(transport)

        text = chat.run_stream(
            ChatRunOptions(agent_id="agent_1", message="hello"),
            ChatStreamHandlers(reconnect_delay=0),
        )

        self.assertEqual(text, "ok")
        self.assertEqual(len(transport.request_ids), 2)
        self.assertTrue(transport.request_ids[0].startswith("sdk_"))
        self.assertEqual(transport.request_ids[0], transport.request_ids[1])
        self.assertEqual(transport.replay_calls, 0)

    def test_stream_existing_run_resumes_after_requested_seq(self) -> None:
        transport = _ExistingRunTransport()
        chat = _chat_resource(transport)

        text = chat.stream(
            "run_existing",
            ChatStreamHandlers(reconnect_delay=0),
            {"after_seq": 5},
        )

        self.assertEqual(text, "ab")
        self.assertEqual(transport.queries, [{"after_seq": 5}, {"after_seq": 6}])

    def test_auto_resume_can_be_disabled_and_does_not_retry_4xx(self) -> None:
        disabled_transport = _AlwaysFailTransport(SeaAgentError("disconnected"))
        chat = _chat_resource(disabled_transport)
        with self.assertRaises(SeaAgentError):
            chat.run_stream(
                ChatRunOptions(agent_id="agent_1", message="hello"),
                ChatStreamHandlers(auto_resume=False, reconnect_delay=0),
            )
        self.assertEqual(disabled_transport.calls, 1)

        api_transport = _AlwaysFailTransport(APIError(401, "unauthorized"))
        chat = _chat_resource(api_transport)
        with self.assertRaises(APIError):
            chat.run_stream(
                ChatRunOptions(agent_id="agent_1", message="hello"),
                ChatStreamHandlers(reconnect_delay=0),
            )
        self.assertEqual(api_transport.calls, 1)

        limited_transport = _AlwaysFailTransport(SeaAgentError("still disconnected"))
        chat = _chat_resource(limited_transport)
        with self.assertRaises(SeaAgentError):
            chat.run_stream(
                ChatRunOptions(agent_id="agent_1", message="hello"),
                ChatStreamHandlers(max_reconnects=1, reconnect_delay=0),
            )
        self.assertEqual(limited_transport.calls, 2)

    def test_websocket_handshake_status_retry_policy(self) -> None:
        unauthorized = _WebSocketHandshakeTransport(401)
        chat = _chat_resource(unauthorized)
        with self.assertRaises(APIError):
            chat.run_stream(
                ChatRunOptions(agent_id="agent_1", message="hello"),
                ChatStreamHandlers(transport=STREAM_TRANSPORT_WS, reconnect_delay=0),
            )
        self.assertEqual(unauthorized.calls, 1)

        for status_code in (408, 429):
            with self.subTest(status_code=status_code):
                retryable = _WebSocketHandshakeTransport(status_code, succeeds_after=1)
                chat = _chat_resource(retryable)
                text = chat.run_stream(
                    ChatRunOptions(agent_id="agent_1", message="hello"),
                    ChatStreamHandlers(transport=STREAM_TRANSPORT_WS, reconnect_delay=0),
                )
                self.assertEqual(text, "")
                self.assertEqual(retryable.calls, 2)

    def test_sse_terminal_closes_connection_without_waiting_for_eof(self) -> None:
        response = _OpenSSEStreamResponse(
            (
                'event: chat.delta\ndata: {"content":"done"}\nid: 1\n\n'
                'event: response.completed\ndata: {}\nid: 2\n\n'
                'event: chat.delta\ndata: {"content":"ignored"}\nid: 3\n\n'
            ).encode()
        )
        events: list[ChatStreamEvent] = []

        with patch("sea_agent_sdk.transport.request.urlopen", return_value=response):
            text = _chat_resource(Transport("http://127.0.0.1:8080")).run_stream(
                ChatRunOptions(agent_id="agent_1", message="hello"),
                ChatStreamHandlers(on_event=events.append),
            )

        self.assertEqual(text, "done")
        self.assertEqual([event.event for event in events], ["chat.delta", "response.completed"])
        self.assertEqual(response.read_calls, 1)
        self.assertTrue(response.closed)

    def test_websocket_terminal_closes_connection_without_waiting_for_close(self) -> None:
        connection = _OpenWebSocketConnection(
            [
                '{"id":"1","event":"chat.delta","data":{"content":"done"}}',
                '{"id":"2","event":"chat.completed","data":{}}',
                '{"id":"3","event":"chat.delta","data":{"content":"ignored"}}',
            ]
        )
        fake_websocket = types.SimpleNamespace(
            WebSocketBadStatusException=_WebSocketBadStatus,
            WebSocketConnectionClosedException=_WebSocketClosed,
            create_connection=lambda *args, **kwargs: connection,
        )
        events: list[ChatStreamEvent] = []

        with patch.dict(sys.modules, {"websocket": fake_websocket}):
            text = _chat_resource(Transport("http://127.0.0.1:8080")).run_stream(
                ChatRunOptions(agent_id="agent_1", message="hello"),
                ChatStreamHandlers(
                    transport=STREAM_TRANSPORT_WS,
                    on_event=events.append,
                ),
            )

        self.assertEqual(text, "done")
        self.assertEqual([event.event for event in events], ["chat.delta", "chat.completed"])
        self.assertEqual(connection.recv_calls, 2)
        self.assertTrue(connection.closed)


def _chat_resource(transport):
    from sea_agent_sdk.resources import ChatResource

    return ChatResource(transport)


class _ResumeAfterRunIDTransport:
    def __init__(self) -> None:
        self.replay_queries: list[dict[str, int]] = []

    def post_stream(self, path, body, on_chunk, headers=None) -> None:
        on_chunk(
            'event: chat.created\ndata: {"run_id":"run_1"}\nid: 1\n\n'
            'event: chat.delta\ndata: {"content":"hel"}\nid: 2\n\n'
        )
        raise SeaAgentError("connection reset")

    def get_stream(self, path, query, on_chunk, headers=None) -> None:
        self.replay_queries.append(query)
        on_chunk(
            'event: chat.delta\ndata: {"content":"duplicate"}\nid: 2\n\n'
            'event: response.text.delta\ndata: {"delta":"lo"}\nid: 3\n\n'
            'event: response.completed\ndata: {}\nid: 4\n\n'
        )


class _ResumeBeforeRunIDTransport:
    def __init__(self) -> None:
        self.request_ids: list[str] = []
        self.replay_calls = 0

    def post_stream(self, path, body, on_chunk, headers=None) -> None:
        self.request_ids.append(body["request_id"])
        if len(self.request_ids) == 1:
            raise SeaAgentError("connection reset before first event")
        on_chunk(
            'event: chat.created\ndata: {"run_id":"run_2"}\nid: 1\n\n'
            'event: chat.response\ndata: {"content":"ok"}\nid: 2\n\n'
        )

    def get_stream(self, path, query, on_chunk, headers=None) -> None:
        self.replay_calls += 1


class _ExistingRunTransport:
    def __init__(self) -> None:
        self.queries: list[dict[str, int]] = []

    def get_stream(self, path, query, on_chunk, headers=None) -> None:
        self.queries.append(query)
        if len(self.queries) == 1:
            on_chunk('event: chat.delta\ndata: {"content":"a"}\nid: 6\n\n')
            raise SeaAgentError("connection reset")
        on_chunk(
            'event: chat.delta\ndata: {"content":"b"}\nid: 7\n\n'
            'event: response.completed\ndata: {}\nid: 8\n\n'
        )


class _AlwaysFailTransport:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def post_stream(self, path, body, on_chunk, headers=None) -> None:
        self.calls += 1
        raise self.exc


class _CanceledTransport:
    def __init__(self) -> None:
        self.calls = 0

    def post_stream(self, path, body, on_chunk, headers=None) -> None:
        self.calls += 1
        on_chunk(
            'event: chat.delta\ndata: {"content":"before cancel"}\nid: 1\n\n'
            'event: response.canceled\ndata: {}\nid: 2\n\n'
        )


class _TerminalThenFailTransport:
    def __init__(self) -> None:
        self.calls = 0
        self.continued_after_terminal = False

    def post_stream(self, path, body, on_chunk, headers=None) -> None:
        self.calls += 1
        try:
            on_chunk(
                'event: chat.delta\ndata: {"content":"done"}\nid: 1\n\n'
                'event: response.completed\ndata: {}\nid: 2\n\n'
            )
        except Exception as exc:
            raise SeaAgentError("connection reset while closing") from exc
        self.continued_after_terminal = True


class _TerminalThenIncompleteTransport:
    def post_stream(self, path, body, on_chunk, headers=None) -> None:
        on_chunk(
            'event: chat.delta\ndata: {"content":"done"}\nid: 1\n\n'
            'event: response.completed\ndata: {}\nid: 2\n\n'
            'event: chat.delta\ndata: {"content":"must be discarded"}\nid: 3\n'
        )


class _IncompleteCleanCloseTransport:
    def post_stream(self, path, body, on_chunk, headers=None) -> None:
        on_chunk('event: chat.delta\ndata: {"content":"must be discarded"}\nid: 1\n')


class _WebSocketHandshakeTransport:
    def __init__(self, status_code: int, succeeds_after: int | None = None) -> None:
        self.status_code = status_code
        self.succeeds_after = succeeds_after
        self.calls = 0

    def websocket(self, path, query, initial_message, on_message, headers=None) -> None:
        self.calls += 1
        if self.succeeds_after is None or self.calls <= self.succeeds_after:
            raise APIError(self.status_code, "handshake failed")
        on_message('{"id":"1","event":"response.completed","data":{}}')


class _OpenSSEStreamResponse:
    def __init__(self, first_chunk: bytes) -> None:
        self.first_chunk = first_chunk
        self.read_calls = 0
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        self.read_calls += 1
        if self.read_calls == 1:
            return self.first_chunk
        raise AssertionError("SSE transport read again after terminal event")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.closed = True


class _OpenWebSocketConnection:
    def __init__(self, messages: list[str]) -> None:
        self.messages = iter(messages)
        self.recv_calls = 0
        self.closed = False
        self.sent: list[str] = []

    def send(self, message: str) -> None:
        self.sent.append(message)

    def recv(self) -> str:
        self.recv_calls += 1
        try:
            return next(self.messages)
        except StopIteration as exc:
            raise AssertionError("WebSocket read again after terminal event") from exc

    def close(self) -> None:
        self.closed = True


class _WebSocketBadStatus(Exception):
    pass


class _WebSocketClosed(Exception):
    pass


if __name__ == "__main__":
    unittest.main()
