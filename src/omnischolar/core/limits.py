"""Unified result shaping and deterministic output limits."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any


def jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return jsonable(value.model_dump(mode="json", by_alias=True, exclude_none=True))
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    return value


def _utf8_prefix(text: str, limit: int) -> str:
    if len(text.encode("utf-8")) <= limit:
        return text
    encoded = text.encode("utf-8")[:limit]
    return encoded.decode("utf-8", errors="ignore")


def truncate_output(value: Any, *, max_bytes: int, max_lines: int) -> dict[str, Any]:
    """Serialize and limit any result while reporting exact truncation metadata."""
    normalized = jsonable(value)
    text = json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True)
    original_bytes = len(text.encode("utf-8"))
    original_lines = text.count("\n") + 1
    lines = text.splitlines()
    limited = "\n".join(lines[:max_lines])
    limited = _utf8_prefix(limited, max_bytes)
    truncated = original_bytes > len(limited.encode("utf-8")) or original_lines > max_lines
    if not truncated:
        return {
            "value": normalized,
            "truncated": False,
            "bytes": original_bytes,
            "lines": original_lines,
        }
    return {
        "value": limited,
        "truncated": True,
        "bytes": len(limited.encode("utf-8")),
        "lines": limited.count("\n") + 1 if limited else 0,
        "originalBytes": original_bytes,
        "originalLines": original_lines,
        "format": "truncated-json-text",
    }
