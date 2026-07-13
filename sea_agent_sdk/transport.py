from __future__ import annotations

import codecs
import json
import os
import socket
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from .errors import APIError, SeaAgentError, WebSocketDependencyError
from .types import QueryParams, to_jsonable


@dataclass(slots=True)
class Transport:
    endpoint: str
    api_key: str = ""
    headers: dict[str, str] | None = None
    timeout: float = 60.0

    def __post_init__(self) -> None:
        self.endpoint = normalize_agent_gateway_endpoint(self.endpoint)
        self.headers = dict(self.headers or {})
        if self.timeout <= 0:
            self.timeout = 60.0

    def get_json(self, path: str, query: QueryParams | None = None) -> Any:
        return self._request_json("GET", path, query, None, None)

    def get_text(self, path: str, query: QueryParams | None = None) -> str:
        return self._request_text("GET", path, query, None, "*/*", None)

    def get_stream(
        self,
        path: str,
        query: QueryParams | None,
        on_chunk: Callable[[str], None],
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._request_stream("GET", path, query, None, headers, on_chunk)

    def post_json(self, path: str, body: Any, headers: Mapping[str, str] | None = None) -> Any:
        return self._request_json("POST", path, None, body, headers)

    def post_text(self, path: str, body: Any) -> str:
        return self._request_text("POST", path, None, body, "*/*", None)

    def post_stream(
        self,
        path: str,
        body: Any,
        on_chunk: Callable[[str], None],
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._request_stream("POST", path, None, body, headers, on_chunk)

    def put_json(self, path: str, body: Any) -> Any:
        return self._request_json("PUT", path, None, body, None)

    def delete_json(self, path: str, query: QueryParams | None = None) -> Any:
        return self._request_json("DELETE", path, query, None, None)

    def websocket(
        self,
        path: str,
        query: QueryParams | None,
        initial_message: Any,
        on_message: Callable[[str], None],
        headers: Mapping[str, str] | None = None,
    ) -> None:
        try:
            import websocket  # type: ignore
        except ModuleNotFoundError as exc:
            raise WebSocketDependencyError() from exc

        url = self.build_websocket_url(path, query)
        request_headers = self.build_headers("*/*", False, headers)
        header_lines = [f"{key}: {value}" for key, value in request_headers.items()]

        if _is_debug_enabled():
            print("WS", url, file=sys.stderr)

        try:
            conn = websocket.create_connection(url, header=header_lines, timeout=self.timeout)
        except websocket.WebSocketBadStatusException as exc:
            status_code = int(exc.status_code)
            response_body = exc.resp_body
            if isinstance(response_body, bytes):
                response_body = response_body.decode("utf-8", errors="replace")
            elif response_body is not None and not isinstance(response_body, str):
                response_body = str(response_body)
            message = _error_message_from_response(response_body or str(exc))
            raise APIError(status_code, message) from exc
        try:
            if initial_message is not None:
                conn.send(json.dumps(to_jsonable(initial_message), ensure_ascii=False))

            while True:
                try:
                    message = conn.recv()
                except websocket.WebSocketConnectionClosedException:
                    return
                if message is None:
                    return
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                on_message(str(message))
        finally:
            conn.close()

    def build_url(self, path: str, query: QueryParams | None = None) -> str:
        parsed = parse.urlsplit(self.endpoint)
        base_path = parsed.path
        if not base_path.endswith("/"):
            base_path += "/"
        relative_path = path.lstrip("/")
        joined_path = _collapse_path(base_path + relative_path)

        query_pairs = parse.parse_qsl(parsed.query, keep_blank_values=True)
        values: dict[str, str] = {key: value for key, value in query_pairs}
        for key, value in (query or {}).items():
            if _is_zero_value(value):
                continue
            if isinstance(value, bool):
                values[key] = str(value).lower()
            else:
                values[key] = str(value)

        return parse.urlunsplit(
            parsed._replace(
                path=joined_path,
                query=parse.urlencode(values),
            )
        )

    def build_websocket_url(self, path: str, query: QueryParams | None = None) -> str:
        url = self.build_url(path, query)
        parsed = parse.urlsplit(url)
        if parsed.scheme == "http":
            parsed = parsed._replace(scheme="ws")
        elif parsed.scheme == "https":
            parsed = parsed._replace(scheme="wss")
        return parse.urlunsplit(parsed)

    def build_headers(
        self,
        accept: str,
        has_body: bool,
        request_headers: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}
        if accept:
            headers["Accept"] = accept
        if has_body:
            headers["Content-Type"] = "application/json"
        for key, value in (self.headers or {}).items():
            if key.strip():
                headers[key] = value
        for key, value in (request_headers or {}).items():
            if key.strip():
                headers[key] = value
        if self.api_key and not _has_header(headers, "Authorization"):
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request_json(
        self,
        method: str,
        path: str,
        query: QueryParams | None,
        body: Any,
        headers: Mapping[str, str] | None,
    ) -> Any:
        text = self._request_text(method, path, query, body, "application/json", headers)
        if text == "":
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            preview = " ".join(text.split())
            if len(preview) > 240:
                preview = preview[:240]
            raise SeaAgentError(f"expected JSON response, got: {preview}") from exc

    def _request_text(
        self,
        method: str,
        path: str,
        query: QueryParams | None,
        body: Any,
        accept: str,
        headers: Mapping[str, str] | None,
    ) -> str:
        req = self._build_request(method, path, query, body, accept, headers)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
        except error.HTTPError as exc:
            raw = exc.read()
            raise APIError(exc.code, _error_message_from_response(raw.decode("utf-8"))) from exc
        except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise SeaAgentError(f"request failed: {exc}") from exc
        return raw.decode("utf-8")

    def _request_stream(
        self,
        method: str,
        path: str,
        query: QueryParams | None,
        body: Any,
        headers: Mapping[str, str] | None,
        on_chunk: Callable[[str], None],
    ) -> None:
        req = self._build_request(method, path, query, body, "text/event-stream", headers)
        try:
            response = request.urlopen(req, timeout=self.timeout)
        except error.HTTPError as exc:
            raw = exc.read()
            raise APIError(exc.code, _error_message_from_response(raw.decode("utf-8"))) from exc
        except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise SeaAgentError(f"request failed: {exc}") from exc

        decoder = codecs.getincrementaldecoder("utf-8")()
        with response:
            while True:
                try:
                    raw = response.read(4096)
                except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
                    raise SeaAgentError(f"stream failed: {exc}") from exc
                if not raw:
                    tail = decoder.decode(b"", final=True)
                    if tail:
                        on_chunk(tail)
                    return
                chunk = decoder.decode(raw)
                if chunk:
                    on_chunk(chunk)

    def _build_request(
        self,
        method: str,
        path: str,
        query: QueryParams | None,
        body: Any,
        accept: str,
        headers: Mapping[str, str] | None,
    ) -> request.Request:
        url = self.build_url(path, query)
        data = None
        if body is not None:
            data = json.dumps(to_jsonable(body), ensure_ascii=False).encode("utf-8")

        if _is_debug_enabled():
            print(method, url, file=sys.stderr)

        return request.Request(
            url=url,
            data=data,
            headers=self.build_headers(accept, body is not None, headers),
            method=method,
        )


def normalize_agent_gateway_endpoint(endpoint: str) -> str:
    if endpoint.strip() == "":
        return endpoint

    parsed = parse.urlsplit(endpoint)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if "agent-v2" in segments:
        return parse.urlunsplit(parsed)

    segments.append("agent-v2")
    path = "/" + "/".join(segments)
    return parse.urlunsplit(parsed._replace(path=path))


def _collapse_path(path: str) -> str:
    parts: list[str] = []
    for part in path.split("/"):
        if part == "":
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def _is_zero_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    return False


def _error_message_from_response(text: str) -> str:
    if text == "":
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, dict) and "error" in parsed:
        return str(parsed["error"])
    return text


def _has_header(headers: Mapping[str, str], name: str) -> bool:
    return any(key.lower() == name.lower() for key in headers)


def _is_debug_enabled() -> bool:
    return os.environ.get("SEAAGENT_DEBUG") == "1"


NewTransport = Transport
normalizeAgentGatewayEndpoint = normalize_agent_gateway_endpoint
