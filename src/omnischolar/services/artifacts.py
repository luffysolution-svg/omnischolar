"""Shared secure extraction and persistence for generated image artifacts."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import mimetypes
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from omnischolar.core import OmniScholarError, atomic_write

from .transport import ServiceTransport

UrlValidator = Callable[[str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class SavedImagePayload:
    artifacts: list[dict[str, Any]]
    sanitized_payload: Any


@dataclass(frozen=True, slots=True)
class _Candidate:
    source: str
    content: bytes | None
    mime_hint: str


def image_mime(content: bytes) -> str | None:
    """Return a supported image MIME type based only on magic bytes."""

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if (
        len(content) >= 12
        and content[4:8] == b"ftyp"
        and content[8:12]
        in {
            b"avif",
            b"avis",
        }
    ):
        return "image/avif"
    return None


async def validate_public_https(value: str) -> None:
    """Reject credentials, non-HTTPS URLs, and non-public DNS results."""

    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise OmniScholarError(
            "unsafe_remote_url",
            "Remote artifact/reference must be an HTTPS URL without credentials",
            category="authorization",
        )
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        raise OmniScholarError(
            "dns_failed",
            "Remote artifact host could not be resolved",
            category="network",
            retryable=True,
            cause=exc,
        ) from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise OmniScholarError(
                "ssrf_blocked",
                "Remote artifact/reference resolves to a non-public address",
                category="authorization",
            )


def _decode_base64(value: str, max_bytes: int) -> bytes:
    max_encoded = ((max_bytes + 2) // 3) * 4 + 4
    if len(value) > max_encoded:
        raise OmniScholarError(
            "artifact_too_large",
            "Generated base64 artifact exceeds its configured limit",
            category="limits",
        )
    return base64.b64decode(value, validate=True)


def _extract(payload: Any, max_bytes: int) -> tuple[list[_Candidate], dict[str, str]]:
    found: list[_Candidate] = []
    seen: set[str] = set()
    redactions: dict[str, str] = {}

    def append(source: str, content: bytes | None, mime: object, replacement: str) -> None:
        identity = source if content is None else hashlib.sha256(content).hexdigest()
        redactions[source] = replacement
        if identity in seen:
            return
        seen.add(identity)
        found.append(
            _Candidate(
                source,
                content,
                str(mime) if isinstance(mime, str) else "image/png",
            )
        )

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            encoded = value.get("b64_json")
            if isinstance(encoded, str):
                append(
                    encoded,
                    _decode_base64(encoded, max_bytes),
                    "image/png",
                    "[saved to local artifact]",
                )
            inline = value.get("inlineData") or value.get("inline_data")
            if isinstance(inline, dict) and isinstance(inline.get("data"), str):
                inline_data = inline["data"]
                append(
                    inline_data,
                    _decode_base64(inline_data, max_bytes),
                    inline.get("mimeType") or inline.get("mime_type") or "image/png",
                    "[saved to local artifact]",
                )
            mime = value.get("content_type") or value.get("mimeType") or value.get("mime_type")
            for child_key, item in value.items():
                normalized = child_key.lower().replace("-", "").replace("_", "")
                artifact_key = normalized in {"url", "image", "imageurl", "fileurl"}
                if isinstance(item, str) and artifact_key and item.startswith("https://"):
                    append(
                        item,
                        None,
                        mime or "image/png",
                        "[downloaded to local artifact]",
                    )
                elif isinstance(item, str) and artifact_key and item.startswith("data:image/"):
                    metadata, separator, encoded_data = item.partition(",")
                    if not separator or not metadata.endswith(";base64"):
                        raise ValueError("invalid image data URI")
                    append(
                        item,
                        _decode_base64(encoded_data, max_bytes),
                        metadata[5:].removesuffix(";base64"),
                        "[saved to local artifact]",
                    )
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    try:
        visit(payload)
    except (ValueError, TypeError) as exc:
        raise OmniScholarError(
            "invalid_image_payload",
            "Provider returned invalid base64 image data",
            category="provider",
            cause=exc,
        ) from exc
    return found, redactions


def _sanitize(payload: Any, redactions: dict[str, str]) -> Any:
    if isinstance(payload, str):
        return redactions.get(payload, payload)
    if isinstance(payload, list):
        return [_sanitize(item, redactions) for item in payload]
    if isinstance(payload, dict):
        return {key: _sanitize(value, redactions) for key, value in payload.items()}
    return payload


async def save_image_payload(
    transport: ServiceTransport,
    payload: Any,
    *,
    output_root: Path,
    directory: str,
    name_prefix: str,
    max_bytes: int,
    timeout_seconds: float = 120,
    url_validator: UrlValidator = validate_public_https,
) -> SavedImagePayload:
    """Extract, validate, atomically save, and redact image artifacts."""

    candidates, redactions = _extract(payload, max_bytes)
    if not candidates:
        raise OmniScholarError(
            "image_artifact_missing",
            "Provider response did not contain a generated image artifact",
            category="provider",
        )
    artifacts: list[dict[str, Any]] = []
    created: list[Path] = []
    try:
        for index, candidate in enumerate(candidates, 1):
            content = candidate.content
            if content is None:
                await url_validator(candidate.source)
                content = await transport.bytes(
                    "GET",
                    candidate.source,
                    max_response_bytes=max_bytes,
                    timeout_seconds=timeout_seconds,
                )
            if len(content) > max_bytes:
                raise OmniScholarError(
                    "artifact_too_large",
                    "Generated artifact exceeds its configured limit",
                    category="limits",
                )
            mime = image_mime(content)
            if mime is None:
                raise OmniScholarError(
                    "artifact_integrity_failed",
                    "Generated artifact does not have a supported image signature",
                    category="provider",
                )
            extension = mimetypes.guess_extension(mime) or ".bin"
            relative = f"{directory}/{name_prefix}-{uuid4().hex[:12]}-{index:02d}{extension}"
            path = await atomic_write(output_root, relative, content)
            created.append(path)
            artifacts.append({"path": str(path), "bytes": len(content), "mimeType": mime})
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return SavedImagePayload(artifacts, _sanitize(payload, redactions))
