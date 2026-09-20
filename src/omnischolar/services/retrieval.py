"""Bounded local retrieval over managed Markdown publications."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omnischolar.core import OmniScholarError

from .reader import LiteratureReader
from .reading_context import ReadingContextStore


_TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]")


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(value)]


@dataclass(slots=True)
class IndexedChunk:
    zotero_key: str
    title: str
    doi: str | None
    markdown_path: str
    heading: str | None
    text: str
    start: int
    end: int
    line_start: int
    line_end: int
    paragraph_id: str
    context_before: str
    context_after: str


class LiteratureRetriever:
    """Use local BM25-style evidence retrieval and leave room for embeddings."""

    def __init__(
        self,
        reader: LiteratureReader,
        *,
        context_store: ReadingContextStore | None = None,
        max_chunks: int = 20_000,
    ) -> None:
        self.reader = reader
        self.context_store = context_store
        self.max_chunks = max(100, min(max_chunks, 100_000))
        self._manifest_revision: int | None = None
        self._chunks: list[IndexedChunk] = []
        self._document_count = 0

    async def _build_index(self) -> bool:
        manifest = await self.reader.sync.manifest()
        revision = int(manifest.get("revision", 0))
        if self._manifest_revision == revision:
            return True
        chunks: list[IndexedChunk] = []
        seen: set[str] = set()
        document_count = 0
        for publication_id, entry in manifest.get("entries", {}).items():
            if not isinstance(entry, dict) or entry.get("excluded"):
                continue
            parts = str(publication_id).rsplit(":", 2)
            if len(parts) != 3:
                continue
            key, attachment_key = parts[-2], parts[-1]
            if key in seen:
                continue
            try:
                source = await self.reader.source(key, attachment_key)
            except OmniScholarError:
                continue
            seen.add(key)
            document_count += 1
            records = LiteratureReader.paragraph_records(source["markdown"])
            for index, record in enumerate(records):
                if len(chunks) >= self.max_chunks:
                    break
                chunks.append(
                    IndexedChunk(
                        zotero_key=source["key"],
                        title=source["title"],
                        doi=source["paper"].get("doi"),
                        markdown_path=str(source["markdownPath"]),
                        heading=record["heading"],
                        text=record["text"],
                        start=record["start"],
                        end=record["end"],
                        line_start=record["lineStart"],
                        line_end=record["lineEnd"],
                        paragraph_id=f"p-{record['start']}",
                        context_before=records[index - 1]["text"][:800] if index else "",
                        context_after=records[index + 1]["text"][:800]
                        if index + 1 < len(records)
                        else "",
                    )
                )
        self._chunks = chunks
        self._document_count = document_count
        self._manifest_revision = revision
        return False

    @staticmethod
    def _score(query: list[str], chunk: IndexedChunk, document_frequency: dict[str, int], total: int) -> float:
        values = _tokens(f"{chunk.title} {chunk.heading or ''} {chunk.text}")
        if not values:
            return 0.0
        frequencies: dict[str, int] = {}
        for token in values:
            frequencies[token] = frequencies.get(token, 0) + 1
        average = max(1.0, len(values))
        score = 0.0
        for term in set(query):
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (total + 1) / (document_frequency.get(term, 0) + 1))
            score += idf * (frequency * 2.2) / (frequency + 1.2 * (0.7 + 0.3 * len(values) / average))
        lowered = chunk.text.casefold()
        phrase = " ".join(query)
        if phrase and phrase in lowered:
            score += 1.5
        heading = (chunk.heading or "").casefold()
        score += sum(1.5 for term in set(query) if term in heading)
        if chunk.title and all(term in chunk.title.casefold() for term in set(query)):
            score += 1.0
        return score

    @staticmethod
    def _tfidf_score(
        query: list[str], chunk: IndexedChunk, document_frequency: dict[str, int], total: int
    ) -> float:
        query_frequency: dict[str, int] = {}
        for term in query:
            query_frequency[term] = query_frequency.get(term, 0) + 1
        document_frequency_in_chunk: dict[str, int] = {}
        for term in _tokens(f"{chunk.title} {chunk.heading or ''} {chunk.text}"):
            document_frequency_in_chunk[term] = document_frequency_in_chunk.get(term, 0) + 1
        query_vector: dict[str, float] = {}
        document_vector: dict[str, float] = {}
        for term, frequency in query_frequency.items():
            idf = math.log(1 + (total + 1) / (document_frequency.get(term, 0) + 1))
            query_vector[term] = (1 + math.log(frequency)) * idf
            if term in document_frequency_in_chunk:
                document_vector[term] = (1 + math.log(document_frequency_in_chunk[term])) * idf
        query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
        document_norm = math.sqrt(sum(value * value for value in document_vector.values()))
        if not query_norm or not document_norm:
            return 0.0
        return sum(
            query_vector[term] * document_vector.get(term, 0.0) for term in query_vector
        ) / (query_norm * document_norm)

    @staticmethod
    def _excerpt(text: str, query: str, max_chars: int) -> str:
        value = text.strip()
        if len(value) <= max_chars:
            return value
        terms = _tokens(query)
        lowered = value.casefold()
        positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
        center = positions[0] if positions else 0
        start = max(0, min(center - max_chars // 3, len(value) - max_chars))
        return value[start : start + max_chars]

    async def search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise OmniScholarError(
                "query_required", "Focused literature search requires a query", category="validation"
            )
        query_terms = _tokens(query)
        if not query_terms:
            raise OmniScholarError(
                "query_empty", "Focused literature search could not tokenize the query", category="validation"
            )
        cache_hit = await self._build_index()
        keys = {str(key) for key in arguments.get("keys", [])}
        section = str(arguments.get("section", "")).casefold().strip()
        top_k = max(1, min(int(arguments.get("topK", 8)), 50))
        max_chars = max(500, min(int(arguments.get("maxChars", 2_000)), 8_000))
        max_per_document = max(1, min(int(arguments.get("maxPerDocument", 3)), 10))
        include_context = bool(arguments.get("includeContext", False))
        selected = [
            chunk
            for chunk in self._chunks
            if (not keys or chunk.zotero_key in keys)
            and (not section or section in (chunk.heading or "").casefold())
        ]
        document_frequency: dict[str, int] = {}
        for chunk in selected:
            for term in set(_tokens(f"{chunk.title} {chunk.heading or ''} {chunk.text}")):
                document_frequency[term] = document_frequency.get(term, 0) + 1
        ranked = [
            (
                self._score(query_terms, chunk, document_frequency, len(selected))
                + 0.5 * self._tfidf_score(query_terms, chunk, document_frequency, len(selected)),
                chunk,
            )
            for chunk in selected
        ]
        ranked = [(score, chunk) for score, chunk in ranked if score > 0]
        ranked.sort(key=lambda pair: (-pair[0], pair[1].zotero_key, pair[1].start))
        results: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        for score, chunk in ranked:
            if counts.get(chunk.zotero_key, 0) >= max_per_document:
                continue
            counts[chunk.zotero_key] = counts.get(chunk.zotero_key, 0) + 1
            result = {
                "zoteroKey": chunk.zotero_key,
                "title": chunk.title,
                "doi": chunk.doi,
                "heading": chunk.heading,
                "paragraphId": chunk.paragraph_id,
                "locator": f"{Path(chunk.markdown_path).name}#L{chunk.line_start}-L{chunk.line_end}",
                "start": chunk.start,
                "end": chunk.end,
                "score": round(score, 4),
                "excerpt": self._excerpt(chunk.text, query, max_chars),
                "markdownPath": chunk.markdown_path,
            }
            if include_context:
                result["contextBefore"] = chunk.context_before
                result["contextAfter"] = chunk.context_after
            results.append(result)
            if len(results) >= top_k:
                break
        response: dict[str, Any] = {
            "query": query,
            "strategy": "hybrid-bm25-tfidf",
            "semantic": False,
            "vectorBackend": "tfidf-local",
            "cacheHit": cache_hit,
            "indexedDocuments": self._document_count,
            "indexedChunks": len(self._chunks),
            "candidateChunks": len(selected),
            "results": results,
        }
        context_id = arguments.get("contextId")
        if context_id and self.context_store:
            items = [
                {
                    "text": result["excerpt"],
                    "source": {
                        key: result[key]
                        for key in ("zoteroKey", "title", "heading", "locator", "markdownPath")
                        if result.get(key) is not None
                    },
                }
                for result in results
            ]
            response["context"] = await self.context_store.add_items(
                str(context_id), items, title=f"Focused search: {query[:100]}"
            )
        return response
