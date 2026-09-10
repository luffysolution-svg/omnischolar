"""Provider registry and bounded runtime routing."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from omnischolar.core import OmniScholarError

from .models import (
    LiteratureProvider,
    LiteratureRecord,
    ProviderStatus,
    SearchRequest,
    SearchResult,
)


class LiteratureRouter:
    def __init__(self, providers: Iterable[LiteratureProvider], *, max_attempts: int = 4) -> None:
        self._providers = {provider.id: provider for provider in providers}
        self.max_attempts = max(1, max_attempts)

    def statuses(self) -> list[ProviderStatus]:
        return [provider.status for provider in self._providers.values()]

    def provider(self, provider_id: str) -> LiteratureProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise OmniScholarError(
                "unknown_provider",
                f"Unknown literature provider: {provider_id}",
                category="validation",
            ) from exc

    async def search(
        self, request: SearchRequest, provider_ids: list[str], *, fallback: bool = True
    ) -> SearchResult:
        if not provider_ids:
            raise OmniScholarError(
                "provider_required",
                "At least one literature provider is required",
                category="validation",
            )
        errors: list[dict[str, Any]] = []
        for provider_id in provider_ids[: self.max_attempts]:
            provider = self.provider(provider_id)
            try:
                return await provider.search(request)
            except OmniScholarError as error:
                errors.append(
                    {"provider": provider_id, "code": error.code, "retryable": error.retryable}
                )
                if not fallback or not error.retryable:
                    raise
        raise OmniScholarError(
            "providers_exhausted",
            "All selected literature providers failed",
            category="provider",
            retryable=True,
            details={"attempts": errors},
        )

    async def get(self, provider_id: str, identifier: str) -> LiteratureRecord:
        return await self.provider(provider_id).get(identifier)

    async def graph(
        self, provider_id: str, identifier: str, kind: str, **options: Any
    ) -> SearchResult:
        provider = self.provider(provider_id)
        graph = getattr(provider, "graph", None)
        if graph is None:
            raise OmniScholarError(
                "unsupported_capability",
                f"{provider_id} does not support literature.{kind}",
                category="capability",
            )
        return cast(SearchResult, await graph(identifier, kind, **options))

    async def fulltext(
        self, provider_id: str, identifier: str, *, fetch: bool = False
    ) -> dict[str, Any]:
        provider = self.provider(provider_id)
        fulltext = getattr(provider, "fulltext", None)
        if fulltext is None:
            raise OmniScholarError(
                "unsupported_capability",
                f"{provider_id} does not support full text",
                category="capability",
            )
        try:
            return cast(dict[str, Any], await fulltext(identifier, fetch=fetch))
        except TypeError:
            if fetch:
                raise OmniScholarError(
                    "unsupported_capability",
                    f"{provider_id} resolves but does not fetch full text",
                    category="capability",
                ) from None
            return cast(dict[str, Any], await fulltext(identifier))

    async def journal_metrics(self, provider_id: str, query: str) -> dict[str, Any]:
        provider = self.provider(provider_id)
        metrics = getattr(provider, "metrics", None)
        if metrics is None:
            raise OmniScholarError(
                "unsupported_capability",
                f"{provider_id} does not support journal metrics",
                category="capability",
            )
        return cast(dict[str, Any], await metrics(query))
