"""Render readable, source-linked Zotero notes and PDF annotations."""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

import yaml

_TAG_RE = re.compile(r"<[^>]+>")
_COLOR_NAMES = {
    "#ffd400": "yellow",
    "#ff6666": "red",
    "#5fb236": "green",
    "#2ea8e5": "blue",
    "#a28ae5": "purple",
    "#f19837": "orange",
}
_COLOR_STYLES = {
    "yellow": ("#ffd400", "#fff8cc"),
    "red": ("#ff6666", "#ffe5e5"),
    "green": ("#5fb236", "#e9f6df"),
    "blue": ("#2ea8e5", "#e4f4fc"),
    "purple": ("#a28ae5", "#f0ebfb"),
    "orange": ("#f19837", "#fff0df"),
}


def _plain_note(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"</(?:p|div|li|h[1-6])\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            tag = item.get("tag")
        else:
            tag = item
        if isinstance(tag, str) and tag.strip():
            result.append(tag.strip())
    return list(dict.fromkeys(result))


def _tag_line(tags: list[str]) -> str:
    return " ".join(f"`#{html.escape(tag.replace('`', ''))}`" for tag in tags)


def _obsidian_tag(value: str) -> str | None:
    tag = unicodedata.normalize("NFKC", value).strip().lstrip("#").strip()
    tag = re.sub(r"\s+", "-", tag)
    tag = re.sub(r"[^\w/-]+", "-", tag, flags=re.UNICODE)
    tag = re.sub(r"-{2,}", "-", tag).strip("-_/ ")
    if not tag:
        return None
    return f"tag-{tag}" if tag.isdecimal() else tag


def _creator_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for creator in value:
        if not isinstance(creator, Mapping):
            continue
        name = str(creator.get("name") or "").strip()
        if not name:
            name = " ".join(
                part
                for field in ("firstName", "lastName")
                if (part := str(creator.get(field) or "").strip())
            )
        if name:
            names.append(name)
    return list(dict.fromkeys(names))


def render_frontmatter(
    paper: Mapping[str, Any],
    *,
    record_type: str,
    source_kinds: list[str] | None = None,
) -> str:
    """Render shared Zotero-backed YAML properties for Obsidian Markdown."""

    collections = paper.get("collections")
    tags = [tag for value in _tags(paper.get("tags")) if (tag := _obsidian_tag(value))]
    zotero_key = str(paper.get("zoteroKey") or "")
    properties: dict[str, Any] = {
        "recordType": record_type,
        "title": str(paper.get("title") or "Untitled"),
        "itemType": paper.get("itemType"),
        "creators": _creator_names(paper.get("creators")),
        "zoteroKey": zotero_key,
        "DOI": paper.get("doi"),
        "URL": paper.get("url"),
        "publicationTitle": paper.get("publicationTitle"),
        "tags": list(dict.fromkeys(tags)),
        "abstract": paper.get("abstract"),
        "collections": list(collections) if isinstance(collections, list) else [],
        "zoteroLink": f"zotero://select/library/items/{zotero_key}" if zotero_key else None,
    }
    if source_kinds is not None:
        properties["sourceKinds"] = source_kinds
    document = yaml.safe_dump(
        properties,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100_000,
    ).rstrip()
    return f"---\n{document}\n---"


def _annotation_data(annotation: Mapping[str, Any]) -> dict[str, Any]:
    raw = annotation.get("data")
    data = dict(raw) if isinstance(raw, Mapping) else dict(annotation)
    position = data.get("annotationPosition")
    if isinstance(position, str):
        try:
            import json

            position = json.loads(position)
        except (TypeError, ValueError):
            pass
    page = data.get("annotationPageLabel") or data.get("pageLabel")
    if page is None and isinstance(position, Mapping):
        page = position.get("pageIndex")
        if isinstance(page, int):
            page += 1
    color = str(data.get("annotationColor") or "").casefold()
    color_name = _COLOR_NAMES.get(color, color.removeprefix("#") or "default")
    annotation_type = str(data.get("annotationType") or "annotation").replace("_", " ")
    return {
        "key": annotation.get("key") or data.get("key"),
        "type": annotation_type,
        "color": color_name,
        "colorHex": color if color.startswith("#") else None,
        "page": page,
        "text": str(data.get("annotationText") or "").strip(),
        "comment": _plain_note(data.get("annotationComment")),
        "tags": _tags(data.get("tags")),
        "position": position,
        "dateModified": data.get("dateModified") or annotation.get("dateModified"),
    }


def _annotation_block(annotation: Mapping[str, Any], index: int, pdf_filename: str) -> str:
    item = _annotation_data(annotation)
    color_name = str(item["color"])
    border, background = _COLOR_STYLES.get(color_name, ("#888888", "#f4f4f4"))
    page = item.get("page")
    page_label = f"Page {page}" if page is not None else "Page unknown"
    tags = _tag_line(item["tags"])
    tag_suffix = f" · {tags}" if tags else ""
    link = f"./{pdf_filename}#page={page}" if page is not None else f"./{pdf_filename}"
    text = html.escape(str(item["text"] or "(no selected text)"))
    comment = html.escape(str(item["comment"] or ""))
    comment_block = f"<p><strong>Comment:</strong> {comment}</p>" if comment else ""
    return (
        f'<div class="zotero-annotation zotero-{html.escape(color_name)}" '
        f'style="border-left:4px solid {border};background:{background};padding:0.65em 0.85em;margin:0.8em 0">\n'
        f"<p><strong>{html.escape(str(item['type']).title())}</strong> · "
        f"{html.escape(page_label)} · {html.escape(color_name)}{tag_suffix}</p>\n"
        f"<blockquote>{text}</blockquote>\n"
        f"{comment_block}"
        f'<p><a href="{html.escape(link)}">Open PDF</a> · annotation {index}</p>\n'
        "</div>"
    )


def render_zotero_reading_record(
    paper: Mapping[str, Any], *, pdf_filename: str = "paper.pdf", embed_pdf: bool = True
) -> str:
    """Render a human-readable record while preserving note/annotation provenance."""

    title = str(paper.get("title") or "Untitled")
    lines = [
        render_frontmatter(
            paper,
            record_type="zotero-reading-record",
            source_kinds=["zotero-note", "pdf-annotation"],
        ),
        "",
        f"# Zotero 阅读记录：{title}",
        "",
        f"[打开 PDF](./{pdf_filename})",
    ]
    if embed_pdf:
        lines.extend(["", f"![[{pdf_filename}]]"])
    lines.extend(["", "---", "", "## Zotero 笔记", ""])
    notes = paper.get("notes")
    if isinstance(notes, list) and notes:
        for index, note in enumerate(notes, 1):
            if not isinstance(note, Mapping):
                continue
            note_text = _plain_note(note.get("note"))
            if not note_text:
                continue
            tags = _tag_line(_tags(note.get("tags")))
            lines.extend(
                [
                    f"### 笔记 {index}",
                    "",
                    f"**Zotero note key:** `{note.get('key', '')}`",
                    f"**Tags:** {tags or 'None'}",
                    "",
                    note_text,
                    "",
                ]
            )
    else:
        lines.extend(["_No Zotero notes were found._", ""])

    lines.extend(["---", "", "## PDF 批注", ""])
    annotations = paper.get("annotations")
    rendered = 0
    if isinstance(annotations, list):
        for index, annotation in enumerate(annotations, 1):
            if not isinstance(annotation, Mapping):
                continue
            lines.extend([_annotation_block(annotation, index, pdf_filename), ""])
            rendered += 1
    if rendered == 0:
        lines.extend(["_No PDF annotations were found._", ""])
    lines.extend(
        [
            "---",
            "",
            "> Notes and annotations are personal reading records. They are not independent paper evidence.",
            "",
        ]
    )
    return "\n".join(lines)
