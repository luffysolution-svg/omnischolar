"""Read-only Zotero Desktop Local API service."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from omnischolar.core import OmniScholarError

from .transport import ServiceTransport

_KEY = re.compile(r"^[A-Z0-9]{8}$")


def validate_zotero_key(value: str, label: str = "Zotero key") -> str:
    if not _KEY.fullmatch(value):
        raise OmniScholarError(
            "invalid_zotero_key",
            f"{label} must be 8 uppercase letters or digits",
            category="validation",
        )
    return value


class ZoteroService:
    """All methods issue GET requests only, to a validated loopback base URL."""

    def __init__(
        self,
        transport: ServiceTransport,
        *,
        base_url: str = "http://127.0.0.1:23119/api",
        max_items: int = 500,
        max_indexed_text_bytes: int = 16 * 1024,
    ) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.port != 23119
        ):
            raise OmniScholarError(
                "unsafe_zotero_url",
                "Zotero Local API must use HTTP loopback port 23119",
                category="config",
            )
        self.transport = transport
        self.base_url = base_url.rstrip("/")
        self.max_items = max(1, min(max_items, 5_000))
        self.max_indexed_text_bytes = max(0, min(max_indexed_text_bytes, 1024 * 1024))
        self.headers = {
            "Zotero-API-Version": "3",
            "Zotero-Allowed-Request": "1",
            "User-Agent": "OmniScholar/0.1",
        }

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            raise OmniScholarError(
                "unsafe_zotero_path", "Zotero path must be absolute", category="validation"
            )
        return f"{self.base_url}/users/0{path}"

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self.transport.json(
            "GET", self._url(path), params=params, headers=self.headers
        )

    async def list(
        self, path: str, *, params: dict[str, Any] | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        requested = min(max(limit or self.max_items, 1), self.max_items)
        items: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        start = 0
        exhausted = False
        while len(items) < requested:
            page_size = min(100, requested - len(items))
            query = {**(params or {}), "start": start, "limit": page_size}
            value = await self._get(path, params=query)
            if not isinstance(value, list):
                raise OmniScholarError(
                    "zotero_schema_mismatch",
                    "Zotero returned a malformed list",
                    category="provider",
                )
            page = [item for item in value if isinstance(item, dict)]
            signature = tuple(str(item.get("key", item)) for item in page)
            if signature in seen and signature:
                raise OmniScholarError(
                    "zotero_pagination_loop", "Zotero repeated a page", category="provider"
                )
            seen.add(signature)
            items.extend(page[: requested - len(items)])
            if len(page) < page_size:
                exhausted = True
                break
            start += len(page)
        return {
            "items": items,
            "total": len(items),
            "truncated": not exhausted and len(items) == requested,
        }

    async def collections(
        self, action: str = "list", *, key: str | None = None, limit: int = 500
    ) -> Any:
        if action == "read":
            return await self._get(
                f"/collections/{validate_zotero_key(key or '', 'Collection key')}"
            )
        if action == "items":
            collection = validate_zotero_key(key or "", "Collection key")
            result = await self.list(f"/collections/{collection}/items", limit=limit)
            result["items"] = [
                item
                for item in result["items"]
                if not item.get("data", {}).get("deleted")
                and not item.get("data", {}).get("parentItem")
                and collection in item.get("data", {}).get("collections", [])
            ]
            result["total"] = len(result["items"])
            return result
        if action != "list":
            raise OmniScholarError(
                "invalid_action", "Unknown Zotero collection action", category="validation"
            )
        return await self.list("/collections", limit=limit)

    async def search(
        self,
        query: str = "",
        *,
        collection_key: str | None = None,
        item_type: str | None = None,
        sort: str | None = None,
        direction: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        term = query.strip()
        browsing = not term or term == "*"
        params = {
            "q": None if browsing else term,
            "qmode": None if browsing else "everything",
            "itemType": item_type,
            "sort": sort or ("dateModified" if browsing else None),
            "direction": direction or ("desc" if browsing else None),
        }
        clean = {key: value for key, value in params.items() if value is not None}
        path = "/items" if item_type in {"attachment", "note", "annotation"} else "/items/top"
        if collection_key:
            collection = validate_zotero_key(collection_key, "Collection key")
            path = f"/collections/{collection}/items"
        return await self.list(path, params=clean, limit=limit)

    def _bounded_indexed_text(
        self, value: Any, remaining_bytes: int
    ) -> tuple[dict[str, Any], int]:
        if not isinstance(value, dict) or not isinstance(value.get("content"), str):
            raise OmniScholarError(
                "zotero_schema_mismatch",
                "Zotero returned malformed indexed text",
                category="provider",
            )
        raw = value["content"].encode("utf-8")
        prefix = raw[:remaining_bytes].decode("utf-8", errors="ignore")
        returned_bytes = len(prefix.encode("utf-8"))
        return (
            {
                "status": "available",
                "content": prefix,
                "indexedPages": value.get("indexedPages"),
                "totalPages": value.get("totalPages"),
                "bytes": returned_bytes,
                "originalBytes": len(raw),
                "truncated": returned_bytes < len(raw),
            },
            returned_bytes,
        )

    async def item(
        self, key: str, *, aggregate: bool = True, attachment_key: str | None = None
    ) -> dict[str, Any]:
        parent_key = validate_zotero_key(key)
        raw = await self._get(f"/items/{parent_key}")
        if not isinstance(raw, dict):
            raise OmniScholarError(
                "zotero_schema_mismatch",
                "Zotero returned a malformed item",
                category="provider",
            )
        if not aggregate:
            return raw
        data = raw.get("data", {}) if isinstance(raw.get("data"), dict) else {}
        if data.get("deleted") or data.get("itemType") in {"attachment", "note", "annotation"}:
            raise OmniScholarError(
                "invalid_zotero_item",
                "Requested item is not a bibliographic parent",
                category="validation",
            )
        children_result = await self.list(f"/items/{parent_key}/children", limit=self.max_items)
        children = children_result["items"]
        notes = [
            {
                "key": item.get("key"),
                "version": item.get("version"),
                "note": item.get("data", {}).get("note", ""),
            }
            for item in children
            if item.get("data", {}).get("itemType") == "note"
        ]
        attachments: list[dict[str, Any]] = []
        indexed_text_budget = self.max_indexed_text_bytes
        for item in children:
            attachment = item.get("data", {})
            if attachment.get("itemType") != "attachment":
                continue
            is_pdf = attachment.get("contentType") == "application/pdf" or str(
                attachment.get("filename", "")
            ).lower().endswith(".pdf")
            annotations: list[dict[str, Any]] = []
            indexed: dict[str, Any] = {"status": "unavailable"}
            local_path: str | None = None
            if is_pdf:
                descendants = await self.list(
                    f"/items/{item['key']}/children", limit=self.max_items
                )
                annotations = [
                    child
                    for child in descendants["items"]
                    if child.get("data", {}).get("itemType") == "annotation"
                ]
                try:
                    fulltext = await self._get(f"/items/{item['key']}/fulltext")
                    indexed, consumed = self._bounded_indexed_text(
                        fulltext, indexed_text_budget
                    )
                    indexed_text_budget -= consumed
                except OmniScholarError as error:
                    if error.http_status != 404:
                        raise
                local_path = await self._locate_attachment(item["key"])
            attachments.append(
                {
                    "key": item.get("key"),
                    "version": item.get("version"),
                    "title": attachment.get("title", ""),
                    "filename": attachment.get("filename"),
                    "contentType": attachment.get("contentType"),
                    "path": attachment.get("path"),
                    "md5": attachment.get("md5"),
                    "mtime": attachment.get("mtime"),
                    "indexedText": indexed,
                    "annotations": annotations,
                    "localPath": local_path,
                    "selected": False,
                }
            )
        pdfs = [
            item
            for item in attachments
            if item["contentType"] == "application/pdf"
            or str(item["filename"] or "").lower().endswith(".pdf")
        ]
        selected: dict[str, Any] | None
        if attachment_key:
            validate_zotero_key(attachment_key, "Attachment key")
            matches = [item for item in pdfs if item["key"] == attachment_key]
            if not matches:
                raise OmniScholarError(
                    "invalid_attachment",
                    "Selected attachment is not a child PDF",
                    category="validation",
                )
            selected = matches[0]
        else:
            selected = min(pdfs, key=lambda item: item["key"], default=None)
        if selected:
            selected["selected"] = True
        creators = data.get("creators", []) if isinstance(data.get("creators"), list) else []
        return {
            "zoteroKey": raw.get("key"),
            "zoteroVersion": raw.get("version"),
            "itemType": data.get("itemType"),
            "title": data.get("title") or "Untitled",
            "creators": creators,
            "metadata": data,
            "date": data.get("date"),
            "doi": data.get("DOI"),
            "isbn": data.get("ISBN"),
            "issn": data.get("ISSN"),
            "publicationTitle": data.get("publicationTitle") or data.get("proceedingsTitle"),
            "url": data.get("url"),
            "abstract": data.get("abstractNote"),
            "tags": data.get("tags", []),
            "collections": data.get("collections", []),
            "notes": notes,
            "annotations": [
                annotation for item in attachments for annotation in item["annotations"]
            ],
            "attachments": attachments,
            "selectedPdf": selected,
        }

    async def _locate_attachment(self, key: str) -> str | None:
        validate_zotero_key(key, "Attachment key")
        try:
            value = await self.transport.text(
                "GET", self._url(f"/items/{key}/file/view/url"), headers=self.headers
            )
        except OmniScholarError as error:
            if error.http_status == 404:
                return None
            raise
        parsed = urlparse(value.strip())
        if parsed.scheme != "file" or parsed.hostname not in {"", None, "localhost"}:
            raise OmniScholarError(
                "unsafe_attachment_url",
                "Zotero returned a non-local attachment URL",
                category="filesystem",
            )
        path = Path(
            unquote(
                parsed.path.lstrip("/") if re.match(r"^/[A-Za-z]:", parsed.path) else parsed.path
            )
        )
        return str(path.resolve()) if path.is_file() else None
