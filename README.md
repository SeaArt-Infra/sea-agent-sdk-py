# Sea Agent Python SDK

SeaArt Agent 网关 Python SDK，用于通过 `agent-gateway` 调用 Agent 目录、工具、技能、Agent 注册、Hook 管理、Chat Completion、SSE 流式响应和 WebSocket 流式响应能力。

特点：

- 纯标准库实现，默认无第三方运行时依赖
- 自动补全 `agent-gateway` 的 `/agent-v2` API 前缀
- 兼容 `~/.seaagent/config.yaml` CLI 配置
- 支持 OpenAI 风格多轮消息和多模态 content parts
- 支持 SSE 流式响应解析，WebSocket 作为可选依赖
- 提供 Python `snake_case` API，同时保留少量 Go SDK 风格别名便于迁移

## 功能导航

| 能力 | Client 字段 | 功能 |
|------|-------------|------|
| 系统检查 | `client.system` / `client.System` | 健康检查和 metrics |
| Catalog | `client.catalog` / `client.Catalog` | 查询已解析的能力目录 |
| Tools | `client.tools` / `client.Tools` | 注册、查询、更新、删除、解析工具 |
| Skills | `client.skills` / `client.Skills` | 注册、查询、更新、删除技能 |
| Agents | `client.agents` / `client.Agents` | 注册、查询、更新、删除 Agent，查询能力 |
| Hooks | `client.hooks` / `client.Hooks` | 注册和管理 Worker 事件 Hook |
| Chat | `client.chat` / `client.Chat` | 非流式对话、流式对话、事件回放、取消会话 |

## 安装

从 PyPI 安装：

```bash
pip install --upgrade sea-agent-sdk
```

如果需要 WebSocket 流式能力：

```bash
pip install --upgrade 'sea-agent-sdk[ws]'
```

如果希望使用 PyYAML 读写更完整的 YAML 配置：

```bash
pip install --upgrade 'sea-agent-sdk[yaml]'
```

从 GitHub 安装最新代码：

```bash
pip install --upgrade git+https://github.com/SeaArt-Infra/sea-agent-sdk-py.git
```

要求：

- Python 3.10+

## 初始化

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

`endpoint` 可以是网关根地址，也可以是已经包含 `/agent-v2` 的地址。SDK 会在缺失时自动补全 `/agent-v2`。

也可以复用 seaagent CLI 配置：

```python
import sea_agent_sdk as sa

client = sa.new_client_from_config()
```

默认读取：

```yaml
endpoint: http://127.0.0.1:8080
apiKey: sa-xxxxxxxx
userId: production-line-123
```

`userId` 会映射为请求头 `X-User-ID`。当网关需要 provider、owner 或 operator 信息时，`tools`、`skills`、`agents` 写操作通常需要这个请求头。

## 系统检查

```python
health = client.system.health()
metrics = client.system.metrics()
print(health)
```

## 资源查询

List API 跟随 CLI 和网关过滤参数。常用参数包括 `search`、`status`、`provider`、`public`、`limit`、`offset`，兼容参数包括 `source_kind`、`owner_id`、`category`。

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

也可以直接传 dict：

```python
tools = client.tools.list(
    {
        "provider": "web-tools-mcp",
        "status": "active",
        "limit": 20,
    }
)
```

## Chat API

### 单轮对话

```python
result = client.chat.run(
    sa.ChatRunOptions(
        agent_id="33333333-3333-4333-8333-333333333333",
        message="Fetch https://example.com and explain what it is.",
    )
)
print(result)
```

### 多轮对话

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

### 多模态消息

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

### 请求元数据和自定义请求头

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

`request_id`、`category`、`metadata` 会进入请求体。`headers` 会在非流式、SSE 和 WebSocket Chat 请求中透传。

## SSE 流式对话

SSE 是默认流式协议，适合大多数 HTTP 网关和代理：

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

## WebSocket 流式对话

WebSocket 是可选能力，需要安装 `ws` extra：

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

## 回放已有 Chat

如果 Chat 是由其他进程、浏览器页面或 CLI 命令创建的，可以按 `chat_id` 订阅事件。`after_seq` 用于从指定序号之后继续消费：

```python
text = client.chat.stream(
    "chat_xxxxxxxxxxxxx",
    sa.ChatStreamHandlers(
        on_text_delta=lambda delta, event: print(delta, end=""),
    ),
    sa.ChatEventsOptions(after_seq=0),
)
```

使用 `sa.STREAM_TRANSPORT_WS` 可以通过同一 API 切换到 WebSocket 回放。

## Inline Agent Config

当请求不想引用已注册 Agent 时，可以传入 `agent_config`。`temperature`、`max_turns`、`timeout` 等运行时字段会由 `agent-gateway` 转发给 Worker：

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

需要网关为 Inline Agent 启动沙盒时，可以声明 sandbox template。目前支持 `react-game` 和 `react-web`：

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

## 注册 Tools、Skills 和 Agents

`agent-gateway` 使用服务端生成的 UUID `id` 作为资源身份。注册资源后的查找和关联应使用 UUID，不要再发送已经移除的 `tool_key`、`skill_key` 或 `agent_key`。

### 注册 HTTP Tool

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

`service_name` 是工具顶层字段，用于标识同一服务上的工具集合。不要把 `service_name` 放进 metadata/config，也不要在用户侧注册 payload 中发送 `inject_user_credentials`。

### 注册 Skill

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

当 `required_tools` 或 `optional_tools` 包含已注册 HTTP Tool UUID 字符串时，网关会规范化为：

```python
{"type": "http", "ref": "<tool-uuid>"}
```

需要非默认工具类型时可以直接传对象：

```python
{
    "required_tools": [
        {"type": "http", "ref": "22222222-2222-4222-8222-222222222222"},
        {"type": "builtin", "ref": "seaart:generate_image"},
        {"type": "mcp", "ref": "filesystem:read_file", "server": "mcp-filesystem"},
    ]
}
```

`type` 必须是 `http`、`http_batch`、`builtin` 或 `mcp`。MCP 工具还需要 `server`。不要使用 Tool `name` 或旧 `tool_key` 作为 `ref`。

### 注册 Agent

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

注册 Worker 事件 Hook：

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

Hook 使用 `ClientOptions.api_key` 生成 `Authorization: Bearer ...` 请求头，不要在 payload 中发送 `api_key`。

## API Reference

| 模块 | 方法 |
|------|------|
| System | `health()`、`metrics()` |
| Catalog | `list(options)` |
| Tools | `register(payload)`、`list(options)`、`get(tool_id)`、`update(tool_id, payload)`、`delete(tool_id)`、`resolve(tool_id)` |
| Skills | `register(payload)`、`list(options)`、`get(skill_id)`、`update(skill_id, payload)`、`delete(skill_id)` |
| Agents | `register(payload)`、`list(options)`、`get(agent_id)`、`update(agent_id, payload)`、`delete(agent_id)`、`capabilities(agent_id)` |
| Hooks | `register(payload)`、`list(options)`、`get(hook_id)`、`update(hook_id, payload)`、`delete(hook_id)` |
| Chat | `create_completion(payload)`、`stream_completion(payload, handlers)`、`run(options)`、`run_stream(options, handlers)`、`get(chat_id)`、`events(chat_id, options)`、`stream(chat_id, handlers, options)`、`cancel(chat_id)` |

## 调试

设置 `SEAAGENT_DEBUG=1` 可以打印 HTTP 和 WebSocket 请求：

```bash
export SEAAGENT_DEBUG=1
```

## 本地开发

```bash
make test
make build
make check
```
