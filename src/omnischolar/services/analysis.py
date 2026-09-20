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

    def _normalise_table_image_embeds(self, body: str, analysis_path: str) -> str:
        analysis_directory = (self.sync.root / analysis_path).parent
        vault_root = self._vault_root()

        def resolve_asset(raw_path: str) -> Path:
            raw_path = unquote(raw_path).replace("\\", "/")
            raw = Path(raw_path)
            if raw.is_absolute():
                return raw
            if raw_path.startswith("../"):
                return (analysis_directory / raw).resolve()
            candidate = vault_root / raw
            return candidate if candidate.exists() else (analysis_directory / raw).resolve()

        def relative_asset(path: Path) -> str:
            try:
                relative = path.resolve().relative_to(vault_root.resolve()).as_posix()
            except ValueError:
                relative = os.path.relpath(path, analysis_directory)
            return Path(relative).as_posix()

        def make_markdown_image(raw_path: str) -> str:
            original = resolve_asset(raw_path)
            vault_link = relative_asset(original)
            return f"![[{vault_link}]]"

        wiki_pattern = re.compile(r"!\[\[(?P<path>[^\]]+)\]\]")

        def figure_right_cell(value: str) -> str:
            if "图表标题" in value:
                if "1. **图表标题**：" in value:
                    headings = re.findall(r"\*\*(Figure\s+\d+[^*<]+)\*\*", value)
                    title = headings[-1].strip(" 。") if headings else "图表标题"
                    if headings:
                        marker = f"**{headings[-1]}**"
                        interpretation = value.rsplit(marker, 1)[-1].strip(" 。")
                    else:
                        interpretation = value.rsplit("4. **图表解读**：", 1)[-1].strip()
                    location_match = re.search(r"§\s*[^，。 ]+", title)
                    location = location_match.group(0) if location_match else "见对应图注/正文"
                    author_match = re.search(
                        r"3\. \*\*作者原文表述\*\*：(.+?)(?=<br><br>|$)", value
                    )
                    author = author_match.group(1).strip() if author_match else "见论文图注和对应正文段落。"
                    return (
                        f"1. **图表标题**：{title}<br><br>"
                        f"2. **原文位置**：{location}<br><br>"
                        f"3. **作者原文表述**：{author}<br><br>"
                        f"4. **图表解读**：{interpretation.strip()}"
                    )
                fields = {}
                for label in ("图表标题", "原文位置", "作者原文表述", "图表解读"):
                    field = re.search(
                        rf"(?:^|<br>)\s*[-\d.]+\s*\*?\*?{label}\*?\*?：(.+?)(?=<br>|$)",
                        value,
                    )
                    fields[label] = field.group(1).strip() if field else "见对应图注/正文"
                return (
                    f"1. **图表标题**：{fields['图表标题']}<br><br>"
                    f"2. **原文位置**：{fields['原文位置']}<br><br>"
                    f"3. **作者原文表述**：{fields['作者原文表述']}<br><br>"
                    f"4. **图表解读**：{fields['图表解读']}"
                )
            compact = re.sub(r"\s*<br>\s*", " ", value).strip()
            bold = re.search(r"\*\*(.+?)\*\*", compact)
            heading = bold.group(1).strip(" 。") if bold else compact
            location_match = re.search(r"(§\s*[^，。]+)", heading)
            location = location_match.group(1) if location_match else "见对应图注/正文"
            name_match = re.search(r"名称：(.+?)(?=原文观察：|解读：|$)", compact)
            observation_match = re.search(r"原文观察：(.+?)(?=解读：|$)", compact)
            interpretation_match = re.search(r"解读：(.+)$", compact)
            title = (name_match.group(1).strip(" 。") if name_match else heading)
            observation = (
                observation_match.group(1).strip(" 。")
                if observation_match
                else "见论文图注和对应正文段落；MinerU 未抽取可靠逐字表述。"
            )
            interpretation = interpretation_match.group(1).strip(" 。") if interpretation_match else compact
            if not interpretation_match and bold:
                interpretation = compact.replace(bold.group(0), "", 1).strip(" 。")
            return (
                f"1. **图表标题**：{title}<br><br>"
                f"2. **原文位置**：{location}<br><br>"
                f"3. **作者原文表述**：{observation}<br><br>"
                f"4. **图表解读**：{interpretation}"
            )

        output: list[str] = []
        in_figure_table = False
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and "预览" in stripped and "图表名称" in stripped:
                in_figure_table = True
                output.append("| 预览 | 图表名称、原文位置与分析解读 |")
                continue
            if in_figure_table:
                if not stripped.startswith("|"):
                    in_figure_table = False
                    output.append(line)
                    continue
                if re.fullmatch(r"\|[\s|:-]+\|", stripped):
                    output.append("| --- | --- |")
                    continue
                matches = [
                    (match.start(), match.end(), make_markdown_image(match.group("path")))
                    for match in wiki_pattern.finditer(line)
                ]
                if matches:
                    tail = line[matches[-1][1] :].strip().lstrip("|").strip()
                    right = re.split(r"\s+\|", tail, maxsplit=1)[0].strip()
                    right_cell = figure_right_cell(right)
                    output.extend(f"| {item[2]} | {right_cell} |" for item in matches)
                elif line.count("|") >= 3:
                    output.append(line)
                continue
            if stripped.startswith("|"):
                output.append(line)
            else:
                output.append(line)
        return "\n".join(output)

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
        body = re.sub(
            r"(?ims)^##\s+(?:Sources|来源|来源与阅读记录)\s*$.*?(?=^##\s+|\Z)",
            "",
            body,
        ).strip()
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
