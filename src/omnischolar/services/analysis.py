"""Persist structured literature analyses with source fingerprints and links."""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote

from omnischolar.core import OmniScholarError, atomic_write, confined_path, read_file_bounded

from .reader import LiteratureReader
from .sync import SyncService, metadata_fingerprint, stable_hash

AnalysisType = Literal["full-read", "targeted-reading", "compare", "review"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(value: str, fallback: str) -> str:
    value = re.sub(r"[^\w\-\u3400-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-._ ")
    return value[:120] or fallback


class AnalysisService:
    """Write Agent-generated analysis Markdown without overwriting local edits."""

    def __init__(self, sync: SyncService, reader: LiteratureReader, config: Any) -> None:
        self.sync = sync
        self.reader = reader
        self.config = config

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        action = str(arguments.get("action", "write"))
        if action == "write":
            return await self.write(arguments)
        if action == "list":
            return await self.list(arguments)
        if action == "get":
            return await self.get(arguments)
        raise OmniScholarError(
            "invalid_analysis_action",
            f"Unknown analysis action: {action}",
            category="validation",
        )

    async def write(self, arguments: dict[str, Any]) -> dict[str, Any]:
        analysis_type = str(arguments.get("analysisType", ""))
        if analysis_type not in {"full-read", "targeted-reading", "compare", "review"}:
            raise OmniScholarError(
                "invalid_analysis_type",
                "analysisType must be full-read, targeted-reading, compare, or review",
                category="validation",
            )
        content = arguments.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OmniScholarError(
                "analysis_content_required",
                "Analysis write requires non-empty Markdown content",
                category="validation",
            )
        keys = self._keys(arguments)
        if analysis_type in {"compare", "review"} and len(keys) < 2:
            raise OmniScholarError(
                "multiple_keys_required",
                f"{analysis_type} requires at least two Zotero keys",
                category="validation",
            )
        sources = [
            await self.reader.source(key, arguments.get("attachmentKey")) for key in keys
        ]
        source_fingerprints = {
            source["key"]: stable_hash(
                {
                    "metadata": metadata_fingerprint(source["paper"]),
                    "markdown": stable_hash(source["markdown"]),
                    "notes": stable_hash(source["paper"].get("notes", [])),
                    "annotations": stable_hash(source["paper"].get("annotations", [])),
                }
            )
            for source in sources
        }
        source_fingerprint = stable_hash(source_fingerprints)
        relative_path = self._relative_path(analysis_type, arguments, sources)
        source_links = self._source_links(relative_path, sources)
        document = self._document(
            analysis_type,
            keys,
            source_fingerprint,
            source_links,
            content,
            arguments.get("language"),
            relative_path,
        )
        target = confined_path(self.sync.root, relative_path)
        if target.exists() and not bool(arguments.get("overwrite", False)):
            candidate = f".conflicts/analysis/{Path(relative_path).with_suffix('').as_posix()}-{uuid.uuid4().hex[:8]}.md"
            await atomic_write(self.sync.root, candidate, document.encode("utf-8"))
            return {
                "status": "conflict",
                "path": relative_path,
                "candidatePath": candidate,
                "sourceFingerprint": source_fingerprint,
                "sourceKeys": keys,
            }
        await atomic_write(self.sync.root, relative_path, document.encode("utf-8"))
        return {
            "status": "written",
            "path": relative_path,
            "sourceFingerprint": source_fingerprint,
            "sourceKeys": keys,
            "analysisType": analysis_type,
        }

    async def list(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        paths: list[str] = []
        for directory in (
            self.config.analysis.single_directory,
            self.config.analysis.multi_directory,
        ):
            root = confined_path(self.sync.root, directory)
            if root.is_dir():
                paths.extend(
                    str(path.relative_to(self.sync.root)).replace("\\", "/")
                    for path in root.rglob("*.md")
                    if path.is_file()
                )
        return {"analyses": sorted(paths)}

    async def get(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments.get("path")
        if not isinstance(path, str) or not path:
            raise OmniScholarError(
                "analysis_path_required", "Analysis get requires a relative path", category="validation"
            )
        target = confined_path(self.sync.root, path, must_exist=True)
        content = (await read_file_bounded(target, 2 * 1024 * 1024)).decode("utf-8", errors="replace")
        return {"path": str(target.relative_to(self.sync.root)).replace("\\", "/"), "content": content}

    @staticmethod
    def _keys(arguments: dict[str, Any]) -> list[str]:
        raw = arguments.get("keys") or ([] if not arguments.get("key") else [arguments["key"]])
        if isinstance(raw, str) or not isinstance(raw, list):
            raise OmniScholarError(
                "analysis_keys_required", "Analysis keys must be an array", category="validation"
            )
        keys = [str(value) for value in raw if str(value).strip()]
        if not keys:
            raise OmniScholarError(
                "analysis_keys_required", "Analysis requires one or more Zotero keys", category="validation"
            )
        return list(dict.fromkeys(keys))

    def _relative_path(
        self, analysis_type: str, arguments: dict[str, Any], sources: list[dict[str, Any]]
    ) -> str:
        if analysis_type in {"full-read", "targeted-reading"}:
            paper = sources[0]["paper"]
            folder = sources[0]["directory"].name
            template = self.config.analysis.single_filename_template
            filename = self._format_filename(
                template,
                paper=paper,
                analysis_type=analysis_type,
                topic=str(arguments.get("topic") or ""),
            )
            return f"{self.config.analysis.single_directory}/{folder}/{filename}.md"
        topic = str(arguments.get("topic") or "literature")
        template = (
            self.config.analysis.comparison_filename_template
            if analysis_type == "compare"
            else self.config.analysis.review_filename_template
        )
        filename = self._format_filename(
            template,
            paper=sources[0]["paper"],
            analysis_type=analysis_type,
            topic=topic,
        )
        return f"{self.config.analysis.multi_directory}/{filename}.md"

    def _format_filename(
        self,
        template: str,
        *,
        paper: dict[str, Any],
        analysis_type: str,
        topic: str,
    ) -> str:
        creators = paper.get("creators") if isinstance(paper.get("creators"), list) else []
        author = next(
            (
                item.get("lastName") or item.get("name")
                for item in creators
                if isinstance(item, dict) and item.get("creatorType") == "author"
            ),
            "UnknownAuthor",
        )
        values = {
            "author": str(author),
            "year": str(paper.get("year") or paper.get("date") or "UnknownYear")[:4],
            "title": str(paper.get("title") or "Untitled"),
            "zoteroKey": str(paper.get("zoteroKey") or ""),
            "topic": topic,
            "date": datetime.now(UTC).date().isoformat(),
            "analysisType": analysis_type,
            "separator": self.sync.filename_separator,
        }
        result = _slug(template.format(**values), analysis_type)
        return result[:-3] if result.casefold().endswith(".md") else result

    def _source_links(self, analysis_path: str, sources: list[dict[str, Any]]) -> list[dict[str, str]]:
        base = (self.sync.root / analysis_path).parent
        vault_root = self._vault_root()
        links: list[dict[str, str]] = []
        for source in sources:
            paper_dir = source["directory"]
            markdown = source["markdownPath"]
            pdf = paper_dir / self.sync.source_directory / self.sync._source_pdf_name(source["paper"])
            record = paper_dir / self.sync.source_directory / self.sync.zotero_reading_record_filename
            links.append(
                {
                    "zoteroKey": source["key"],
                    "title": source["title"],
                    "paper": Path(os.path.relpath(markdown, base)).as_posix(),
                    "pdf": Path(os.path.relpath(pdf, base)).as_posix(),
                    "readingRecord": Path(os.path.relpath(record, base)).as_posix(),
                    "vaultPaper": self._vault_link_path(markdown, vault_root),
                    "vaultPdf": self._vault_link_path(pdf, vault_root),
                    "vaultReadingRecord": self._vault_link_path(record, vault_root),
                }
            )
        return links

    def _vault_root(self) -> Path:
        for candidate in (self.sync.root, *self.sync.root.parents):
            if (candidate / ".obsidian").is_dir():
                return candidate
        return self.sync.root

    @staticmethod
    def _vault_link_path(path: Path, vault_root: Path) -> str:
        try:
            return path.resolve().relative_to(vault_root.resolve()).as_posix()
        except ValueError:
            return path.name

    @staticmethod
    def _strip_input_frontmatter(content: str) -> str:
        body = content.lstrip("\ufeff")
        while body.startswith("---"):
            match = re.match(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", body, flags=re.DOTALL)
            if not match:
                break
            body = body[match.end() :].lstrip()
        return body.strip()

    @staticmethod
    def _split_table_row(line: str) -> list[str]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            return []
        cells: list[str] = []
        current: list[str] = []
        in_wiki_embed = False
        index = 0
        while index < len(stripped):
            if not in_wiki_embed and stripped.startswith("![[", index):
                in_wiki_embed = True
                current.extend("![[")
                index += 3
                continue
            if in_wiki_embed and stripped.startswith("]]", index):
                in_wiki_embed = False
                current.extend("]]")
                index += 2
                continue
            character = stripped[index]
            if character == "\\" and index + 1 < len(stripped):
                current.extend((character, stripped[index + 1]))
                index += 2
                continue
            if character == "|" and not in_wiki_embed:
                cells.append("".join(current).strip())
                current = []
            else:
                current.append(character)
            index += 1
        cells.append("".join(current).strip())
        if cells and not cells[0]:
            cells.pop(0)
        if cells and not cells[-1]:
            cells.pop()
        return cells

    @staticmethod
    def _clean_field_value(value: str, *, title: bool = False) -> str:
        value = re.sub(r"(?:^\s*<br\s*/?>\s*)+", "", value)
        value = re.sub(r"(?:\s*<br\s*/?>\s*)+$", "", value)
        value = value.strip()
        if title:
            value = re.sub(r"^\s*\d+[.)]\s*", "", value)
        return value

    @staticmethod
    def _extract_figure_fields(value: str) -> dict[str, str]:
        labels = ("图表标题", "原文位置", "作者原文表述", "图表解读")
        marker_pattern = re.compile(
            r"(?:^|<br\s*/?>|\n|\s+)"
            r"(?:\d+[.)]\s*)?\*{0,2}"
            r"(?P<label>图表标题|原文位置|作者原文表述|图表解读)"
            r"\*{0,2}\s*[:：]\s*"
        )
        matches = list(marker_pattern.finditer(value))
        fields: dict[str, str] = {}
        for match in matches:
            label = match.group("label")
            if label in fields:
                continue
            following = next(
                (candidate for candidate in matches if candidate.start() > match.end()),
                None,
            )
            end = following.start() if following else len(value)
            fields[label] = AnalysisService._clean_field_value(
                value[match.end() : end],
                title=label == "图表标题",
            )
        return {label: fields[label] for label in labels if fields.get(label)}

    @staticmethod
    def _simple_figure_fields(value: str) -> dict[str, str]:
        compact = re.sub(r"\s*<br\s*/?>\s*", " ", value).strip()
        name_match = re.search(
            r"(?:名称|图表标题)\s*[:：]\s*(.+?)(?=(?:原文观察|作者原文表述|解读|图表解读)\s*[:：]|$)",
            compact,
        )
        observation_match = re.search(
            r"(?:原文观察|作者原文表述)\s*[:：]\s*(.+?)(?=(?:解读|图表解读)\s*[:：]|$)",
            compact,
        )
        interpretation_match = re.search(r"(?:解读|图表解读)\s*[:：]\s*(.+)$", compact)
        bold = re.search(r"\*\*(.+?)\*\*", compact)
        figure = re.search(
            r"(?:^|\s)((?:图\s*\d+|Figure\s*\d+)\.?)(?=\s|$|[:：])",
            compact,
            re.IGNORECASE,
        )
        title = name_match.group(1).strip() if name_match else (
            bold.group(1).strip() if bold else (figure.group(1).strip() if figure else compact)
        )
        if figure and not name_match and not bold:
            title = title.rstrip(".")
        observation = observation_match.group(1).strip() if observation_match else ""
        interpretation = interpretation_match.group(1).strip() if interpretation_match else compact
        return {
            "图表标题": AnalysisService._clean_field_value(title, title=True),
            "原文位置": "见对应图注/正文",
            "作者原文表述": observation or "见论文图注和对应正文段落；MinerU 未抽取可靠逐字表述。",
            "图表解读": interpretation,
        }

    @staticmethod
    def _format_figure_fields(fields: dict[str, str]) -> str:
        return (
            f"1. **图表标题**：{fields['图表标题']}<br><br>"
            f"2. **原文位置**：{fields['原文位置']}<br><br>"
            f"3. **作者原文表述**：{fields['作者原文表述']}<br><br>"
            f"4. **图表解读**：{fields['图表解读']}"
        )

    def _normalise_table_image_embeds(self, body: str, analysis_path: str) -> str:
        analysis_directory = (self.sync.root / analysis_path).parent
        vault_root = self._vault_root()

        def resolve_asset(raw_path: str) -> Path | None:
            normalized = unquote(raw_path).replace("\\", "/").strip()
            raw = Path(normalized)
            if raw.is_absolute():
                return raw
            if normalized.startswith("../"):
                candidate = (analysis_directory / raw).resolve()
                return candidate if candidate.exists() else None
            for candidate in (vault_root / raw, analysis_directory / raw):
                if candidate.exists():
                    return candidate.resolve()
            return None

        def relative_asset(path: Path) -> str:
            try:
                relative = path.resolve().relative_to(vault_root.resolve()).as_posix()
            except ValueError:
                relative = os.path.relpath(path, analysis_directory)
            return Path(relative).as_posix()

        def make_markdown_image(raw_path: str) -> str:
            normalized = unquote(raw_path).replace("\\", "/").strip()
            normalized = re.sub(r"\s*\|\s*\d+\s*$", "", normalized).strip()
            original = resolve_asset(normalized)
            if original is None:
                return f"![[{normalized}]]"
            vault_link = relative_asset(original)
            return f"![[{vault_link}]]"

        wiki_pattern = re.compile(r"!\[\[(?P<path>[^\]]+?)\]\]")

        def figure_right_cell(value: str) -> str:
            fields = self._extract_figure_fields(value)
            if fields:
                defaults = self._simple_figure_fields(value)
                fields = {
                    label: fields.get(label) or defaults[label]
                    for label in ("图表标题", "原文位置", "作者原文表述", "图表解读")
                }
            else:
                fields = self._simple_figure_fields(value)
            return self._format_figure_fields(fields)

        output: list[str] = []
        in_figure_table = False
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and "预览" in stripped and "图表" in stripped:
                in_figure_table = True
                output.append("| 预览 | 图表名称、原文位置与分析解读 |")
                continue
            if in_figure_table:
                if not stripped.startswith("|"):
                    in_figure_table = False
                    output.append(line)
                    continue
                cells = self._split_table_row(stripped)
                if cells and all(re.fullmatch(r"[-:\s]+", cell) for cell in cells):
                    output.append("| --- | --- |")
                    continue
                if len(cells) < 2:
                    continue
                left, right_parts = cells[0], cells[1:]
                right = " \\| ".join(right_parts).strip()
                matches = list(wiki_pattern.finditer(left))
                if matches:
                    right_cell = figure_right_cell(right)
                    output.extend(
                        f"| {make_markdown_image(match.group('path'))} | {right_cell} |"
                        for match in matches
                    )
                else:
                    output.append(f"| {left} | {right} |")
                continue
            if stripped.startswith("|"):
                output.append(line)
            else:
                output.append(line)
        return "\n".join(output)

    @staticmethod
    def _strip_input_sources(body: str) -> str:
        return re.sub(
            r"(?ims)^##\s+(?:Sources|来源|来源与阅读记录|Zotero\s+(?:阅读记录|Reading\s+Record))\s*$.*?(?=^##\s+|\Z)",
            "",
            body,
        ).strip()

    def _document(
        self,
        analysis_type: str,
        keys: list[str],
        fingerprint: str,
        source_links: list[dict[str, str]],
        content: str,
        language: str | None,
        analysis_path: str,
    ) -> str:
        import json

        frontmatter = {
            "schemaVersion": 1,
            "analysisType": analysis_type,
            "sourceKeys": keys,
            "sourceCount": len(keys),
            "sourceFingerprint": fingerprint,
            "language": language or "user-language",
            "status": "ready",
            "updatedAt": _now(),
        }
        body = self._strip_input_frontmatter(content)
        body = self._strip_input_sources(body)
        body = self._normalise_table_image_embeds(body, analysis_path)
        lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}: [{', '.join(json.dumps(item, ensure_ascii=False) for item in value)}]")
            else:
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        lines.extend(["---", "", body, "", "## Sources", ""])
        for source in source_links:
            lines.extend(
                [
                    f"- **{source['title']}** (`{source['zoteroKey']}`)",
                    f"  - MinerU 原文：[[{source['vaultPaper']}|打开解析文档]]",
                    f"  - PDF：[[{source['vaultPdf']}|打开或预览 PDF]]",
                    f"  - Zotero 笔记与批注：[[{source['vaultReadingRecord']}|打开阅读记录]]",
                ]
            )
        lines.append("")
        return "\n".join(lines)
