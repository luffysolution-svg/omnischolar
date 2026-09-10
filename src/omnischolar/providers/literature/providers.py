"""Official literature API adapters with normalized, bounded pagination semantics."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from urllib.parse import quote

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from omnischolar.core import OmniScholarError

from .models import Author, LiteratureRecord, ProviderStatus, SearchRequest, SearchResult
from .transport import LiteratureTransport

DOCS = {
    "semantic-scholar": "https://api.semanticscholar.org/api-docs/graph",
    "openalex": "https://docs.openalex.org/",
    "pubmed": "https://www.ncbi.nlm.nih.gov/books/NBK25497/",
    "arxiv": "https://info.arxiv.org/help/api/user-manual.html",
    "crossref": "https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
    "unpaywall": "https://unpaywall.org/products/api",
    "easyscholar": "https://www.easyscholar.cc/open/getPublicationRank",
}


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _year(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 1000 <= number <= 9999 else None


def _authors(values: Any) -> list[Author]:
    if not isinstance(values, list):
        return []
    result: list[Author] = []
    for value in values:
        if isinstance(value, str):
            result.append(Author(value))
        elif isinstance(value, Mapping):
            name = _text(value.get("name")) or " ".join(
                item for item in (_text(value.get("given")), _text(value.get("family"))) if item
            )
            result.append(
                Author(name or "Unknown", _text(value.get("authorId") or value.get("id")))
            )
    return result


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _object(value: Any, provider: str, field: str = "response") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OmniScholarError(
            "provider_schema_mismatch",
            f"{provider} {field} must be an object",
            category="provider",
        )
    return value


def _list(value: Any, provider: str, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise OmniScholarError(
            "provider_schema_mismatch",
            f"{provider} response is missing list field {field}",
            category="provider",
        )
    return value


class RateGate:
    """Serialize requests to respect a provider's minimum interval."""

    def __init__(
        self,
        interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.interval = interval_seconds
        self.clock = clock
        self.sleep = sleep
        self._last: float | None = None
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = self.clock()
            if self._last is not None:
                remaining = self.interval - (now - self._last)
                if remaining > 0:
                    await self.sleep(remaining)
            self._last = self.clock()


class BaseProvider:
    id = "base"
    capabilities: tuple[str, ...] = ()

    def __init__(self, transport: LiteratureTransport, *, enabled: bool = True) -> None:
        self.transport = transport
        self.enabled = enabled

    @property
    def status(self) -> ProviderStatus:
        return ProviderStatus(
            id=self.id,
            enabled=self.enabled,
            capabilities=self.capabilities,
            credential_status="not_required",
            validation_status="mock_passed",
            docs=(DOCS[self.id],),
        )

    def ensure_enabled(self) -> None:
        if not self.enabled:
            raise OmniScholarError(
                "provider_unavailable",
                f"{self.id} is disabled",
                category="provider",
                retryable=True,
            )

    def unsupported(self, capability: str) -> None:
        raise OmniScholarError(
            "unsupported_capability",
            f"{self.id} does not support {capability}",
            category="capability",
        )


class SemanticScholarProvider(BaseProvider):
    id = "semantic-scholar"
    capabilities = (
        "literature.search",
        "literature.lookup",
        "literature.references",
        "literature.citations",
        "literature.recommendations",
        "fulltext.resolve",
    )
    base_url = "https://api.semanticscholar.org/graph/v1"
    fields = (
        "paperId,title,abstract,authors,year,venue,citationCount,referenceCount,"
        "influentialCitationCount,externalIds,openAccessPdf,url,publicationDate,publicationTypes"
    )

    def __init__(
        self, transport: LiteratureTransport, *, api_key: str | None = None, enabled: bool = True
    ) -> None:
        super().__init__(transport, enabled=enabled)
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key} if self.api_key else {}

    @property
    def status(self) -> ProviderStatus:
        return ProviderStatus(
            id=self.id,
            enabled=self.enabled,
            capabilities=self.capabilities,
            credential_status="configured" if self.api_key else "not_required",
            validation_status="mock_passed",
            docs=(DOCS[self.id],),
        )

    @staticmethod
    def _map(raw_value: Any) -> LiteratureRecord:
        raw = _object(raw_value, "semantic-scholar", "paper")
        external = _mapping(raw.get("externalIds"))
        doi = _text(external.get("DOI"))
        open_pdf = _mapping(raw.get("openAccessPdf"))
        return LiteratureRecord(
            id=_text(raw.get("paperId")) or doi or "unknown",
            title=_text(raw.get("title")) or "Untitled",
            provider="semantic-scholar",
            authors=_authors(raw.get("authors")),
            abstract=_text(raw.get("abstract")),
            year=_year(raw.get("year")),
            venue=_text(raw.get("venue")),
            doi=doi,
            url=_text(raw.get("url")),
            open_access_url=_text(open_pdf.get("url")),
            citation_count=raw.get("citationCount")
            if isinstance(raw.get("citationCount"), int)
            else None,
            identifiers={
                str(key): str(value) for key, value in external.items() if value is not None
            },
            license=_text(open_pdf.get("license")),
            raw=raw,
        )

    async def search(self, request: SearchRequest) -> SearchResult:
        self.ensure_enabled()
        params: dict[str, Any] = {
            "query": request.query,
            "limit": min(max(request.limit, 1), 100),
            "offset": int(request.cursor or "0") if (request.cursor or "0").isdigit() else 0,
            "fields": ",".join(request.fields) if request.fields else self.fields,
        }
        if request.year_from or request.year_to:
            params["year"] = f"{request.year_from or ''}-{request.year_to or ''}"
        if request.open_access_only:
            params["openAccessPdf"] = ""  # Presence is the API's boolean filter.
        payload = _object(
            await self.transport.json(
                "GET", f"{self.base_url}/paper/search", params=params, headers=self._headers()
            ),
            self.id,
        )
        items = [self._map(item) for item in _list(payload.get("data"), self.id, "data")]
        next_value = payload.get("next")
        return SearchResult(
            self.id,
            items,
            payload.get("total") if isinstance(payload.get("total"), int) else None,
            str(next_value) if next_value is not None else None,
        )

    async def get(self, identifier: str) -> LiteratureRecord:
        self.ensure_enabled()
        payload = await self.transport.json(
            "GET",
            f"{self.base_url}/paper/{quote(identifier, safe='')}",
            params={"fields": self.fields},
            headers=self._headers(),
        )
        return self._map(payload)

    async def graph(
        self, identifier: str, kind: str, *, limit: int = 20, cursor: str | None = None
    ) -> SearchResult:
        self.ensure_enabled()
        if kind == "recommendations":
            url = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{quote(identifier, safe='')}"
            payload = _object(
                await self.transport.json(
                    "GET", url, params={"limit": min(limit, 500)}, headers=self._headers()
                ),
                self.id,
            )
            values = _list(payload.get("recommendedPapers", []), self.id, "recommendedPapers")
            return SearchResult(self.id, [self._map(item) for item in values])
        if kind not in {"references", "citations"}:
            self.unsupported(f"literature.{kind}")
        payload = _object(
            await self.transport.json(
                "GET",
                f"{self.base_url}/paper/{quote(identifier, safe='')}/{kind}",
                params={
                    "limit": min(limit, 1_000),
                    "offset": int(cursor or "0"),
                    "fields": self.fields,
                },
                headers=self._headers(),
            ),
            self.id,
        )
        key = "citedPaper" if kind == "references" else "citingPaper"
        values = _list(payload.get("data"), self.id, "data")
        items = [
            self._map(value[key]) for value in values if isinstance(value, dict) and value.get(key)
        ]
        next_value = payload.get("next")
        return SearchResult(
            self.id,
            items,
            payload.get("total"),
            str(next_value) if next_value is not None else None,
        )

    async def fulltext(self, identifier: str) -> dict[str, Any]:
        item = await self.get(identifier)
        return {
            "provider": self.id,
            "id": item.id,
            "available": bool(item.open_access_url),
            "url": item.open_access_url,
            "license": item.license,
            "downloaded": False,
        }


class OpenAlexProvider(BaseProvider):
    id = "openalex"
    capabilities = (
        "literature.search",
        "literature.lookup",
        "literature.references",
        "literature.citations",
    )
    base_url = "https://api.openalex.org"

    def __init__(
        self,
        transport: LiteratureTransport,
        *,
        api_key: str | None = None,
        email: str | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(transport, enabled=enabled)
        self.api_key = api_key
        self.email = email

    def _params(self, values: dict[str, Any]) -> dict[str, Any]:
        if self.api_key:
            values["api_key"] = self.api_key
        elif self.email:
            values["mailto"] = self.email
        return values

    @staticmethod
    def _map(raw_value: Any) -> LiteratureRecord:
        raw = _object(raw_value, "openalex", "work")
        authors: list[Author] = []
        for authorship in (
            raw.get("authorships", []) if isinstance(raw.get("authorships"), list) else []
        ):
            author = _mapping(authorship.get("author")) if isinstance(authorship, dict) else {}
            institutions = [
                {"name": item.get("display_name", "Unknown"), "id": item.get("id", "")}
                for item in authorship.get("institutions", [])
                if isinstance(item, dict)
            ]
            authors.append(
                Author(author.get("display_name", "Unknown"), author.get("id"), institutions)
            )
        primary = _mapping(raw.get("primary_location"))
        source = _mapping(primary.get("source"))
        oa = _mapping(raw.get("open_access"))
        doi = _text(raw.get("doi"))
        if doi:
            doi = re.sub(r"^https?://doi\.org/", "", doi, flags=re.IGNORECASE)
        identifier = _text(raw.get("id")) or doi or "unknown"
        return LiteratureRecord(
            identifier,
            _text(raw.get("title")) or "Untitled",
            "openalex",
            authors,
            year=_year(raw.get("publication_year")),
            venue=_text(source.get("display_name")),
            doi=doi,
            url=_text(raw.get("id")),
            open_access_url=_text(oa.get("oa_url")),
            citation_count=raw.get("cited_by_count")
            if isinstance(raw.get("cited_by_count"), int)
            else None,
            identifiers={"OpenAlex": identifier},
            raw=raw,
        )

    async def search(self, request: SearchRequest) -> SearchResult:
        self.ensure_enabled()
        filters: list[str] = []
        if request.year_from:
            filters.append(f"from_publication_date:{request.year_from}-01-01")
        if request.year_to:
            filters.append(f"to_publication_date:{request.year_to}-12-31")
        if request.open_access_only:
            filters.append("is_oa:true")
        params: dict[str, Any] = {"search": request.query, "per-page": min(request.limit, 100)}
        if request.cursor is not None:
            params["cursor"] = request.cursor
        elif request.page is not None:
            params["page"] = min(max(request.page, 1), 10_000)
        else:
            params["cursor"] = "*"
        if filters:
            params["filter"] = ",".join(filters)
        payload = _object(
            await self.transport.json("GET", f"{self.base_url}/works", params=self._params(params)),
            self.id,
        )
        meta = _mapping(payload.get("meta"))
        return SearchResult(
            self.id,
            [self._map(item) for item in _list(payload.get("results"), self.id, "results")],
            meta.get("count") if isinstance(meta.get("count"), int) else None,
            _text(meta.get("next_cursor")),
        )

    async def get(self, identifier: str) -> LiteratureRecord:
        self.ensure_enabled()
        normalized = re.sub(r"^https?://openalex\.org/", "", identifier, flags=re.IGNORECASE)
        payload = await self.transport.json(
            "GET", f"{self.base_url}/works/{quote(normalized, safe='')}", params=self._params({})
        )
        return self._map(payload)

    async def graph(
        self, identifier: str, kind: str, *, limit: int = 20, cursor: str | None = None
    ) -> SearchResult:
        if kind == "references":
            item = await self.get(identifier)
            references = item.raw.get("referenced_works", [])
            values = references if isinstance(references, list) else []
            return SearchResult(
                self.id,
                [
                    LiteratureRecord(
                        str(value), "Untitled", self.id, identifiers={"OpenAlex": str(value)}
                    )
                    for value in values[: min(limit, 200)]
                ],
            )
        if kind != "citations":
            self.unsupported(f"literature.{kind}")
        normalized = re.sub(r"^https?://openalex\.org/", "", identifier, flags=re.IGNORECASE)
        request = SearchRequest("", limit=limit, cursor=cursor)
        params = {
            "filter": f"cites:{normalized}",
            "per-page": min(request.limit, 100),
            "cursor": cursor or "*",
        }
        payload = _object(
            await self.transport.json("GET", f"{self.base_url}/works", params=self._params(params)),
            self.id,
        )
        meta = _mapping(payload.get("meta"))
        return SearchResult(
            self.id,
            [self._map(item) for item in _list(payload.get("results"), self.id, "results")],
            meta.get("count"),
            _text(meta.get("next_cursor")),
        )


class PubMedProvider(BaseProvider):
    id = "pubmed"
    capabilities = (
        "literature.search",
        "literature.lookup",
        "literature.references",
        "literature.citations",
        "fulltext.resolve",
        "fulltext.fetch",
    )
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        transport: LiteratureTransport,
        *,
        api_key: str | None = None,
        email: str | None = None,
        tool: str = "omnischolar",
        enabled: bool = True,
        gate: RateGate | None = None,
    ) -> None:
        super().__init__(transport, enabled=enabled)
        self.api_key = api_key
        self.email = email
        self.tool = tool
        self.gate = gate or RateGate(0.1 if api_key else 1 / 3)

    def _params(self, values: dict[str, Any]) -> dict[str, Any]:
        values.update({"db": "pubmed", "retmode": "json", "tool": self.tool})
        if self.email:
            values["email"] = self.email
        if self.api_key:
            values["api_key"] = self.api_key
        return values

    @staticmethod
    def _map(identifier: str, raw_value: Any) -> LiteratureRecord:
        raw = _object(raw_value, "pubmed", "record")
        identifiers = {"PMID": identifier}
        for value in raw.get("articleids", []) if isinstance(raw.get("articleids"), list) else []:
            if not isinstance(value, dict):
                continue
            kind = _text(value.get("idtype"))
            content = _text(value.get("value") or value.get("id"))
            if kind and content:
                normalized_kind = kind.lower()
                identifier_kind = (
                    "PMCID"
                    if normalized_kind in {"pmc", "pmcid"}
                    else "PMID"
                    if normalized_kind in {"pubmed", "pmid"}
                    else kind.upper()
                )
                identifiers[identifier_kind] = content
        authors = raw.get("authors") if isinstance(raw.get("authors"), list) else []
        return LiteratureRecord(
            identifier,
            _text(raw.get("title")) or "Untitled",
            "pubmed",
            _authors(authors),
            year=_year(str(raw.get("pubdate", ""))[:4]),
            venue=_text(raw.get("fulljournalname") or raw.get("source")),
            doi=identifiers.get("DOI"),
            identifiers=identifiers,
            raw=raw,
        )

    async def _json(self, endpoint: str, params: dict[str, Any]) -> Any:
        await self.gate.wait()
        return await self.transport.json(
            "GET", f"{self.base_url}/{endpoint}", params=self._params(params)
        )

    async def search(self, request: SearchRequest) -> SearchResult:
        self.ensure_enabled()
        search = _object(
            await self._json(
                "esearch.fcgi",
                {
                    "term": request.query,
                    "retmax": min(request.limit, 100),
                    "retstart": int(request.cursor or "0"),
                },
            ),
            self.id,
        )
        result = _object(search.get("esearchresult"), self.id, "esearchresult")
        ids = [str(value) for value in _list(result.get("idlist"), self.id, "idlist")]
        if not ids:
            return SearchResult(self.id, [], int(result.get("count", 0)), None)
        summary = _object(await self._json("esummary.fcgi", {"id": ",".join(ids)}), self.id)
        values = _object(summary.get("result"), self.id, "result")
        items = [
            self._map(identifier, values[identifier]) for identifier in ids if identifier in values
        ]
        start = int(request.cursor or "0") + len(ids)
        total = int(result.get("count", len(items)))
        return SearchResult(
            self.id, items, total, str(start) if start < total else None, requests=2
        )

    async def get(self, identifier: str) -> LiteratureRecord:
        self.ensure_enabled()
        payload = _object(await self._json("esummary.fcgi", {"id": identifier}), self.id)
        values = _object(payload.get("result"), self.id, "result")
        if identifier not in values:
            raise OmniScholarError(
                "not_found", f"PubMed record {identifier} was not found", category="provider"
            )
        return self._map(identifier, values[identifier])

    async def graph(self, identifier: str, kind: str, *, limit: int = 20) -> SearchResult:
        if kind not in {"references", "citations"}:
            self.unsupported(f"literature.{kind}")
        linkname = "pubmed_pubmed_refs" if kind == "references" else "pubmed_pubmed_citedin"
        payload = _object(
            await self._json(
                "elink.fcgi",
                {"dbfrom": "pubmed", "db": "pubmed", "id": identifier, "linkname": linkname},
            ),
            self.id,
        )
        ids: list[str] = []
        for linkset in payload.get("linksets", []):
            for database in linkset.get("linksetdb", []):
                ids.extend(
                    str(link.get("id"))
                    for link in database.get("links", database.get("link", []))
                    if isinstance(link, dict)
                )
        return SearchResult(
            self.id,
            [
                LiteratureRecord(value, "Untitled", self.id, identifiers={"PMID": value})
                for value in ids[:limit]
            ],
        )

    @staticmethod
    def _pmc_xml(value: str, stage: str) -> Any:
        check = re.sub(r"^\s*<\?xml[^>]*\?>", "", value, count=1, flags=re.IGNORECASE)
        if "<!DOCTYPE" in check.upper() or "<?" in check:
            raise OmniScholarError(
                "provider_schema_mismatch",
                f"PMC {stage} XML contains a forbidden declaration",
                category="provider",
            )
        try:
            root = ET.fromstring(value)
        except (ET.ParseError, DefusedXmlException) as exc:
            raise OmniScholarError(
                "provider_schema_mismatch",
                f"PMC {stage} returned invalid XML",
                category="provider",
                cause=exc,
            ) from exc
        errors = [item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "error"]
        if errors:
            code = errors[0].attrib.get("code", "oai_error")
            raise OmniScholarError(
                "pmc_oai_error",
                f"PMC OAI-PMH returned {code}",
                category="provider",
            )
        return root

    async def fulltext(self, pmc_id: str, *, fetch: bool = False) -> dict[str, Any]:
        normalized = pmc_id.upper()
        if not re.fullmatch(r"PMC\d+", normalized):
            raise OmniScholarError(
                "invalid_identifier",
                "PMC full text requires an identifier such as PMC123456",
                category="validation",
            )
        numeric_id = normalized.removeprefix("PMC")
        oai_url = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
        oai_identifier = f"oai:pubmedcentral.nih.gov:{numeric_id}"
        await self.gate.wait()
        formats_xml = await self.transport.text(
            "GET",
            oai_url,
            params={"verb": "ListMetadataFormats", "identifier": oai_identifier},
        )
        formats_root = self._pmc_xml(formats_xml, "metadata formats")
        formats = {
            (item.text or "").strip()
            for item in formats_root.iter()
            if item.tag.rsplit("}", 1)[-1] == "metadataPrefix"
        }
        available = "pmc" in formats
        resolved: dict[str, Any] = {
            "provider": self.id,
            "id": normalized,
            "available": available,
            "downloaded": False,
            "licenseEvidence": "PMC OAI-PMH metadataPrefix=pmc" if available else None,
        }
        if not fetch:
            return resolved
        if not available:
            raise OmniScholarError(
                "entitlement_required",
                f"PMC record {normalized} is not available for permitted full-text retrieval",
                category="authorization",
            )
        await self.gate.wait()
        content = await self.transport.text(
            "GET",
            oai_url,
            params={
                "verb": "GetRecord",
                "identifier": oai_identifier,
                "metadataPrefix": "pmc",
            },
        )
        root = self._pmc_xml(content, "full text")
        license_values: list[str] = []
        for item in root.iter():
            if item.tag.rsplit("}", 1)[-1] not in {"license", "license-p", "rights"}:
                continue
            href = next((value for key, value in item.attrib.items() if key.endswith("href")), None)
            text = " ".join("".join(item.itertext()).split())
            if href:
                license_values.append(href)
            elif text:
                license_values.append(text)
        return {
            **resolved,
            "downloaded": True,
            "license": license_values[0] if license_values else None,
            "content": content,
            "contentType": "application/xml",
        }


class ArxivProvider(BaseProvider):
    id = "arxiv"
    capabilities = ("literature.search", "literature.lookup", "fulltext.resolve", "fulltext.fetch")
    base_url = "https://export.arxiv.org/api/query"

    def __init__(
        self, transport: LiteratureTransport, *, enabled: bool = True, gate: RateGate | None = None
    ) -> None:
        super().__init__(transport, enabled=enabled)
        self.gate = gate or RateGate(3.0)

    @staticmethod
    def _parse(xml: str) -> list[LiteratureRecord]:
        check = re.sub(r"^\s*<\?xml[^>]*\?>", "", xml, count=1, flags=re.IGNORECASE)
        if "<!DOCTYPE" in check.upper() or "<?" in check:
            raise OmniScholarError(
                "provider_schema_mismatch",
                "arXiv XML contains a forbidden declaration",
                category="provider",
            )
        try:
            root = ET.fromstring(xml)
        except (ET.ParseError, DefusedXmlException) as exc:
            raise OmniScholarError(
                "provider_schema_mismatch", "Invalid arXiv Atom XML", category="provider", cause=exc
            ) from exc
        atom = "{http://www.w3.org/2005/Atom}"
        records: list[LiteratureRecord] = []
        for entry in root.findall(f"{atom}entry"):
            identifier = (entry.findtext(f"{atom}id") or "unknown").strip()
            published = entry.findtext(f"{atom}published") or ""
            records.append(
                LiteratureRecord(
                    identifier,
                    " ".join((entry.findtext(f"{atom}title") or "Untitled").split()),
                    "arxiv",
                    [
                        Author((author.findtext(f"{atom}name") or "Unknown").strip())
                        for author in entry.findall(f"{atom}author")
                    ],
                    abstract=" ".join((entry.findtext(f"{atom}summary") or "").split()) or None,
                    year=_year(published[:4]),
                    url=identifier,
                    identifiers={"arXiv": identifier.rsplit("/abs/", 1)[-1]},
                )
            )
        return records

    async def _query(self, params: Mapping[str, Any]) -> list[LiteratureRecord]:
        await self.gate.wait()
        return self._parse(await self.transport.text("GET", self.base_url, params=params))

    async def search(self, request: SearchRequest) -> SearchResult:
        self.ensure_enabled()
        limit = min(request.limit, 2_000)
        start = (max(request.page or 1, 1) - 1) * limit
        if start + limit > 30_000:
            raise OmniScholarError(
                "pagination_limit",
                "arXiv query exceeds the 30,000-result API limit",
                category="limits",
            )
        items = await self._query(
            {"search_query": f"all:{request.query}", "start": start, "max_results": limit}
        )
        return SearchResult(
            self.id, items, next_cursor=str(start + len(items)) if len(items) == limit else None
        )

    async def get(self, identifier: str) -> LiteratureRecord:
        normalized = self._id(identifier)
        items = await self._query({"id_list": normalized, "start": 0, "max_results": 1})
        if not items:
            raise OmniScholarError(
                "not_found", f"arXiv record {normalized} was not found", category="provider"
            )
        return items[0]

    @staticmethod
    def _id(identifier: str) -> str:
        value = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", identifier, flags=re.IGNORECASE)
        value = re.sub(r"\.pdf$", "", value, flags=re.IGNORECASE)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-/]+(?:v\d+)?", value):
            raise OmniScholarError(
                "invalid_identifier", "Invalid arXiv identifier", category="validation"
            )
        return value

    async def fulltext(self, identifier: str, *, fetch: bool = False) -> dict[str, Any]:
        value = self._id(identifier)
        abstract_url = f"https://arxiv.org/abs/{value}"
        pdf_url = f"https://arxiv.org/pdf/{value}"
        result: dict[str, Any] = {
            "provider": self.id,
            "id": value,
            "abstractUrl": abstract_url,
            "pdfUrl": pdf_url,
            "original": True,
        }
        if fetch:
            await self.gate.wait()
            content = await self.transport.bytes(
                "GET", pdf_url, headers={"Accept": "application/pdf"}
            )
            if not content.startswith(b"%PDF-"):
                raise OmniScholarError(
                    "provider_schema_mismatch", "arXiv response is not a PDF", category="provider"
                )
            result["content"] = content
            result["contentType"] = "application/pdf"
        return result


class CrossrefProvider(BaseProvider):
    id = "crossref"
    capabilities = ("literature.search", "literature.lookup", "literature.references")
    base_url = "https://api.crossref.org/works"

    def __init__(
        self, transport: LiteratureTransport, *, email: str | None = None, enabled: bool = True
    ) -> None:
        super().__init__(transport, enabled=enabled)
        self.email = email

    def _headers(self) -> dict[str, str]:
        address = self.email or "noreply@example.invalid"
        return {"User-Agent": f"OmniScholar/0.1 (mailto:{address})"}

    @staticmethod
    def _map(raw_value: Any, fallback: str | None = None) -> LiteratureRecord:
        raw = _object(raw_value, "crossref", "work")
        doi = _text(raw.get("DOI")) or fallback
        title = raw.get("title")
        venue = raw.get("container-title")
        dates = (
            raw.get("published", {}).get("date-parts", [[]])
            if isinstance(raw.get("published"), dict)
            else [[]]
        )
        return LiteratureRecord(
            doi or "unknown",
            (_text(title[0]) or "Untitled") if isinstance(title, list) and title else "Untitled",
            "crossref",
            _authors(raw.get("author")),
            year=_year(dates[0][0] if dates and dates[0] else None),
            venue=_text(venue[0]) if isinstance(venue, list) and venue else None,
            doi=doi,
            url=_text(raw.get("URL")),
            identifiers={"DOI": doi} if doi else {},
            raw=raw,
        )

    async def search(self, request: SearchRequest) -> SearchResult:
        self.ensure_enabled()
        params: dict[str, Any] = {
            "query.bibliographic": request.query,
            "rows": min(request.limit, 1_000),
            "cursor": request.cursor or "*",
        }
        payload = _object(
            await self.transport.json("GET", self.base_url, params=params, headers=self._headers()),
            self.id,
        )
        message = _object(payload.get("message"), self.id, "message")
        items = [self._map(item) for item in _list(message.get("items"), self.id, "items")]
        return SearchResult(
            self.id, items, message.get("total-results"), _text(message.get("next-cursor"))
        )

    async def get(self, identifier: str) -> LiteratureRecord:
        doi = re.sub(r"^https?://doi\.org/", "", identifier, flags=re.IGNORECASE)
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            raise OmniScholarError(
                "invalid_identifier", "Crossref lookup requires a DOI", category="validation"
            )
        payload = _object(
            await self.transport.json(
                "GET", f"{self.base_url}/{quote(doi, safe='')}", headers=self._headers()
            ),
            self.id,
        )
        return self._map(payload.get("message"), doi)

    async def graph(
        self, identifier: str, kind: str, *, limit: int = 20, cursor: str | None = None
    ) -> SearchResult:
        if kind != "references":
            self.unsupported(f"literature.{kind}")
        item = await self.get(identifier)
        references = item.raw.get("reference", [])
        values = references if isinstance(references, list) else []
        start = int(cursor or "0")
        selected = values[start : start + min(limit, 1_000)]
        items = [
            self._map(value, _text(value.get("DOI")))
            for value in selected
            if isinstance(value, dict)
        ]
        next_cursor = str(start + len(selected)) if start + len(selected) < len(values) else None
        return SearchResult(self.id, items, len(values), next_cursor)


class UnpaywallProvider(BaseProvider):
    id = "unpaywall"
    capabilities = ("literature.search", "literature.lookup", "fulltext.resolve")
    base_url = "https://api.unpaywall.org/v2"

    def __init__(
        self, transport: LiteratureTransport, *, email: str | None, enabled: bool = True
    ) -> None:
        super().__init__(transport, enabled=enabled)
        self.email = email

    def _email(self) -> str:
        if not self.email:
            raise OmniScholarError(
                "contact_required", "Unpaywall requires a contact email", category="config"
            )
        return self.email

    @staticmethod
    def _map(raw_value: Any) -> LiteratureRecord:
        raw = _object(raw_value, "unpaywall", "work")
        doi = _text(raw.get("doi")) or "unknown"
        best = _mapping(raw.get("best_oa_location"))
        return LiteratureRecord(
            doi,
            _text(raw.get("title")) or "Untitled",
            "unpaywall",
            year=_year(raw.get("year")),
            venue=_text(raw.get("journal_name")),
            doi=doi,
            url=_text(raw.get("doi_url")),
            open_access_url=_text(
                best.get("url_for_pdf") or best.get("url_for_landing_page") or best.get("url")
            ),
            identifiers={"DOI": doi},
            license=_text(best.get("license")),
            raw=raw,
        )

    async def search(self, request: SearchRequest) -> SearchResult:
        self.ensure_enabled()
        page = min(max(request.page or 1, 1), 10_000)
        params: dict[str, Any] = {"query": request.query, "page": page, "email": self._email()}
        if request.open_access_only:
            params["is_oa"] = "true"
        payload = _object(
            await self.transport.json("GET", f"{self.base_url}/search", params=params), self.id
        )
        values = payload.get("results", payload.get("items", []))
        items = [self._map(item) for item in _list(values, self.id, "results")[:50]]
        total = payload.get("total") if isinstance(payload.get("total"), int) else None
        next_cursor = (
            str(page + 1) if len(items) == 50 and (total is None or page * 50 < total) else None
        )
        return SearchResult(self.id, items, total, next_cursor)

    async def get(self, identifier: str) -> LiteratureRecord:
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", identifier, flags=re.IGNORECASE)
        if not doi.startswith("10."):
            raise OmniScholarError(
                "invalid_identifier", "Unpaywall lookup requires a DOI", category="validation"
            )
        payload = await self.transport.json(
            "GET", f"{self.base_url}/{quote(doi, safe='')}", params={"email": self._email()}
        )
        return self._map(payload)

    async def fulltext(self, identifier: str) -> dict[str, Any]:
        item = await self.get(identifier)
        locations = item.raw.get("oa_locations", [])
        return {
            "provider": self.id,
            "id": item.id,
            "isOa": item.raw.get("is_oa") is True,
            "oaStatus": item.raw.get("oa_status"),
            "locations": locations if isinstance(locations, list) else [],
            "downloaded": False,
        }


class EasyScholarProvider(BaseProvider):
    id = "easyscholar"
    capabilities = ("journal.metrics",)
    endpoint = "https://www.easyscholar.cc/open/getPublicationRank"

    def __init__(
        self, transport: LiteratureTransport, *, api_key: str | None, enabled: bool = True
    ) -> None:
        super().__init__(transport, enabled=enabled)
        self.api_key = api_key

    @property
    def status(self) -> ProviderStatus:
        return ProviderStatus(
            self.id,
            self.enabled,
            self.capabilities,
            "configured" if self.api_key else "missing",
            "mock_passed",
            (DOCS[self.id],),
            ("Only the verified getPublicationRank endpoint is implemented.",),
        )

    async def search(self, request: SearchRequest) -> SearchResult:
        self.unsupported("literature.search")
        raise AssertionError(request)

    async def get(self, identifier: str) -> LiteratureRecord:
        self.unsupported("literature.lookup")
        raise AssertionError(identifier)

    async def metrics(self, publication_name: str) -> dict[str, Any]:
        self.ensure_enabled()
        if not self.api_key:
            raise OmniScholarError(
                "credential_required",
                "easyScholar credential is not configured",
                category="authentication",
            )
        payload = _object(
            await self.transport.json(
                "GET",
                self.endpoint,
                params={"secretKey": self.api_key, "publicationName": publication_name},
            ),
            self.id,
        )
        if payload.get("code") != 200:
            raise OmniScholarError(
                "provider_application_error",
                f"easyScholar returned application code {payload.get('code')}",
                category="provider",
            )
        return {
            "provider": self.id,
            "publicationName": publication_name,
            "data": payload.get("data", {}),
        }
