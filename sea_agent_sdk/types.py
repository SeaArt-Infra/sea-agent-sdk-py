from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Callable, Literal

QueryParams = dict[str, Any]
StreamTransport = Literal["sse", "ws"]
STREAM_TRANSPORT_SSE = "sse"
STREAM_TRANSPORT_WS = "ws"


@dataclass(slots=True)
class Config:
    endpoint: str = ""
    api_key: str = ""
    user_id: str = ""


@dataclass(slots=True)
class ClientOptions:
    endpoint: str = ""
    api_key: str = ""
    headers: dict[str, str] | None = None
    timeout: float = 60.0


@dataclass(slots=True)
class PaginationOptions:
    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class CatalogListOptions:
    capability_type: str = ""
    search: str = ""
    status: str = ""
    source_kind: str = ""
    owner_id: str = ""
    public: bool | None = None
    provider: str = ""
    category: str = ""
    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class ToolListOptions:
    search: str = ""
    status: str = ""
    source_kind: str = ""
    owner_id: str = ""
    public: bool | None = None
    provider: str = ""
    category: str = ""
    include_deleted: bool = False
    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class SkillListOptions:
    search: str = ""
    status: str = ""
    source_kind: str = ""
    owner_id: str = ""
    public: bool | None = None
    provider: str = ""
    category: str = ""
    include_deleted: bool = False
    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class AgentListOptions:
    search: str = ""
    status: str = ""
    owner_id: str = ""
    category: str = ""
    include_deleted: bool = False
    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class HookListOptions:
    search: str = ""
    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class ChatEventsOptions:
    after_seq: int = 0
    limit: int = 0


@dataclass(slots=True)
class ChatContentURL:
    url: str

    def to_dict(self) -> dict[str, str]:
        return {"url": self.url}


@dataclass(slots=True)
class ChatContentPart:
    type: str
    text: str = ""
    image_url: ChatContentURL | Mapping[str, Any] | None = None
    video_url: ChatContentURL | Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.text:
            result["text"] = self.text
        if self.image_url is not None:
            result["image_url"] = to_jsonable(self.image_url)
        if self.video_url is not None:
            result["video_url"] = to_jsonable(self.video_url)
        return result


def text_chat_content(text: str) -> ChatContentPart:
    return ChatContentPart(type="text", text=text)


def image_url_chat_content(url: str) -> ChatContentPart:
    return ChatContentPart(type="image_url", image_url=ChatContentURL(url=url))


def video_url_chat_content(url: str) -> ChatContentPart:
    return ChatContentPart(type="video_url", video_url=ChatContentURL(url=url))


TextChatContent = text_chat_content
ImageURLChatContent = image_url_chat_content
VideoURLChatContent = video_url_chat_content


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": to_jsonable(self.content),
        }


@dataclass(slots=True)
class ChatCompletionRequest:
    messages: list[ChatMessage | Mapping[str, Any]]
    request_id: str = ""
    agent_id: str = ""
    category: str = ""
    agent_config: dict[str, Any] | None = None
    skill_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None
    stream: bool = False
    headers: dict[str, str] | None = None
    extra_body: dict[str, Any] | None = None


@dataclass(slots=True)
class ChatRunOptions:
    request_id: str = ""
    agent_id: str = ""
    category: str = ""
    agent_config: dict[str, Any] | None = None
    skill_ids: list[str] | None = None
    message: str = ""
    messages: list[ChatMessage | Mapping[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    extra_body: dict[str, Any] | None = None


@dataclass(slots=True)
class ChatStreamEvent:
    event: str
    data: Any


@dataclass(slots=True)
class ChatStreamHandlers:
    transport: StreamTransport = STREAM_TRANSPORT_SSE
    on_event: Callable[[ChatStreamEvent], None] | None = None
    on_text_delta: Callable[[str, ChatStreamEvent], None] | None = None


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if is_dataclass(value):
        result: dict[str, Any] = {}
        for field in fields(value):
            field_value = getattr(value, field.name)
            if field_value is not None:
                result[field.name] = to_jsonable(field_value)
        return result
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def option_value(options: Any, name: str, default: Any = None) -> Any:
    if options is None:
        return default
    if isinstance(options, Mapping):
        return options.get(name, default)
    return getattr(options, name, default)


def options_to_query(options: Any, names: list[str]) -> QueryParams:
    return {name: option_value(options, name) for name in names}
