"""Recursive secret redaction used before every log, error, and tool result."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?:api[-_]?key|access[-_]?token|refresh[-_]?token|^token$|secret|password|authorization|private[-_]?key|client[-_]?secret)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/]+=*")
_QUERY_SECRET = re.compile(r"(?i)([?&](?:api_?key|key|token|access_token|secret)=)[^&#\s]+")
_HEADER_SECRET = re.compile(
    r"(?i)((?:authorization|x-api-key|api-key)\s*[:=]\s*)([^,;\s]+(?:\s+[^,;\s]+)?)"
)


def redact_text(value: str, known_secrets: Sequence[str] = ()) -> str:
    redacted = value
    for secret in sorted((item for item in known_secrets if item), key=len, reverse=True):
        redacted = redacted.replace(secret, _REDACTED)
    redacted = _BEARER.sub(f"Bearer {_REDACTED}", redacted)
    redacted = _QUERY_SECRET.sub(rf"\1{_REDACTED}", redacted)
    return _HEADER_SECRET.sub(rf"\1{_REDACTED}", redacted)


def redact(value: Any, known_secrets: Sequence[str] = ()) -> Any:
    """Return a deeply redacted copy without invoking secret-bearing reprs."""
    if isinstance(value, str):
        return redact_text(value, known_secrets)
    if isinstance(value, bytes):
        return _REDACTED
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            result[name] = _REDACTED if _SENSITIVE_KEY.search(name) else redact(item, known_secrets)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item, known_secrets) for item in value]
    return value
