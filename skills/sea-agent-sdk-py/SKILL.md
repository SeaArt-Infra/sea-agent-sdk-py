---
name: sea-agent-sdk-py
description: Integrate Python services with SeaArt Agent Gateway through the official sea-agent-sdk package. Use for catalog lookup, Tool, Skill, Agent, Hook, chat completion, SSE or WebSocket streaming, chat replay, and cancellation in Python 3.10+.
---

# SeaAgent Python SDK

Use `sea-agent-sdk` for Agent Gateway work in Python. Prefer its `Client` and stream helpers over hand-written HTTP or SSE code.

## Workflow

1. Inspect `pyproject.toml` and use Python 3.10 or newer.
2. Add the package with the project's environment manager, for example `pip install --upgrade sea-agent-sdk`.
3. Create one `Client` with the gateway endpoint, API key, and any global headers.
4. Use the lowercase client resource that matches the operation.
5. Run the project's focused test or `make test` after changing the integration.

The SDK appends `/agent-v2` when the configured endpoint does not already contain it. Store the API key outside source control. Send `X-User-ID` for Tool, Skill, and Agent writes when the gateway requires owner or operator metadata.

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
| Skill registration and listing | `skills` |
| Agent registration and inspection | `agents` |
| Multimodal charge reservation hook | `hooks` |
| Chat, streaming, replay, cancellation | `chat` |

Pass list filters in each resource's options object. Keep custom gateway fields in `extra_body` only when the SDK has no first-class option. Put request-specific HTTP headers in `headers` on `ChatRunOptions`, not in the JSON body.

## Verify And Protect Data

Run `make test` from the package root. Verify a health check or a non-streaming chat before adding streaming UI behavior. Do not expose gateway API keys in browser code, commits, logs, errors, or telemetry. Redact complete prompts and raw Tool output from diagnostic logs.
