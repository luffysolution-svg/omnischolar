"""Bounded, mode-aware reading of locally published literature."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from omnischolar.core import OmniScholarError, confined_path, read_file_bounded

from .sync import SyncService
from .zotero import validate_zotero_key

_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
_BLOCK_FORMULA = re.compile(r"(?s)(\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\))")
_CAPTION = re.compile(r"(?i)^\s*(?:figure|fig\.?|table)\s*\d*\s*[:.]?")


class LiteratureReader:
    """Read managed Markdown without returning an unbounded document."""

    def __init__(
        self,
        sync: SyncService,
        *,
        context_store: Any | None = None,
        max_document_bytes: int = 32 * 1024 * 1024,
    ) -> None:
        self.sync = sync
        self.context_store = context_store
        self.max_document_bytes = max_document_bytes

    async def read(self, arguments: dict[str, Any]) -> dict[str, Any]:
        mode = arguments["mode"]
        keys = list(arguments.get("keys") or [])
        if arguments.get("key"):
            keys.insert(0, arguments["key"])
        keys = list(dict.fromkeys(keys))
        if mode in {"compare", "review"}:
            if not keys:
                raise OmniScholarError(
                    "keys_required", f"Reading mode {mode} requires one or more Zotero keys", category="validation"
                )
            if len(keys) > 8:
                raise OmniScholarError(
                    "too_many_keys", "Reading modes accept at most 8 Zotero keys", category="limits"
                )
            return await self._multi(keys, mode, arguments)
        if len(keys) != 1:
            raise OmniScholarError(
                "key_required", f"Reading mode {mode} requires exactly one Zotero key", category="validation"
            )
        source = await self._source(keys[0], arguments.get("attachmentKey"))
        text = source["markdown"]
        scoped = self._section(text, arguments.get("section"))
        common = {
            "zoteroKey": source["key"],
            "title": source["title"],
            "mode": mode,
            "markdownPath": str(source["markdownPath"]),
        }
        if mode == "full":
            result = {**common, **self._chunk(scoped, arguments.get("cursor", 0), arguments.get("maxChars", 8000))}
        elif mode == "paragraphs":
            result = {**common, "items": self._paragraphs(scoped, arguments.get("query"), arguments.get("maxItems", 20))}
        elif mode == "formulas":
            result = {**common, "items": self._formulas(scoped, arguments.get("maxItems", 20))}
        elif mode == "figures":
            result = {**common, "items": self._figures(scoped, source["directory"], arguments.get("maxItems", 20))}
        else:
            raise OmniScholarError(
                "invalid_reading_mode", f"Unsupported reading mode: {mode}", category="validation"
            )
        return await self._cache_result(result, arguments)

    async def source(self, key: str, attachment_key: str | None = None) -> dict[str, Any]:
        """Return a local publication source for bounded internal workflows."""
        return await self._source(key, attachment_key)

    async def locate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        key = arguments.get("key")
        if not isinstance(key, str):
            raise OmniScholarError(
                "key_required", "Paragraph location requires one Zotero key", category="validation"
            )
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise OmniScholarError(
                "query_required", "Paragraph location requires a query", category="validation"
            )
        source = await self._source(key, arguments.get("attachmentKey"))
        records = self.paragraph_records(source["markdown"], arguments.get("section"))
        lowered_query = query.casefold()
        terms = [term.casefold() for term in re.findall(r"[A-Za-z0-9_]+|[\u3400-\u9fff]", query)]
        mode = arguments.get("matchMode", "allTerms")
        max_items = max(1, min(int(arguments.get("maxItems", 20)), 50))
        max_chars = max(500, min(int(arguments.get("maxChars", 4_000)), 8_000))
        matches: list[dict[str, Any]] = []
        for record in records:
            value = record["text"]
            lowered = value.casefold()
            exact = lowered_query in lowered
            all_terms = bool(terms) and all(term in lowered for term in terms)
            if (mode == "phrase" and not exact) or (mode == "allTerms" and not all_terms):
                continue
            if mode not in {"phrase", "allTerms"}:
                raise OmniScholarError(
                    "invalid_match_mode", f"Unsupported paragraph match mode: {mode}", category="validation"
                )
            score = 2.0 if exact else 1.0
            score += sum(1.0 for term in set(terms) if term in lowered)
            matches.append(
                {
                    "zoteroKey": source["key"],
                    "title": source["title"],
                    "heading": record["heading"],
                    "paragraphId": f"p-{record['start']}",
                    "start": record["start"],
                    "end": record["end"],
                    "lineStart": record["lineStart"],
                    "lineEnd": record["lineEnd"],
                    "locator": f"{source['markdownPath'].name}#L{record['lineStart']}-L{record['lineEnd']}",
                    "score": score,
                    "text": value[:max_chars],
                    "markdownPath": str(source["markdownPath"]),
                }
            )
            if len(matches) >= max_items:
                break
        result = {
            "zoteroKey": source["key"],
            "title": source["title"],
            "query": query,
            "matchMode": mode,
            "items": matches,
            "markdownPath": str(source["markdownPath"]),
        }
        return await self._cache_result(result, arguments)

    async def _source(self, key: str, attachment_key: str | None) -> dict[str, Any]:
        parent_key = validate_zotero_key(key)
        if attachment_key:
            validate_zotero_key(attachment_key, "Attachment key")
        manifest = await self.sync.manifest()
        candidates: list[dict[str, Any]] = []
        for publication_id, entry in manifest["entries"].items():
            if f":{parent_key}:" not in publication_id:
                continue
            candidate_attachment = publication_id.rsplit(":", 1)[-1]
            if attachment_key and candidate_attachment != attachment_key:
                continue
            relative = entry.get("relativePath")
            if not isinstance(relative, str):
                continue
            directory = confined_path(self.sync.root, relative, must_exist=True)
            metadata_path = confined_path(directory, "metadata.json", must_exist=True)
            metadata = json.loads(
                (await read_file_bounded(metadata_path, self.max_document_bytes)).decode("utf-8")
            )
            paper = metadata.get("zotero") if isinstance(metadata, dict) else None
            if not isinstance(paper, dict) or paper.get("zoteroKey") != parent_key:
                continue
            baseline = entry.get("baseline", {})
            markdown_names = [name for name in baseline if str(name).lower().endswith(".md")]
            if not markdown_names:
                raise OmniScholarError(
                    "publication_markdown_missing",
                    "Managed publication has no Markdown artifact",
                    category="filesystem",
                )
            markdown_path = confined_path(directory, markdown_names[0], must_exist=True)
            markdown = (
                await read_file_bounded(markdown_path, self.max_document_bytes)
            ).decode("utf-8", errors="replace")
            candidates.append(
                {
                    "key": parent_key,
                    "title": str(paper.get("title") or "Untitled"),
                    "paper": paper,
                    "directory": directory,
                    "markdownPath": markdown_path,
                    "markdown": markdown,
                    "attachmentKey": candidate_attachment,
                }
            )
        if not candidates:
            raise OmniScholarError(
                "publication_not_found",
                "No managed parsed publication exists for the Zotero item",
                category="filesystem",
            )
        if len(candidates) > 1 and not attachment_key:
            raise OmniScholarError(
                "publication_ambiguous",
                "Multiple parsed attachments exist; provide attachmentKey",
                category="validation",
                details={"attachments": [item["attachmentKey"] for item in candidates]},
            )
        return candidates[0]

    @staticmethod
    def _section_bounds(text: str, section: str | None) -> tuple[int, int]:
        if not section:
            return 0, len(text)
        headings = list(_HEADING.finditer(text))
        wanted = section.casefold()
        for index, match in enumerate(headings):
            title = match.group(2).strip()
            if wanted not in title.casefold():
                continue
            level = len(match.group(1))
            end = len(text)
            for next_heading in headings[index + 1 :]:
                if len(next_heading.group(1)) <= level:
                    end = next_heading.start()
                    break
            return match.start(), end
        raise OmniScholarError(
            "section_not_found", f"No heading matched section: {section}", category="validation"
        )

    @classmethod
    def _section(cls, text: str, section: str | None) -> str:
        start, end = cls._section_bounds(text, section)
        return text[start:end].strip()

    @classmethod
    def paragraph_records(cls, text: str, section: str | None = None) -> list[dict[str, Any]]:
        start, end = cls._section_bounds(text, section)
        scoped = text[start:end]
        headings = list(_HEADING.finditer(scoped))
        records: list[dict[str, Any]] = []
        for match in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", scoped):
            value = match.group(0).strip()
            if not value or value.startswith("#"):
                continue
            heading_match = [heading for heading in headings if heading.start() <= match.start()]
            absolute_start = start + match.start()
            absolute_end = start + match.end()
            records.append(
                {
                    "text": value,
                    "heading": heading_match[-1].group(2).strip() if heading_match else None,
                    "start": absolute_start,
                    "end": absolute_end,
                    "lineStart": text.count("\n", 0, absolute_start) + 1,
                    "lineEnd": text.count("\n", 0, absolute_end) + 1,
                }
            )
        return records

    @staticmethod
    def _chunk(text: str, cursor: int, max_chars: int) -> dict[str, Any]:
        start = max(0, min(int(cursor), len(text)))
        size = max(500, min(int(max_chars), 12_000))
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n\n", start, end), text.rfind("\n", start, end))
            if boundary > start + size // 2:
                end = boundary
        return {
            "cursor": start,
            "nextCursor": end if end < len(text) else None,
            "hasMore": end < len(text),
            "totalChars": len(text),
            "text": text[start:end].strip(),
        }

    @classmethod
    def _paragraphs(cls, text: str, query: str | None, max_items: int) -> list[dict[str, Any]]:
        wanted = (query or "").casefold().strip()
        terms = [
            term.casefold()
            for term in re.findall(r"[A-Za-z0-9_]+|[\u3400-\u9fff]", wanted)
        ]
        items: list[dict[str, Any]] = []
        for record in cls.paragraph_records(text):
            value = record["text"]
            lowered = value.casefold()
            if wanted and wanted not in lowered and not all(term in lowered for term in terms):
                continue
            items.append(
                {
                    "text": value[:4000],
                    "heading": record["heading"],
                    "paragraphId": f"p-{record['start']}",
                    "start": record["start"],
                    "end": record["end"],
                    "lineStart": record["lineStart"],
                    "lineEnd": record["lineEnd"],
                }
            )
            if len(items) >= max(1, min(int(max_items), 50)):
                break
        return items

    @staticmethod
    def _heading_at(text: str, position: int) -> str | None:
        matches = [match for match in _HEADING.finditer(text, 0, position)]
        return matches[-1].group(2).strip() if matches else None

    @classmethod
    def _formulas(cls, text: str, max_items: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for match in _BLOCK_FORMULA.finditer(text):
            items.append({"formula": match.group(1).strip(), "heading": cls._heading_at(text, match.start())})
            if len(items) >= max(1, min(int(max_items), 50)):
                break
        return items

    @classmethod
    def _figures(cls, text: str, directory: Path, max_items: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        figure_index = 0
        for match in _IMAGE.finditer(text):
            figure_index += 1
            target = match.group(1).strip()
            if "://" in target or target.startswith("data:"):
                continue
            asset_path = confined_path(directory, target.lstrip("./"))
            line_end = text.find("\n", match.end())
            line_end = len(text) if line_end < 0 else line_end
            following = text[match.end() : min(len(text), line_end + 500)].strip()
            caption = following.splitlines()[0].strip() if following else ""
            if not _CAPTION.match(caption):
                caption = ""
            items.append(
                {
                    "kind": "figure",
                    "objectId": f"figure-{figure_index}",
                    "path": str(asset_path),
                    "exists": asset_path.exists(),
                    "caption": caption,
                    "heading": cls._heading_at(text, match.start()),
                    "analysisContext": cls._nearby_context(text, match.start(), line_end),
                }
            )
            if len(items) >= max(1, min(int(max_items), 50)):
                break
        table_pattern = re.compile(r"(?m)(?:^\|.*\|\s*$\n?){2,}")
        table_index = 0
        for match in table_pattern.finditer(text):
            table_index += 1
            items.append(
                {
                    "kind": "table",
                    "objectId": f"table-{table_index}",
                    "markdown": match.group(0).strip(),
                    "heading": cls._heading_at(text, match.start()),
                    "analysisContext": cls._nearby_context(text, match.start(), match.end()),
                }
            )
            if len(items) >= max(1, min(int(max_items), 50)):
                break
        return items

    @staticmethod
    def _nearby_context(text: str, start: int, end: int, limit: int = 1_200) -> str:
        before = text[max(0, start - limit // 2) : start].strip()
        after = text[end : min(len(text), end + limit // 2)].strip()
        return "\n\n".join(part for part in (before, after) if part)[-limit:]

    async def _cache_result(self, result: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
        context_id = arguments.get("contextId")
        if not context_id or not self.context_store:
            return result
        items = result.get("items")
        if not isinstance(items, list):
            text = result.get("text") or result.get("evidence")
            items = [{"text": text}] if text else []
        bounded: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("text"):
                bounded.append(item)
            elif item.get("analysisContext"):
                bounded.append({**item, "text": item["analysisContext"]})
        result["context"] = await self.context_store.add_items(
            str(context_id), bounded, title=f"{result.get('mode', 'reading').title()} evidence"
        )
        return result

    async def _multi(self, keys: list[str], mode: str, arguments: dict[str, Any]) -> dict[str, Any]:
        documents: list[dict[str, Any]] = []
        per_document = max(500, min(int(arguments.get("maxChars", 3500)), 6000))
        for key in keys:
            source = await self._source(key, arguments.get("attachmentKey"))
            paper = source["paper"]
            text = source["markdown"]
            section = arguments.get("section")
            if section:
                excerpt = self._section(text, section)
            elif arguments.get("query"):
                paragraphs = self._paragraphs(text, arguments["query"], 4)
                excerpt = "\n\n".join(item["text"] for item in paragraphs)
            else:
                excerpt = str(paper.get("abstract") or "")
            documents.append(
                {
                    "zoteroKey": source["key"],
                    "title": source["title"],
                    "doi": paper.get("doi"),
                    "date": paper.get("date"),
                    "abstract": str(paper.get("abstract") or "")[:2000],
                    "headings": [match.group(2).strip() for match in _HEADING.finditer(text)][:100],
                    "evidence": excerpt[:per_document],
                    "markdownPath": str(source["markdownPath"]),
                }
            )
        result = {"mode": mode, "documents": documents}
        if arguments.get("contextId") and self.context_store:
            result["context"] = await self.context_store.add_items(
                str(arguments["contextId"]),
                [
                    {
                        "text": document["evidence"],
                        "source": {
                            key: document[key]
                            for key in ("zoteroKey", "title", "doi", "markdownPath")
                            if document.get(key) is not None
                        },
                    }
                    for document in documents
                    if document.get("evidence")
                ],
                title=f"{mode.title()} evidence",
            )
        return result
