"""Bounded Ai4Scholar operation service shared by every tool and host."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from omnischolar.core import OmniScholarError, ToolExecutionContext, redact

from .artifacts import save_image_payload
from .transport import ServiceTransport

_DEFAULT_PAPER_FIELDS = (
    "paperId,title,abstract,authors,year,venue,citationCount,externalIds,url,openAccessPdf"
)
_DEFAULT_AUTHOR_FIELDS = "authorId,name,affiliations,homepage,paperCount,citationCount,hIndex"


def _encode_id(value: str) -> str:
    prefix, separator, identifier = value.partition(":")
    if separator:
        return f"{quote(prefix, safe='')}:{quote(identifier, safe='')}"
    return quote(value, safe="")


class Ai4ScholarService:
    def __init__(
        self,
        transport: ServiceTransport,
        *,
        api_key: str,
        base_url: str = "https://ai4scholar.net",
        allow_paid: bool = False,
        timeout_seconds: float = 60,
        figure_timeout_seconds: float = 300,
        max_response_bytes: int = 16 * 1024 * 1024,
        output_root: Path = Path("."),
        max_artifact_bytes: int = 50 * 1024 * 1024,
        artifact_timeout_seconds: float = 120,
    ) -> None:
        if not api_key:
            raise OmniScholarError(
                "credential_required",
                "Ai4Scholar credential is not configured",
                category="authentication",
            )
        self.transport = transport
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.allow_paid = allow_paid
        self.timeout_seconds = timeout_seconds
        self.figure_timeout_seconds = figure_timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.output_root = output_root
        self.max_artifact_bytes = max_artifact_bytes
        self.artifact_timeout_seconds = artifact_timeout_seconds

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    def _authorize(
        self, context: ToolExecutionContext, operation: str, *, free: bool = False
    ) -> None:
        if free:
            return
        if not self.allow_paid:
            raise OmniScholarError(
                "paid_disabled",
                f"Ai4Scholar {operation} is disabled by configuration",
                category="authorization",
            )
        context.require_paid(f"Ai4Scholar {operation}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        context: ToolExecutionContext,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        free: bool = False,
        timeout_seconds: float | None = None,
    ) -> Any:
        self._authorize(context, path, free=free)
        value = await self.transport.json(
            method,
            f"{self.base_url}{path}",
            params=params,
            headers=self.headers,
            body=body,
            timeout_seconds=timeout_seconds or self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
        )
        return redact(value, (self.api_key,))

    async def request_sse(
        self, path: str, *, context: ToolExecutionContext, body: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Parse a bounded SSE response without persisting unbounded provider output."""
        self._authorize(context, path)
        text = await self.transport.text(
            "POST",
            f"{self.base_url}{path}",
            headers={**self.headers, "Accept": "text/event-stream"},
            body=body,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
        )
        events: list[dict[str, Any]] = []
        for block in re.split(r"\r?\n\r?\n", text):
            data = "\n".join(
                line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")
            )
            if not data or data == "[DONE]":
                continue
            events.append({"data": redact(data, (self.api_key,))})
        return events

    async def search(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        source = args["source"]
        if source == "semantic_scholar":
            mode = args.get("semanticMode", "relevance")
            path = {
                "bulk": "/graph/v1/paper/search/bulk",
                "match": "/graph/v1/paper/search/match",
                "autocomplete": "/graph/v1/paper/autocomplete",
            }.get(mode, "/graph/v1/paper/search")
            if mode == "autocomplete":
                params = {"query": args["query"]}
            else:
                params = {
                    key: value
                    for key, value in {
                        "query": args["query"],
                        "fields": args.get("fields", _DEFAULT_PAPER_FIELDS),
                        "limit": args.get("limit", 10) if mode == "relevance" else None,
                        "offset": args.get("offset") if mode == "relevance" else None,
                        "token": args.get("token") if mode == "bulk" else None,
                        "sort": args.get("sort") if mode == "bulk" else None,
                        "publicationTypes": args.get("publicationTypes"),
                        "publicationDateOrYear": args.get("publicationDateOrYear"),
                        "year": f"{args.get('yearFrom', '')}-{args.get('yearTo', '')}"
                        if args.get("yearFrom") or args.get("yearTo")
                        else None,
                        "openAccessPdf": True if args.get("openAccessOnly") else None,
                        "minCitationCount": args.get("minCitationCount"),
                        "venue": args.get("venue"),
                        "fieldsOfStudy": args.get("fieldsOfStudy"),
                    }.items()
                    if value is not None
                }
            return await self._request("GET", path, context=context, params=params)
        if source == "pubmed":
            body = {
                key: value
                for key, value in {
                    "query": args["query"],
                    "limit": args.get("limit", 10),
                    "offset": args.get("offset"),
                    "sort": args.get("sort", "relevance"),
                    "minDate": args.get("minDate"),
                    "maxDate": args.get("maxDate"),
                }.items()
                if value is not None
            }
            return await self._request(
                "POST", "/pubmed/v1/paper/search", context=context, body=body
            )
        if source == "google_scholar":
            body = {
                key: value
                for key, value in {
                    "query": args["query"],
                    "page": args.get("page", 1),
                    "results": args.get("limit", 10),
                    "language": args.get("language"),
                    "yearFrom": args.get("yearFrom"),
                    "yearTo": args.get("yearTo"),
                    "reviewOnly": args.get("reviewOnly"),
                    "sortByDate": args.get("sortByDate"),
                    "cites": args.get("cites"),
                    "cluster": args.get("cluster"),
                }.items()
                if value is not None
            }
            return await self._request(
                "POST", "/google-scholar/v1/search", context=context, body=body
            )
        if source == "google_patents":
            body = {
                key: value
                for key, value in {
                    "query": args["query"],
                    "page": args.get("page", 1),
                    "num": args.get("limit", 10),
                    "sort": args.get("sort"),
                    "status": args.get("status"),
                    "type": args.get("patentType"),
                    "country": args.get("country"),
                    "language": args.get("language"),
                    "inventor": args.get("inventor"),
                    "assignee": args.get("assignee"),
                    "before": args.get("before"),
                    "after": args.get("after"),
                }.items()
                if value is not None
            }
            return await self._request(
                "POST", "/google-scholar/v1/patents", context=context, body=body
            )
        raise OmniScholarError(
            "invalid_source", "Unknown Ai4Scholar search source", category="validation"
        )

    async def paper(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        source, action, identifier = args["source"], args["action"], _encode_id(args["id"])
        if source == "semantic_scholar":
            if action == "related":
                raise OmniScholarError(
                    "unsupported_capability",
                    "Semantic Scholar uses recommendations rather than related",
                    category="capability",
                )
            if action == "recommendations":
                return await self._request(
                    "GET",
                    f"/recommendations/v1/papers/forpaper/{identifier}",
                    context=context,
                    params={
                        "from": args.get("recommendationPool", "recent"),
                        "limit": min(args.get("limit", 20), 500),
                        "fields": args.get("fields", _DEFAULT_PAPER_FIELDS),
                    },
                )
            suffix = "" if action == "detail" else f"/{action}"
            return await self._request(
                "GET",
                f"/graph/v1/paper/{identifier}{suffix}",
                context=context,
                params={
                    "fields": args.get(
                        "fields",
                        _DEFAULT_AUTHOR_FIELDS if action == "authors" else _DEFAULT_PAPER_FIELDS,
                    ),
                    "limit": None if action == "detail" else args.get("limit", 20),
                    "offset": None if action == "detail" else args.get("offset"),
                    "publicationDateOrYear": (
                        args.get("publicationDateOrYear") if action == "citations" else None
                    ),
                },
            )
        if source == "pubmed" and action in {"detail", "citations", "related"}:
            suffix = "" if action == "detail" else f"/{action}"
            return await self._request(
                "GET",
                f"/pubmed/v1/paper/{identifier}{suffix}",
                context=context,
                params=None if action == "detail" else {"limit": args.get("limit", 20)},
            )
        raise OmniScholarError(
            "unsupported_capability",
            "Unsupported Ai4Scholar paper operation",
            category="capability",
        )

    async def author(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        source, action = args["source"], args["action"]
        if action == "search" and not args.get("query"):
            raise OmniScholarError(
                "query_required", "Author search requires query", category="validation"
            )
        if action != "search" and not args.get("authorId"):
            raise OmniScholarError(
                "author_id_required", f"Author {action} requires authorId", category="validation"
            )
        if source == "semantic_scholar":
            if action == "search":
                path = "/graph/v1/author/search"
            else:
                path = f"/graph/v1/author/{_encode_id(args['authorId'])}{'/papers' if action == 'papers' else ''}"
            return await self._request(
                "GET",
                path,
                context=context,
                params={
                    "query": args.get("query"),
                    "fields": args.get(
                        "fields",
                        _DEFAULT_PAPER_FIELDS if action == "papers" else _DEFAULT_AUTHOR_FIELDS,
                    ),
                    "limit": None if action == "detail" else args.get("limit", 20),
                    "offset": None if action == "detail" else args.get("offset"),
                    "publicationDateOrYear": (
                        args.get("publicationDateOrYear") if action == "papers" else None
                    ),
                },
            )
        if source == "google_scholar" and action in {"search", "detail"}:
            path = (
                "/google-scholar/v1/profiles" if action == "search" else "/google-scholar/v1/author"
            )
            body = (
                {"authorName": args.get("query"), "afterAuthor": args.get("afterAuthor")}
                if action == "search"
                else {"authorId": args.get("authorId"), "sort": args.get("sort")}
            )
            return await self._request(
                "POST",
                path,
                context=context,
                body={key: value for key, value in body.items() if value is not None},
            )
        raise OmniScholarError(
            "unsupported_capability",
            "Unsupported Ai4Scholar author operation",
            category="capability",
        )

    async def batch(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        source = args["source"]
        maximum = {"semantic_papers": 500, "semantic_authors": 1_000, "pubmed_papers": 100}[source]
        if len(args["ids"]) > maximum:
            raise OmniScholarError(
                "batch_limit", f"{source} accepts at most {maximum} IDs", category="limits"
            )
        path = {
            "semantic_papers": "/graph/v1/paper/batch",
            "semantic_authors": "/graph/v1/author/batch",
            "pubmed_papers": "/pubmed/v1/paper/batch",
        }[source]
        return await self._request(
            "POST",
            path,
            context=context,
            params={"fields": args.get("fields", _DEFAULT_PAPER_FIELDS)}
            if source != "pubmed_papers"
            else None,
            body={"ids": args["ids"]},
        )

    async def recommend(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        return await self._request(
            "POST",
            "/recommendations/v1/papers",
            context=context,
            params={
                "limit": min(args.get("limit", 20), 500),
                "fields": args.get("fields", _DEFAULT_PAPER_FIELDS),
            },
            body={
                "positivePaperIds": args["positivePaperIds"],
                "negativePaperIds": args.get("negativePaperIds", []),
            },
        )

    async def cite(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        return await self._request(
            "POST",
            "/google-scholar/v1/cite",
            context=context,
            body={"paperId": args["paperId"], "language": args.get("language", "en")},
        )

    async def snippets(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        return await self._request(
            "GET",
            "/graph/v1/snippet/search",
            context=context,
            params={**args, "limit": min(args.get("limit", 10), 1_000)},
        )

    async def credits(self, context: ToolExecutionContext) -> Any:
        return await self._request("GET", "/api/credits", context=context, free=True)

    async def dataset(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        action = args["action"]
        required = {
            "release_detail": ("releaseId",),
            "dataset_download": ("releaseId", "datasetName"),
            "diffs": ("startReleaseId", "endReleaseId", "datasetName"),
        }.get(action, ())
        missing = [field for field in required if not args.get(field)]
        if missing:
            raise OmniScholarError(
                "dataset_arguments_required",
                f"Dataset {action} requires {', '.join(missing)}",
                category="validation",
            )
        if action == "list_releases":
            path = "/datasets/v1/release"
        elif action == "release_detail":
            path = f"/datasets/v1/release/{quote(args['releaseId'], safe='')}"
        elif action == "dataset_download":
            path = f"/datasets/v1/release/{quote(args['releaseId'], safe='')}/dataset/{quote(args['datasetName'], safe='')}"
        else:
            path = f"/datasets/v1/diffs/{quote(args['startReleaseId'], safe='')}/to/{quote(args['endReleaseId'], safe='')}/{quote(args['datasetName'], safe='')}"
        return await self._request("GET", path, context=context)

    async def journal(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        action = args["action"]
        if action == "search":
            params = {
                key: value
                for key, value in {
                    "query": args.get("query"),
                    "category": args.get("category"),
                    "jcr_quartile": args.get("jcrQuartile"),
                    "cas_quartile": args.get("casQuartile"),
                    "min_if": args.get("minImpactFactor"),
                    "max_if": args.get("maxImpactFactor"),
                    "is_oa": args.get("isOpenAccess"),
                    "sort": args.get("sort"),
                    "limit": args.get("limit", 20),
                    "offset": args.get("offset"),
                    "fields": args.get("fieldGroup"),
                }.items()
                if value is not None
            }
            return await self._request("GET", "/jcr/v1/journals", context=context, params=params)
        if action == "detail":
            return await self._request(
                "GET",
                f"/jcr/v1/journals/{quote(args['id'], safe='')}",
                context=context,
                params={"fields": args.get("fieldGroup", "all")},
            )
        if action == "categories":
            return await self._request(
                "GET",
                "/jcr/v1/categories",
                context=context,
                params={"sort": args.get("sort"), "limit": args.get("limit", 0)},
            )
        if not args.get("title"):
            raise OmniScholarError(
                "title_required", "Journal recommend requires title", category="validation"
            )
        raw_filters = args.get("filters")
        filters = dict(raw_filters) if isinstance(raw_filters, dict) else {}
        filters.update(
            {
                key: value
                for key, value in {
                    "min_impact_factor": args.get("minImpactFactor"),
                    "max_impact_factor": args.get("maxImpactFactor"),
                    "jcr_quartiles": (
                        [item.strip() for item in args["jcrQuartile"].split(",") if item.strip()]
                        if isinstance(args.get("jcrQuartile"), str)
                        else None
                    ),
                    "cas_quartiles": (
                        [item.strip() for item in args["casQuartile"].split(",") if item.strip()]
                        if isinstance(args.get("casQuartile"), str)
                        else None
                    ),
                    "is_oa": args.get("isOpenAccess"),
                    "categories": args.get("categories"),
                }.items()
                if value is not None
            }
        )
        body = {
            key: value
            for key, value in {
                "title": args["title"],
                "abstract": args.get("abstract"),
                "top_n": args.get("topN", 10),
                "filters": filters,
                "fields": args.get("fields"),
            }.items()
            if value is not None
        }
        return await self._request("POST", "/jrec/v1/recommend", context=context, body=body)

    async def citation_candidates(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        text = args["text"]
        mode = args.get("mode", "markers" if "[CITE]" in text else "statements")
        claims = (
            text.split("[CITE]")[:-1]
            if mode == "markers"
            else re.split(r"(?<=[.!?。！？])\s*", text)
        )
        claims = [claim.strip()[-500:] for claim in claims if len(claim.strip()) >= 20][
            : args.get("maxClaims", 5)
        ]
        if not claims:
            raise OmniScholarError(
                "no_claims", "No citation claims were found", category="validation"
            )
        matches = []
        for index, claim in enumerate(claims):
            await context.progress(index, len(claims), "searching citation candidates")
            result = await self._request(
                "GET",
                "/graph/v1/paper/search",
                context=context,
                params={
                    "query": claim,
                    "fields": _DEFAULT_PAPER_FIELDS,
                    "limit": min(args.get("candidatesPerClaim", 3), 5),
                    "year": args.get("year"),
                    "fieldsOfStudy": args.get("fieldsOfStudy"),
                },
            )
            matches.append(
                {
                    "claim": claim,
                    "candidates": result.get("data", []) if isinstance(result, dict) else [],
                }
            )
        return {
            "mode": mode,
            "reviewRequired": True,
            "matches": matches,
            "citationStyle": args.get("citationStyle", "apa"),
        }

    async def figure(self, args: dict[str, Any], context: ToolExecutionContext) -> Any:
        if args.get("images"):
            context.require_external_upload("Ai4Scholar Figure")
        body = {
            key: value
            for key, value in {
                "action": args["action"],
                "prompt": args.get("prompt"),
                "model": args.get("model", "flash"),
                "imageSize": args.get("imageSize", "2K"),
                "aspectRatio": args.get("aspectRatio", "1:1"),
                "images": args.get("images"),
                "stylePreset": args.get("stylePreset"),
                "lang": args.get("lang", "en"),
                "vectorizeMode": args.get("vectorizeMode", "fast"),
            }.items()
            if value is not None
        }
        result = await self._request(
            "POST",
            "/api/proxy/nano/generate",
            context=context,
            body=body,
            timeout_seconds=self.figure_timeout_seconds,
        )
        action = str(args["action"])
        if action not in {"critic", "vectorize"}:
            saved = await save_image_payload(
                self.transport,
                result,
                output_root=self.output_root,
                directory="ai4scholar-images",
                name_prefix="ai4scholar",
                max_bytes=self.max_artifact_bytes,
                timeout_seconds=self.artifact_timeout_seconds,
            )
            result = saved.sanitized_payload
            if isinstance(result, dict):
                result["localArtifacts"] = saved.artifacts
        if isinstance(result, dict):
            result["scientificIntegrityWarning"] = (
                "AI-generated figures are illustrative drafts, not experimental results or measured data."
            )
        return result
