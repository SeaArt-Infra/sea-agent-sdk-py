from __future__ import annotations

import json
import unittest

from sea_agent_sdk import (
    ChatCompletionBody,
    ChatCompletionRequest,
    ChatMessage,
    ChatRunOptions,
    ChatStreamHandlers,
    ImageURLChatContent,
    TextChatContent,
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
            'data: {"delta":"hello"}\n\n'
            'data: plain text\n\n'
        )
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event, "response.text.delta")
        self.assertEqual(events[0].data, {"delta": "hello"})
        self.assertEqual(events[1].event, "message")
        self.assertEqual(events[1].data, "plain text")

    def test_parse_websocket_event(self) -> None:
        event = parse_websocket_event('{"event":"message.delta","data":{"content":"hi"}}')
        self.assertEqual(event.event, "message.delta")
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


if __name__ == "__main__":
    unittest.main()
