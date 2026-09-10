"""Service transport protocol and Core HTTP adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from omnischolar.core import BoundedHttpClient

ByteString = bytes


class ServiceTransport(Protocol):
    async def json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
        content: ByteString | None = None,
        timeout_seconds: float | None = None,
        max_response_bytes: int | None = None,
    ) -> Any: ...
    async def text(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
        timeout_seconds: float | None = None,
        max_response_bytes: int | None = None,
    ) -> str: ...
    async def bytes(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
        content: ByteString | None = None,
        max_response_bytes: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ByteString: ...
    async def multipart(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, ByteString, str]]
        | Sequence[tuple[str, tuple[str, ByteString, str]]]
        | None = None,
        timeout_seconds: float | None = None,
        max_response_bytes: int | None = None,
    ) -> Any: ...


class CoreServiceTransport:
    def __init__(self, client: BoundedHttpClient) -> None:
        self.client = client

    async def json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
        content: ByteString | None = None,
        timeout_seconds: float | None = None,
        max_response_bytes: int | None = None,
    ) -> Any:
        options: dict[str, Any] = {
            "params": params,
            "headers": headers,
            "json_body": body,
            "content": content,
        }
        if timeout_seconds is not None:
            options["timeout_seconds"] = timeout_seconds
        if max_response_bytes is not None:
            options["max_response_bytes"] = max_response_bytes
        return await self.client.request_json(method, url, **options)

    async def text(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
        timeout_seconds: float | None = None,
        max_response_bytes: int | None = None,
    ) -> str:
        options: dict[str, Any] = {
            "params": params,
            "headers": headers,
            "json_body": body,
        }
        if timeout_seconds is not None:
            options["timeout_seconds"] = timeout_seconds
        if max_response_bytes is not None:
            options["max_response_bytes"] = max_response_bytes
        return await self.client.request_text(method, url, **options)

    async def bytes(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
        content: ByteString | None = None,
        max_response_bytes: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ByteString:
        options: dict[str, Any] = {
            "params": params,
            "headers": headers,
            "json_body": body,
            "content": content,
        }
        if max_response_bytes is not None:
            options["max_response_bytes"] = max_response_bytes
        if timeout_seconds is not None:
            options["timeout_seconds"] = timeout_seconds
        return await self.client.request_bytes(method, url, **options)

    async def multipart(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, ByteString, str]]
        | Sequence[tuple[str, tuple[str, ByteString, str]]]
        | None = None,
        timeout_seconds: float | None = None,
        max_response_bytes: int | None = None,
    ) -> Any:
        options: dict[str, Any] = {"headers": headers, "data": data, "files": files}
        if timeout_seconds is not None:
            options["timeout_seconds"] = timeout_seconds
        if max_response_bytes is not None:
            options["max_response_bytes"] = max_response_bytes
        return await self.client.request_json(method, url, **options)
