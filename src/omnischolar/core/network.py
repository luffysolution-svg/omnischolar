"""Timeout-bound and size-bound HTTP transport."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, Self

import httpx

from .errors import OmniScholarError
from .redaction import redact_text


class BoundedHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 16 * 1024 * 1024,
        client: httpx.AsyncClient | None = None,
        known_secrets: tuple[str, ...] = (),
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self._client = client
        self._owned = client is None
        self._known_secrets = known_secrets

    async def __aenter__(self) -> Self:
        if self._client is None:
            self._client = httpx.AsyncClient(follow_redirects=False)
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._owned and self._client is not None:
            await self._client.aclose()
            self._client = None

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        content: bytes | AsyncIterator[bytes] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, bytes, str]]
        | Sequence[tuple[str, tuple[str, bytes, str]]]
        | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[httpx.Response]:
        if self._client is None:
            raise RuntimeError("BoundedHttpClient must be used as an async context manager")
        try:
            async with self._client.stream(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                content=content,
                data=data,
                files=files,
                timeout=timeout_seconds or self.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    raise self._http_error(response)
                yield response
        except httpx.TimeoutException as exc:
            raise OmniScholarError(
                "network_timeout",
                "The provider request timed out",
                category="network",
                retryable=True,
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            safe = redact_text(str(exc), self._known_secrets)
            raise OmniScholarError(
                "network_error",
                safe,
                category="network",
                retryable=True,
                cause=exc,
            ) from exc

    async def request_bytes(self, method: str, url: str, **kwargs: Any) -> bytes:
        limit = int(kwargs.pop("max_response_bytes", self.max_response_bytes))
        chunks: list[bytes] = []
        size = 0
        async with self.stream(method, url, **kwargs) as response:
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > limit:
                    raise OmniScholarError(
                        "response_too_large",
                        f"Provider response exceeded the {limit}-byte limit",
                        category="limits",
                    )
                chunks.append(chunk)
        return b"".join(chunks)

    async def request_text(self, method: str, url: str, **kwargs: Any) -> str:
        return (await self.request_bytes(method, url, **kwargs)).decode("utf-8", errors="replace")

    async def request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        raw = await self.request_bytes(method, url, **kwargs)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OmniScholarError(
                "invalid_provider_response",
                "The provider returned invalid JSON",
                category="provider",
                cause=exc,
            ) from exc

    @staticmethod
    def _http_error(response: httpx.Response) -> OmniScholarError:
        status = response.status_code
        retryable = status in {408, 409, 425, 429} or status >= 500
        category = "authentication" if status in {401, 403} else "provider"
        return OmniScholarError(
            "provider_http_error",
            f"Provider request failed with HTTP {status}",
            category=category,
            retryable=retryable,
            http_status=status,
        )
