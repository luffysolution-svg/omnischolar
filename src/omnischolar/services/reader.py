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

    def __init__(self, sync: SyncService, *, max_document_bytes: int = 32 * 1024 * 1024) -> None:
        self.sync = sync
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
            return {**common, **self._chunk(scoped, arguments.get("cursor", 0), arguments.get("maxChars", 8000))}
        if mode == "paragraphs":
            return {**common, "items": self._paragraphs(scoped, arguments.get("query"), arguments.get("maxItems", 20))}
        if mode == "formulas":
            return {**common, "items": self._formulas(scoped, arguments.get("maxItems", 20))}
        if mode == "figures":
            return {**common, "items": self._figures(scoped, source["directory"], arguments.get("maxItems", 20))}
        raise OmniScholarError(
            "invalid_reading_mode", f"Unsupported reading mode: {mode}", category="validation"
        )

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
    def _section(text: str, section: str | None) -> str:
        if not section:
            return text
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
            return text[match.start() : end].strip()
        raise OmniScholarError(
            "section_not_found", f"No heading matched section: {section}", category="validation"
        )

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

    @staticmethod
    def _paragraphs(text: str, query: str | None, max_items: int) -> list[dict[str, Any]]:
        wanted = (query or "").casefold().strip()
        items: list[dict[str, Any]] = []
        for block in re.split(r"\n\s*\n", text):
            value = block.strip()
            if not value or value.startswith("#") or (wanted and wanted not in value.casefold()):
                continue
            heading_matches = list(_HEADING.finditer(value))
            heading = heading_matches[0].group(2).strip() if heading_matches else None
            items.append({"text": value[:4000], "heading": heading})
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
        for match in _IMAGE.finditer(text):
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
                    "path": str(asset_path),
                    "caption": caption,
                    "heading": cls._heading_at(text, match.start()),
                }
            )
            if len(items) >= max(1, min(int(max_items), 50)):
                break
        table_pattern = re.compile(r"(?m)(?:^\|.*\|\s*$\n?){2,}")
        for match in table_pattern.finditer(text):
            items.append(
                {
                    "kind": "table",
                    "markdown": match.group(0).strip(),
                    "heading": cls._heading_at(text, match.start()),
                }
            )
            if len(items) >= max(1, min(int(max_items), 50)):
                break
        return items

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
        return {"mode": mode, "documents": documents}
