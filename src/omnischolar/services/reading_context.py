"""Persistent, bounded evidence contexts for multi-turn paper work."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omnischolar.core import OmniScholarError, atomic_write, read_file_bounded


_CONTEXT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ReadingContextStore:
    """Store only selected evidence, never a complete parsed document."""

    def __init__(
        self,
        root: Path,
        *,
        max_contexts: int = 32,
        max_items: int = 100,
        max_chars: int = 48_000,
    ) -> None:
        self.root = root.resolve()
        self.path = self.root / ".omnischolar" / "reading-contexts.json"
        self.max_contexts = max(1, min(max_contexts, 128))
        self.max_items = max(1, min(max_items, 500))
        self.max_chars = max(1_000, min(max_chars, 512_000))

    async def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "contexts": {}}
        raw = await read_file_bounded(self.path, 8 * 1024 * 1024)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OmniScholarError(
                "reading_context_corrupt",
                "The local reading context cache is not valid JSON",
                category="filesystem",
                cause=exc,
            ) from exc
        if not isinstance(value, dict) or not isinstance(value.get("contexts"), dict):
            raise OmniScholarError(
                "reading_context_corrupt",
                "The local reading context cache has an invalid shape",
                category="filesystem",
            )
        return value

    async def _save(self, value: dict[str, Any]) -> None:
        await atomic_write(
            self.root,
            ".omnischolar/reading-contexts.json",
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )

    @staticmethod
    def _validate_id(value: str) -> str:
        if not _CONTEXT_ID.fullmatch(value):
            raise OmniScholarError(
                "invalid_context_id",
                "contextId must contain 1-64 letters, digits, underscores, or hyphens",
                category="validation",
            )
        return value

    def _new_id(self) -> str:
        return f"ctx-{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _bounded_item(self, item: dict[str, Any]) -> dict[str, Any]:
        raw_text = item.get("text", item.get("excerpt", ""))
        text = str(raw_text)[:4_000]
        if not text:
            raise OmniScholarError(
                "context_item_empty", "Every context item must contain non-empty text", category="validation"
            )
        source = item.get("source")
        if not isinstance(source, dict):
            source = {
                key: item[key]
                for key in ("zoteroKey", "title", "heading", "locator", "markdownPath")
                if key in item
            }
        clean_source = {
            str(key): str(value)[:500]
            for key, value in source.items()
            if value is not None and isinstance(key, str)
        }
        return {"text": text, "source": clean_source}

    @staticmethod
    def _summary(context: dict[str, Any]) -> dict[str, Any]:
        items = context.get("items", [])
        return {
            "contextId": context.get("contextId"),
            "title": context.get("title"),
            "createdAt": context.get("createdAt"),
            "updatedAt": context.get("updatedAt"),
            "itemCount": len(items) if isinstance(items, list) else 0,
            "totalChars": sum(
                len(str(item.get("text", ""))) for item in items if isinstance(item, dict)
            ),
        }

    async def add_items(
        self, context_id: str, items: list[dict[str, Any]], *, title: str | None = None
    ) -> dict[str, Any]:
        context_id = self._validate_id(context_id)
        if not items:
            return {"contextId": context_id, "added": 0}
        document = await self._load()
        contexts = document.setdefault("contexts", {})
        context = contexts.setdefault(
            context_id,
            {
                "contextId": context_id,
                "title": title or "Reading context",
                "createdAt": self._now(),
                "updatedAt": self._now(),
                "items": [],
            },
        )
        if title:
            context["title"] = title[:200]
        existing = context.setdefault("items", [])
        if not isinstance(existing, list):
            existing = []
            context["items"] = existing
        bounded = [self._bounded_item(item) for item in items[: self.max_items]]
        existing.extend(bounded)
        while len(existing) > self.max_items:
            existing.pop(0)
        while sum(len(str(item.get("text", ""))) for item in existing) > self.max_chars:
            existing.pop(0)
        context["updatedAt"] = self._now()
        self._trim_contexts(contexts)
        await self._save(document)
        return {**self._summary(context), "added": len(bounded)}

    def _trim_contexts(self, contexts: dict[str, Any]) -> None:
        if len(contexts) <= self.max_contexts:
            return
        ordered = sorted(
            contexts.items(),
            key=lambda pair: str(pair[1].get("updatedAt", ""))
            if isinstance(pair[1], dict)
            else "",
        )
        for context_id, _ in ordered[: len(contexts) - self.max_contexts]:
            contexts.pop(context_id, None)

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        action = arguments["action"]
        if action == "open":
            context_id = self._validate_id(arguments.get("contextId") or self._new_id())
            document = await self._load()
            contexts = document.setdefault("contexts", {})
            context = contexts.setdefault(
                context_id,
                {
                    "contextId": context_id,
                    "title": str(arguments.get("title") or "Reading context")[:200],
                    "createdAt": self._now(),
                    "updatedAt": self._now(),
                    "items": [],
                },
            )
            self._trim_contexts(contexts)
            await self._save(document)
            return self._summary(context)
        if action == "add":
            context_id = arguments.get("contextId")
            if not isinstance(context_id, str):
                raise OmniScholarError(
                    "context_id_required", "The add action requires contextId", category="validation"
                )
            items = arguments.get("items")
            if not isinstance(items, list):
                raise OmniScholarError(
                    "context_items_required", "The add action requires an items array", category="validation"
                )
            return await self.add_items(context_id, items, title=arguments.get("title"))
        if action == "list":
            document = await self._load()
            contexts = document.get("contexts", {})
            return {
                "contexts": [self._summary(value) for value in contexts.values() if isinstance(value, dict)]
            }
        context_id = arguments.get("contextId")
        if not isinstance(context_id, str):
            raise OmniScholarError(
                "context_id_required", f"The {action} action requires contextId", category="validation"
            )
        context_id = self._validate_id(context_id)
        document = await self._load()
        contexts = document.get("contexts", {})
        context = contexts.get(context_id)
        if not isinstance(context, dict):
            raise OmniScholarError(
                "context_not_found", f"No reading context exists for {context_id}", category="filesystem"
            )
        if action == "clear":
            contexts.pop(context_id, None)
            await self._save(document)
            return {"contextId": context_id, "cleared": True}
        if action != "get":
            raise OmniScholarError(
                "invalid_context_action", f"Unknown context action: {action}", category="validation"
            )
        items = context.get("items", [])
        if not isinstance(items, list):
            items = []
        cursor = max(0, int(arguments.get("cursor", 0)))
        max_items = max(1, min(int(arguments.get("maxItems", 20)), 50))
        max_chars = max(500, min(int(arguments.get("maxChars", 8_000)), 12_000))
        returned: list[dict[str, Any]] = []
        returned_chars = 0
        index = cursor
        while index < len(items) and len(returned) < max_items:
            item = items[index]
            if not isinstance(item, dict):
                index += 1
                continue
            text = str(item.get("text", ""))
            remaining = max_chars - returned_chars
            if remaining <= 0:
                break
            bounded = text[:remaining]
            returned.append({**item, "text": bounded})
            returned_chars += len(bounded)
            index += 1
            if len(bounded) < len(text):
                break
        return {
            **self._summary(context),
            "cursor": cursor,
            "nextCursor": index if index < len(items) else None,
            "hasMore": index < len(items),
            "returnedChars": returned_chars,
            "truncated": returned_chars < sum(
                len(str(item.get("text", ""))) for item in items[cursor:index] if isinstance(item, dict)
            )
            or index < len(items),
            "items": returned,
        }
