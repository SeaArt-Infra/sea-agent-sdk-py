# sea-agent-sdk-py

> Beta: SDK API and agent-gateway behavior may still change with gateway versions.

Python SDK for `agent-gateway`. It wraps the gateway APIs for catalog lookup, resource registration, chat completion, SSE streaming, WebSocket streaming, chat replay, and hook management.

## Available Resources

| Resource | Client field | What it does |
| --- | --- | --- |
| System | `client.system` | Health and metrics checks |
| Catalog | `client.catalog` | List resolved catalog entries |
| Tools | `client.tools` | Register, list, update, delete, and resolve tools |
| Skills | `client.skills` | Register, list, update, and delete skills |
| Agents | `client.agents` | Register, list, update, delete, and inspect agents |
| Hooks | `client.hooks` | Register and manage worker event hook endpoints |
| Chat | `client.chat` | Run chat, stream chat, replay events, and cancel chats |

Go-style aliases such as `client.Chat.Run(...)` and `NewClient(...)` are also provided for migration convenience.

## Quick Start

Install locally while this package is in development:

```bash
pip install -e .
```

Create a client and run a chat request:

```python
import os

from sea_agent_sdk import ChatRunOptions, Client, ClientOptions

client = Client(
    ClientOptions(
        endpoint="http://127.0.0.1:8080",
        api_key=os.environ.get("AGENT_GATEWAY_API_KEY", ""),
        headers={"X-User-ID": "production-line-123"},
    )
)

result = client.chat.run(
    ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Search recent AI news and summarize the top 3 items.",
    )
)
print(result)
```

Check gateway health:

```python
health = client.system.health()
print(health)
```

## Configuration

Pass options directly:

```python
client = Client(
    endpoint="http://127.0.0.1:8080",
    api_key=os.environ.get("AGENT_GATEWAY_API_KEY", ""),
    headers={"X-User-ID": "production-line-123"},
)
```

Or reuse the CLI config:

```python
from sea_agent_sdk import new_client_from_config

client = new_client_from_config()
```

By default, the SDK reads `~/.seaagent/config.yaml`:

```yaml
endpoint: http://127.0.0.1:8080
apiKey: sa-xxxxxxxx
userId: production-line-123
```

`endpoint` may be the gateway base URL or a URL that already includes `/agent-v2`. The SDK appends `/agent-v2` before sending requests when it is missing.

`X-User-ID` is required for `tools`, `skills`, and `agents` write operations when the gateway needs provider, owner, or operator metadata. `new_client_from_config` maps `userId` from the CLI config to `X-User-ID`.

## Listing Resources

List APIs follow CLI and gateway filters. Common filters are `search`, `status`, `provider`, `public`, `limit`, and `offset`. Compatibility filters include `source_kind`, `owner_id`, and `category`.

```python
from sea_agent_sdk import ToolListOptions

tools = client.tools.list(
    ToolListOptions(
        provider="web-tools-mcp",
        status="active",
        limit=20,
    )
)
print(tools)
```

You can also pass plain dictionaries:

```python
tools = client.tools.list({"provider": "web-tools-mcp", "status": "active", "limit": 20})
```

Pagination follows the gateway behavior: `limit` defaults to 20 when omitted or `<= 0`, the gateway caps values above 200, and `offset` starts at 0.

## Chat Requests

Use `message` for the common single-user-message case:

```python
result = client.chat.run(
    ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Fetch https://example.com and explain what it is.",
    )
)
```

Use `messages` for multi-turn conversations:

```python
from sea_agent_sdk import ChatMessage

result = client.chat.run(
    ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        messages=[
            ChatMessage(role="system", content="Answer in concise Chinese."),
            ChatMessage(role="user", content="Fetch https://example.com and explain what it is."),
        ],
    )
)
```

Use OpenAI-style content parts for multimodal messages:

```python
from sea_agent_sdk import ChatMessage, image_url_chat_content, text_chat_content

result = client.chat.run(
    ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        messages=[
            ChatMessage(
                role="user",
                content=[
                    text_chat_content("Describe this image."),
                    image_url_chat_content("https://example.com/image.png"),
                ],
            )
        ],
    )
)
```

Attach request metadata and per-request headers:

```python
result = client.chat.run(
    ChatRunOptions(
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

`request_id`, `category`, and `metadata` are sent in the chat body. Custom headers are forwarded when the SDK creates non-streaming, SSE, or WebSocket chat requests.

## Streaming

SSE is the default stream transport:

```python
from sea_agent_sdk import ChatRunOptions, ChatStreamHandlers

text = client.chat.run_stream(
    ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Fetch https://example.com and summarize it in one paragraph.",
    ),
    ChatStreamHandlers(
        on_text_delta=lambda delta, event: print(delta, end=""),
        on_event=lambda event: None,
    ),
)

print("\n\nFinal text:", text)
```

WebSocket streaming is optional:

```bash
pip install 'sea-agent-sdk[ws]'
```

```python
from sea_agent_sdk import STREAM_TRANSPORT_WS, ChatStreamHandlers

text = client.chat.run_stream(
    ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Tell me what tools you can use, then answer with a short plan.",
    ),
    ChatStreamHandlers(
        transport=STREAM_TRANSPORT_WS,
        on_text_delta=lambda delta, event: print(delta, end=""),
    ),
)
```

## Replay an Existing Chat

If another process, browser page, or CLI command created the chat, subscribe by chat ID. `after_seq` resumes from events after the specified sequence number.

```python
from sea_agent_sdk import ChatEventsOptions, ChatStreamHandlers

text = client.chat.stream(
    "chat_xxxxxxxxxxxxx",
    ChatStreamHandlers(on_text_delta=lambda delta, event: print(delta, end="")),
    ChatEventsOptions(after_seq=0),
)
```

Use `STREAM_TRANSPORT_WS` with the same API to replay over WebSocket.

## Inline Agent Config

Pass `agent_config` when the request should not reference a registered agent. Runtime fields such as `temperature`, `max_turns`, and `timeout` are forwarded by `agent-gateway` to the worker.

```python
result = client.chat.run(
    ChatRunOptions(
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
    ChatRunOptions(
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

Register an HTTP tool:

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

Register a skill:

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

Register an agent:

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

Hooks use `ClientOptions.api_key` as `Authorization: Bearer ...`; do not send `api_key` in the payload.

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

## Debugging

Set `SEAAGENT_DEBUG=1` to print outgoing HTTP and WebSocket requests:

```bash
export SEAAGENT_DEBUG=1
```
