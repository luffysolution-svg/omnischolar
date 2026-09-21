from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

import httpx

from omnischolar.core import BoundedHttpClient, OmniScholarError
from omnischolar.providers.literature.models import SearchRequest
from omnischolar.providers.literature.providers import (
    ArxivProvider,
    CrossrefProvider,
    SemanticScholarProvider,
)


class FakeLiteratureTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None, dict | None, object]] = []

    async def json(self, method, url, *, params=None, headers=None, body=None):
        self.calls.append((method, url, params, headers, body))
        if "recommendations" in url:
            return {"recommendedPapers": [{"paperId": "recommended-1", "title": "Recommended"}]}
        if url.endswith("/paper/batch"):
            return [
                {
                    "paperId": "recommended-1",
                    "title": "Recommended",
                    "externalIds": {"DOI": "10.1000/example"},
                    "year": 2026,
                }
            ]
        if "/author/search" in url:
            return {"total": 1, "data": [{"authorId": "a1", "name": "Example Author"}]}
        return {"total": 0, "data": []}

    async def text(self, *args, **kwargs):
        return ""

    async def bytes(self, *args, **kwargs):
        return b""


class SemanticScholarProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_doi_alias_is_normalized_and_unknown_fields_are_rejected(self) -> None:
        transport = FakeLiteratureTransport()
        provider = SemanticScholarProvider(transport, api_key="key")

        await provider.search(SearchRequest("test", fields=("doi", "title")))
        self.assertEqual(transport.calls[0][2]["fields"], "externalIds,title")

        with self.assertRaises(OmniScholarError) as raised:
            await provider.search(SearchRequest("test", fields=("notAField",)))
        self.assertEqual(raised.exception.code, "invalid_provider_fields")

    async def test_recommendations_are_enriched_with_batch_metadata(self) -> None:
        transport = FakeLiteratureTransport()
        provider = SemanticScholarProvider(transport, api_key="key")

        result = await provider.graph("seed", "recommendations", limit=3)

        self.assertEqual(result.requests, 2)
        self.assertEqual(result.items[0].doi, "10.1000/example")
        self.assertTrue(transport.calls[1][1].endswith("/paper/batch"))

    async def test_author_search_uses_semantic_scholar_author_endpoint(self) -> None:
        transport = FakeLiteratureTransport()
        provider = SemanticScholarProvider(transport, api_key="key")

        result = await provider.author("search", query="Example Author", limit=5)

        self.assertEqual(result["data"][0]["authorId"], "a1")
        self.assertTrue(transport.calls[0][1].endswith("/author/search"))

    def test_retry_after_header_is_preserved_as_bounded_metadata(self) -> None:
        retry_at = (datetime.now(UTC) + timedelta(seconds=5)).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        error = BoundedHttpClient._http_error(
            httpx.Response(429, headers={"Retry-After": retry_at})
        )

        self.assertTrue(error.retryable)
        self.assertGreater(error.details["retryAfterSeconds"], 0)
        self.assertLessEqual(error.details["retryAfterSeconds"], 60)


class LiteratureHttpContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_arxiv_sends_atom_accept_and_contact_user_agent(self) -> None:
        class Transport(FakeLiteratureTransport):
            async def text(self, method, url, *, params=None, headers=None):
                self.calls.append((method, url, params, headers, None))
                return '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'

        transport = Transport()
        provider = ArxivProvider(transport)

        await provider.search(SearchRequest("solid state battery", limit=1))

        headers = transport.calls[0][3]
        self.assertEqual(headers["Accept"], "application/atom+xml")
        self.assertIn("mailto:", headers["User-Agent"])

    async def test_crossref_omits_wildcard_cursor_on_first_page(self) -> None:
        class Transport(FakeLiteratureTransport):
            async def json(self, method, url, *, params=None, headers=None, body=None):
                self.calls.append((method, url, params, headers, body))
                return {"message": {"items": [], "next-cursor": "next"}}

        transport = Transport()
        provider = CrossrefProvider(transport)

        await provider.search(SearchRequest("solid state battery", limit=1))
        await provider.search(SearchRequest("solid state battery", limit=1, cursor="next"))

        self.assertNotIn("cursor", transport.calls[0][2])
        self.assertEqual(transport.calls[1][2]["cursor"], "next")


if __name__ == "__main__":
    unittest.main()
