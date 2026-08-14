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

When `agent_id` is set, the SDK sends the same value in `X-Agent-ID` and the JSON `agent_id` field; the gateway gives the header priority during the compatibility rollout.

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

## Per-Chat Reasoning

Use the top-level `reasoning_effort` option only to override the selected Agent
for this run. Leave it as `None` when the caller did not choose a level so the
Agent and Fabric defaults remain effective. The supported platform values are
`off`, `on`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`;
prefer the exported `REASONING_EFFORT_*` constants and only select values
verified for the Agent's model route. Do not send provider-specific thinking
fields through `extra_body`.

## Agent Default Reasoning

To save a default level on an Agent, set `model.reasoning_effort` in the
concise registration payload. A chat without `reasoning_effort` uses that
default; an explicit chat value applies only to that chat. Full create and
update payloads use `model_config.reasoning_effort` instead.

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

Use `client.mcps` or `client.Mcps` for `register`, `list`, `get`, `update`, `delete`, and `connection_info`. Registration and updates accept `streamable-http` or legacy `sse` transports. Include both `X-User-ID` and `X-Flag: 1` for MCP mutations. Gateway never returns stored upstream header values, only `header_keys`.

To call MCP tools, use `connection_info(mcp_id)` and pass `info.url` and `info.headers` to an official MCP SDK client (`mcp` package, `streamablehttp_client`); the gateway endpoint is standard streamable-HTTP and the SDK does not implement the protocol itself. Upstream credentials stay server-side. `tools` and `call` still work but are deprecated private REST shells; they only support streamable-http upstreams.

## Bind MCP Servers To Skills

Select an `active`, current-user-visible MCP Server UUID from `client.mcps`
registration or listing; never accept a `server_url` in a Skill payload.

```python
client.skills.register(
    {
        "name": "mcp-research",
        "instruction": "Use the registered MCP tools when relevant.",
        "config": {"mcp_servers": ["<registered-mcp-server-uuid>"]},
        "enabled": True,
    }
)
```

`config.mcp_servers` is separate from `required_tools`: do not represent an
MCP Server UUID as a Tool reference. Gateway resolves the UUID and enforces
its active status and visibility. Skill runtime binding currently supports
an unauthenticated Streamable HTTP endpoint. The MCP Server `public` field
controls cross-production-line sharing, so keep it false unless sharing is
intended.

Pass list filters in each resource's options object. Keep custom gateway fields in `extra_body` only when the SDK has no first-class option. Put request-specific HTTP headers in `headers` on `ChatRunOptions`, not in the JSON body.

## Agent Skill Preload

Agent registration keeps `skills` as an array of Skill UUIDs. Add a UUID to
`pre_skills` only when that Skill is expected in most runs and the model needs
its full instruction before deciding what to do. Gateway injects it into the
resolved system prompt and avoids the initial Worker `read_file` call for its
`SKILL.md`, at the cost of system-prompt tokens on every run. Keep conditional,
occasional, long, or low-confidence Skills only in `skills` for progressive
Worker loading; do not preload a Skill merely because it is short.
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
