"""Injectable transport used by all literature providers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from omnischolar.core import BoundedHttpClient


class LiteratureTransport(Protocol):
    async def json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: Any = None,
    ) -> Any: ...

    async def text(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str: ...

    async def bytes(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes: ...


class CoreLiteratureTransport:
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
    ) -> Any:
        return await self.client.request_json(
            method, url, params=params, headers=headers, json_body=body
        )

    async def text(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        return await self.client.request_text(method, url, params=params, headers=headers)

    async def bytes(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        return await self.client.request_bytes(method, url, params=params, headers=headers)
