---
name: sea-agent-sdk-py
description: Integrate Python services with SeaArt Agent Gateway through the official sea-agent-sdk package. Use for catalog lookup, Tool, MCP Server, Skill, Agent, Hook, chat completion, SSE or WebSocket streaming, chat replay, and cancellation in Python 3.10+.
---

# SeaAgent Python SDK

Use `sea-agent-sdk` for Agent Gateway work in Python. Prefer its `Client` and stream helpers over hand-written HTTP or SSE code.

## Workflow

1. Inspect `pyproject.toml` and use Python 3.10 or newer.
2. Add the package with the project's environment manager, for example `pip install --upgrade sea-agent-sdk`.
3. Create one `Client` with the gateway endpoint, API key, and any global headers.
4. Use the lowercase client resource that matches the operation.
5. Run the project's focused test or `make test` after changing the integration.

The SDK appends `/agent-v2` when the configured endpoint does not already contain it. Store the API key outside source control. Send `X-User-ID` for Tool, MCP Server, Skill, and Agent writes when the gateway requires owner or operator metadata.

## Create A Client

```python
import sea_agent_sdk as sa

client = sa.Client(
    sa.ClientOptions(
        endpoint=os.environ["AGENT_GATEWAY_ENDPOINT"],
        api_key=os.environ["AGENT_GATEWAY_API_KEY"],
        headers={"X-User-ID": user_id},
    )
)
```

Use `sa.new_client_from_config()` only when the service intentionally shares `~/.seaagent/config.yaml`.

## Run And Stream Chat

Use `message` for a single user turn and `messages` for a multi-turn or multimodal request. Do not set both `agent_config` and `skill_ids`; `skill_ids` add temporary Skills to an Agent run.

```python
result = client.chat.run(
    sa.ChatRunOptions(agent_id=agent_id, message="Summarize this request.")
)
```

Use SSE by default. Install the optional `ws` dependency and use WebSocket only when the caller needs a persistent connection or manages a WebSocket lifecycle.

```python
text = client.chat.run_stream(
    sa.ChatRunOptions(agent_id=agent_id, message="Explain the result as it arrives."),
    sa.ChatStreamHandlers(
        transport=sa.STREAM_TRANSPORT_SSE,
        on_text_delta=lambda delta, event: print(delta, end=""),
    ),
)
print("\nFinal text:", text)
```

Preserve the default reconnect behavior unless product requirements demand a different retry policy. Use `client.chat.events`, `client.chat.stream`, or `client.chat.cancel` to replay, resume, or cancel an existing chat.

## Select Resources

| Task | Client resource |
| --- | --- |
| Health or metrics | `system` |
| Resolved catalog entries | `catalog` |
| Tool registration and resolution | `tools` |
| MCP Server registration and tool proxying | `mcps` |
| Skill registration and listing | `skills` |
| Agent registration and inspection | `agents` |
| Multimodal charge reservation hook | `hooks` |
| Chat, streaming, replay, cancellation | `chat` |

## Manage MCP Servers

Use `client.mcps` or `client.Mcps` for `register`, `list`, `get`, `update`, `delete`, `tools`, and `call`. Registration and updates accept `streamable-http` or legacy `sse` transports; `call` accepts `{ "name": ..., "arguments": ..., "timeout_ms": ... }`. Include both `X-User-ID` and `X-Flag: 1` for MCP mutations. Gateway never returns stored upstream header values, only `header_keys`; access to a private server's `tools` and `call` operations requires its owner or `X-Admin-Access: 1`.

Pass list filters in each resource's options object. Keep custom gateway fields in `extra_body` only when the SDK has no first-class option. Put request-specific HTTP headers in `headers` on `ChatRunOptions`, not in the JSON body.

## Agent Skill Preload

Agent registration keeps `skills` as an array of Skill UUIDs. Also add a short
instruction needed on every run to `pre_skills`: gateway injects it into the
resolved system prompt and avoids the initial Worker `read_file` call for its
`SKILL.md`. Skills only in `skills` remain progressively loaded by Worker.
`pre_skills` must be a duplicate-free subset of `skills`; every bound Skill
keeps its tool bindings.

## Medium-Term Memory Policy

For a registered Agent, use optional `config.memory_policy` in a concise
registration payload or `agent_config.memory_policy` in a low-level
create/update payload. Omit it for the normal persistent-session behavior;
use it to restrict a particular Agent:

```python
"config": {
    "memory_policy": {
        "medium_term": {"recall": False, "learn": False},
    },
},
```

For a complete persistent session, `medium_term.recall` and
`medium_term.learn` both default to `true`. `recall` retrieves relevant
semantic memory as background context; `learn` queues a qualifying completed
run for asynchronous extraction rather than saving it synchronously. Both
default to `false` for ephemeral runs (no `metadata.session_id`) and are forced
off by a missing memory scope, user opt-out, or Worker
`MEMORY_MEDIUM_TERM_ENABLED=false`. Agent policy and request-level
`memory_policy` only restrict; pass a request-level override through
`extra_body`. Long-term recall and writes remain disabled by default.

## Verify And Protect Data

Run `make test` from the package root. Verify a health check or a non-streaming chat before adding streaming UI behavior. Do not expose gateway API keys in browser code, commits, logs, errors, or telemetry. Redact complete prompts and raw Tool output from diagnostic logs.
