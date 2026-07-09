# Sea Agent Python SDK

> Beta: SDK APIs and `agent-gateway` behavior may still change with gateway versions.

Python SDK for the SeaArt `agent-gateway`. It wraps gateway APIs for catalog lookup, tool registration, skill registration, agent registration, hook management, chat completion, SSE streaming, WebSocket streaming, chat replay, and chat cancellation.

Features:

- Standard-library runtime by default, with no required third-party runtime dependencies
- Automatic `/agent-v2` API prefix normalization for `agent-gateway`
- Explicit client configuration with endpoint, API key, and request headers
- OpenAI-style multi-turn messages and multimodal content parts
- SSE stream parsing by default, with WebSocket support as an optional dependency
- Pythonic `snake_case` APIs, with a small set of Go SDK-style aliases for migration

## Available Resources

| Resource | Client field | What it does |
| --- | --- | --- |
| System | `client.system` / `client.System` | Health and metrics checks |
| Catalog | `client.catalog` / `client.Catalog` | List resolved catalog entries |
| Tools | `client.tools` / `client.Tools` | Register, list, update, delete, and resolve tools |
| Skills | `client.skills` / `client.Skills` | Register, list, update, and delete skills |
| Agents | `client.agents` / `client.Agents` | Register, list, update, delete, and inspect agents |
| Hooks | `client.hooks` / `client.Hooks` | Register and manage worker event hook endpoints |
| Chat | `client.chat` / `client.Chat` | Run chat, stream chat, replay events, and cancel chats |

## Installation

Install from PyPI:

```bash
pip install --upgrade sea-agent-sdk
```

Install WebSocket streaming support when needed:

```bash
pip install --upgrade 'sea-agent-sdk[ws]'
```

Install PyYAML support when you need fuller YAML config handling:

```bash
pip install --upgrade 'sea-agent-sdk[yaml]'
```

Install the latest code from GitHub:

```bash
pip install --upgrade git+https://github.com/SeaArt-Infra/sea-agent-sdk-py.git
```

Requires Python 3.10 or newer.

## Configuration

Create a client with explicit options:

```python
import os

import sea_agent_sdk as sa

client = sa.Client(
    sa.ClientOptions(
        endpoint="http://127.0.0.1:8080",
        api_key=os.environ.get("AGENT_GATEWAY_API_KEY", ""),
        headers={"X-User-ID": "production-line-123"},
    )
)
```

`endpoint` may be the gateway base URL or a URL that already includes `/agent-v2`. The SDK appends `/agent-v2` before sending requests when it is missing.

Pass `X-User-ID` in `ClientOptions.headers` when `tools`, `skills`, or `agents` write operations need provider, owner, or operator metadata.

## System Checks

```python
health = client.system.health()
metrics = client.system.metrics()
print(health)
```

## Listing Resources

List APIs pass gateway filters through SDK option objects. Common filters are `search`, `status`, `provider`, `public`, `limit`, and `offset`. Compatibility filters include `source_kind`, `owner_id`, and `category`.

```python
tools = client.tools.list(
    sa.ToolListOptions(
        provider="web-tools-mcp",
        status="active",
        limit=20,
    )
)
print(tools)
```

You can also pass a plain dictionary:

```python
tools = client.tools.list(
    {
        "provider": "web-tools-mcp",
        "status": "active",
        "limit": 20,
    }
)
```

Pagination follows the gateway behavior: `limit` defaults to 20 when omitted or `<= 0`, the gateway caps values above 200, and `offset` starts at 0.

## Chat Requests

Use `message` for the common single-user-message case:

```python
result = client.chat.run(
    sa.ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Fetch https://example.com and explain what it is.",
    )
)
print(result)
```

Use `skill_ids` to temporarily mount extra Skills for a registered Agent run when it needs one-off capabilities without changing its saved configuration. Agent Gateway accepts at most 20 active, visible Skill UUIDs, merges them after the Agent's own Skills, dedupes repeated IDs, rejects `skill_ids` when `agent_config` is used, and only lets Skill runtime config fill Agent defaults that are unset.

```python
result = client.chat.run(
    sa.ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        skill_ids=["11111111-1111-1111-1111-111111111111"],
        message="Use the extra skill for this run.",
    )
)
```

Use `messages` for multi-turn conversations:

```python
result = client.chat.run(
    sa.ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        messages=[
            sa.ChatMessage(role="system", content="Answer in concise Chinese."),
            sa.ChatMessage(role="user", content="Fetch https://example.com and explain what it is."),
        ],
    )
)
```

Use OpenAI-style content parts for multimodal messages:

```python
result = client.chat.run(
    sa.ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        messages=[
            sa.ChatMessage(
                role="user",
                content=[
                    sa.text_chat_content("Describe this image."),
                    sa.image_url_chat_content("https://example.com/image.png"),
                ],
            )
        ],
    )
)
```

Attach request metadata and per-request headers when gateway or worker tracing needs them:

```python
result = client.chat.run(
    sa.ChatRunOptions(
        request_id="req_123",
        agent_id="33333333-3333-4333-8333-333333333333",
        category="fabric",
        message="Summarize this request context.",
        metadata={
            "session_id": "sess_123",
            "user_id": "user_456",
            "trace_id": "trace_789",
        },
        headers={"X-Trace-ID": "trace_789"},
    )
)
```

`request_id`, `category`, and `metadata` are sent in the chat body. Custom headers are forwarded when the SDK creates non-streaming, SSE, or WebSocket chat requests. Use `extra_body` for gateway fields that are not yet exposed as first-class SDK options.

## SSE Streaming

SSE is the default stream transport and works well with most HTTP gateways and proxies:

```python
text = client.chat.run_stream(
    sa.ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Fetch https://example.com and summarize it in one paragraph.",
    ),
    sa.ChatStreamHandlers(
        on_text_delta=lambda delta, event: print(delta, end=""),
        on_event=lambda event: None,
    ),
)

print("\n\nFinal text:", text)
```

## WebSocket Streaming

WebSocket streaming is optional. Install the `ws` extra first:

```bash
pip install --upgrade 'sea-agent-sdk[ws]'
```

```python
text = client.chat.run_stream(
    sa.ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Tell me what tools you can use, then answer with a short plan.",
    ),
    sa.ChatStreamHandlers(
        transport=sa.STREAM_TRANSPORT_WS,
        on_text_delta=lambda delta, event: print(delta, end=""),
    ),
)
```

## Worker Stream Event Format

`agent-gateway` forwards worker stream events as SSE blocks or WebSocket messages. The SDK normalizes both transports into `ChatStreamEvent(event, data)`. Use `on_text_delta` for assistant text and `on_event` for all raw lifecycle, tool, skill, and terminal events.

SSE frames use the standard event/data envelope:

```text
event: response.text.delta
data: {"type":"response.text.delta","response_id":"run_xxx","item_id":"item_run_xxx_msg","output_index":0,"content_index":0,"delta":"hello"}
```

WebSocket frames carry the same payload under `data`:

```json
{
  "event": "response.text.delta",
  "data": {
    "type": "response.text.delta",
    "response_id": "run_xxx",
    "item_id": "item_run_xxx_msg",
    "output_index": 0,
    "content_index": 0,
    "delta": "hello"
  }
}
```

Common worker event sequence:

| Event | When it appears | Important fields in `data` |
| --- | --- | --- |
| `response.created` | Run accepted and response object created | `type`, `response.id`, `response.status`, `response.model`, `response.metadata` |
| `response.in_progress` | Run enters processing | `type`, `response.id`, `response.status` |
| `response.output_item.added` | Assistant message item or tool call item starts | `response_id`, `output_index`, `item.type`, `item.id`, `item.status`; tool calls also include `item.call_id`, `item.name` |
| `response.content_part.added` | Assistant text content part starts | `response_id`, `item_id`, `output_index`, `content_index`, `part.type` |
| `response.text.delta` | Assistant text token/chunk | `response_id`, `item_id`, `output_index`, `content_index`, `delta` |
| `response.function_call_arguments.done` | Tool call arguments are finalized | `response_id`, `item_id`, `call_id`, `name`, `arguments` as a JSON string |
| `fabric.tool.started` | Worker starts a tool call | `tool.id`, `tool.call_id`, `tool.name`, `tool.status`, `tool.arguments` |
| `fabric.tool.completed` | Worker finishes a tool call | `tool.status`, `tool.output`, `tool.output_text`, `tool.output_type`; structured tool protocols may add `tool.structured_content`, `tool.protocol_type`, `tool.tool_response` |
| `fabric.skill.started` | Worker loads a skill through a `read_file` tool call | `skill.id`, `skill.name`, `skill.status`, `skill.path` |
| `fabric.skill.completed` | Skill file load completes | `skill.status`, `skill.output`, `skill.output_text`, `skill.path` |
| `response.text.done` | Assistant final text is known | `response_id`, `item_id`, `content_index`, `text` |
| `response.content_part.done` | Assistant text content part completes | `part.type`, `part.text` |
| `response.output_item.done` | Assistant message or function call output item completes | `item.type`, `item.status`, `item.content` for messages; `item.call_id`, `item.arguments`, `item.output` for tool calls |
| `response.completed` | Run completed successfully | `response.id`, `response.status`, `response.usage`, `response.elapsed_ms`, `response.metadata`, `response.output` |
| `response.failed` | Run failed | `response.status`, `response.error.type`, `response.error.code`, `response.error.message` |
| `response.cancelled` | Run was cancelled | `response.status`, `response.cancel_reason` |

The SDK accumulates returned text from `response.text.delta`. It also keeps compatibility with legacy `response.output_text.delta`, `chat.response`, and `message.delta` text events. Tool, skill, usage, metadata, and terminal details are not passed to `on_text_delta`; inspect them in `on_event`.

## Replay an Existing Chat

If another SDK client or application created the chat, subscribe by chat ID. `after_seq` resumes from events after the specified sequence number.

```python
text = client.chat.stream(
    "chat_xxxxxxxxxxxxx",
    sa.ChatStreamHandlers(
        on_text_delta=lambda delta, event: print(delta, end=""),
    ),
    sa.ChatEventsOptions(after_seq=0),
)
```

Use `sa.STREAM_TRANSPORT_WS` with the same API to replay over WebSocket.

## Inline Agent Config

Pass `agent_config` when the request should not reference a registered agent. Runtime fields such as `temperature`, `max_turns`, and `timeout` are forwarded by `agent-gateway` to the worker.

```python
result = client.chat.run(
    sa.ChatRunOptions(
        category="fabric",
        agent_config={
            "agent": {
                "name": "inline-assistant",
                "model": "gpt-4.1-mini",
                "reasoning_effort": "medium",
                "temperature": 0.2,
                "max_turns": 6,
                "timeout": 120,
                "system_prompt": "Answer in Chinese and keep the answer brief.",
            }
        },
        message="Explain what agent-gateway does.",
    )
)
```

Declare a sandbox template when the gateway should start a sandbox for the inline agent. Supported template values are `react-game` and `react-web`.

```python
result = client.chat.run(
    sa.ChatRunOptions(
        category="fabric",
        agent_config={
            "agent": {
                "name": "inline-sandbox-agent",
                "model": "gpt-4.1-mini",
                "system_prompt": "Build and modify React apps inside the sandbox.",
            },
            "runtime": {
                "sandbox": {
                    "sandbox_template": "react-game",
                }
            },
        },
        message="Create a small React game.",
    )
)
```

## Register Tools, Skills, and Agents

`agent-gateway` uses server-generated UUID `id` values as resource identities. Registry lookup and association should use UUIDs; do not send removed `tool_key`, `skill_key`, or `agent_key` fields.

### Register an HTTP Tool

```python
tool = client.tools.register(
    {
        "name": "search_web",
        "description": "Search public web pages.",
        "runtime_type": "http",
        "endpoint": "https://example.com/tools/search",
        "service_name": "example",
        "method": "POST",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "enabled": True,
        "public": False,
    }
)
```

`service_name` is a top-level tool field beside `name`. It identifies the backing service shared by tools on the same server. If omitted, the gateway derives it from the endpoint host prefix; builtin and no-endpoint tools default to `deepagent`. Do not put `service_name` in metadata/config, and do not send `inject_user_credentials` in user-facing registration payloads.

### Register a Skill

```python
skill = client.skills.register(
    {
        "name": "web-research",
        "description": "Research a topic with web tools.",
        "instruction": "Search, compare sources, and summarize findings.",
        "required_tools": ["22222222-2222-4222-8222-222222222222"],
        "enabled": True,
        "public": False,
    }
)
```

When `required_tools` or `optional_tools` contains registered HTTP Tool UUID strings, the gateway normalizes them to:

```python
{"type": "http", "ref": "<tool-uuid>"}
```

Use object entries when you need non-default tool types:

```python
{
    "required_tools": [
        {"type": "http", "ref": "22222222-2222-4222-8222-222222222222"},
        {"type": "builtin", "ref": "seaart:generate_image"},
        {"type": "mcp", "ref": "filesystem:read_file", "server": "mcp-filesystem"},
    ]
}
```

`type` is required and must be `http`, `http_batch`, `builtin`, or `mcp`. MCP entries also require `server`. Do not use Tool `name` or old `tool_key` values as `ref`.

### Register an Agent

```python
agent = client.agents.register(
    {
        "name": "web_assistant",
        "category": "fabric",
        "system_prompt": "You are a web research assistant.",
        "skills": ["11111111-1111-4111-8111-111111111111"],
        "config": {"temperature": 0.2, "max_turns": 6},
        "enabled": True,
    }
)
```

## Skill Runtime Rules

| Field | Rule |
| --- | --- |
| `name` | Must match `^[a-z0-9-]+$`; use lowercase letters, numbers, and hyphens only |
| `description` | Required; keep it short because the gateway writes it to inline `SKILL.md` frontmatter |
| `instruction` | Required; full Markdown body for the skill |
| `required_tools` / `optional_tools` | Use UUID refs for registered HTTP, HTTP Batch, and registered builtin tools |

When an agent runs with a registered skill, the gateway assembles an inline skill document:

```md
---
name: web-research
description: Research a topic with web tools.
---

Search, compare sources, and summarize findings.
```

## Hook Endpoints

Register a hook endpoint for worker events:

```python
hook = client.hooks.register(
    {
        "name": "production-line-hook",
        "endpoint": "https://example.com/agent-hook",
        "description": "Receives Agent Worker events for the configured API key.",
        "metadata": {},
    }
)
```

Hooks use `ClientOptions.api_key` as `Authorization: Bearer ...`; do not send `api_key` in the payload. Worker calls use `POST`, and the receiver should filter by `event_id` in the event payload when needed.

## API Reference

| Area | Methods |
| --- | --- |
| System | `health()`, `metrics()` |
| Catalog | `list(options)` |
| Tools | `register(payload)`, `list(options)`, `get(tool_id)`, `update(tool_id, payload)`, `delete(tool_id)`, `resolve(tool_id)` |
| Skills | `register(payload)`, `list(options)`, `get(skill_id)`, `update(skill_id, payload)`, `delete(skill_id)` |
| Agents | `register(payload)`, `list(options)`, `get(agent_id)`, `update(agent_id, payload)`, `delete(agent_id)`, `capabilities(agent_id)` |
| Hooks | `register(payload)`, `list(options)`, `get(hook_id)`, `update(hook_id, payload)`, `delete(hook_id)` |
| Chat | `create_completion(payload)`, `stream_completion(payload, handlers)`, `run(options)`, `run_stream(options, handlers)`, `get(chat_id)`, `events(chat_id, options)`, `stream(chat_id, handlers, options)`, `cancel(chat_id)` |

## Stream Utilities

If you need to process raw stream data yourself, the package also exports these helpers:

```python
from sea_agent_sdk import (
    ChatStreamProcessor,
    parse_sse,
    parse_websocket_event,
    text_from_stream_event,
)
```

## Local Development

```bash
make test
make build
make check
```

## Next Steps

- Start with `client.chat.run()` for non-streaming requests.
- Use `client.chat.run_stream()` with SSE for most streaming integrations.
- Use `client.chat.stream()` with `after_seq` to resume an existing chat.
- Register tools, skills, and agents with UUID-based references only.
