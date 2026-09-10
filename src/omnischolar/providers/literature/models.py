"""Shared literature models used by providers and agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol


@dataclass(slots=True)
class Author:
    name: str
    id: str | None = None
    institutions: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class LiteratureRecord:
    id: str
    title: str
    provider: str
    authors: list[Author] = field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    open_access_url: str | None = None
    citation_count: int | None = None
    identifiers: dict[str, str] = field(default_factory=dict)
    license: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    retrieved_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(slots=True)
class SearchRequest:
    query: str
    limit: int = 20
    cursor: str | None = None
    page: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    open_access_only: bool = False
    fields: tuple[str, ...] = ()


@dataclass(slots=True)
class SearchResult:
    provider: str
    items: list[LiteratureRecord]
    total: int | None = None
    next_cursor: str | None = None
    requests: int = 1
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    id: str
    enabled: bool
    capabilities: tuple[str, ...]
    credential_status: Literal["configured", "missing", "not_required"]
    validation_status: Literal["mock_passed", "live_passed", "live_untested", "contract_blocked"]
    docs: tuple[str, ...]
    limitations: tuple[str, ...] = ()
    paid: bool = False


class LiteratureProvider(Protocol):
    id: str

    @property
    def status(self) -> ProviderStatus: ...

    async def search(self, request: SearchRequest) -> SearchResult: ...

    async def get(self, identifier: str) -> LiteratureRecord: ...
