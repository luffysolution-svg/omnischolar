"""MinerU Precision v4 parsing with deterministic cache and upload authorization."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from omnischolar.core import (
    OmniScholarError,
    ToolExecutionContext,
    atomic_write,
    read_file_bounded,
    temporary_path,
    validate_zip,
)

from .transport import ServiceTransport


@dataclass(slots=True)
class MinerUResult:
    markdown: str
    assets: dict[str, bytes] = field(default_factory=dict, repr=False)
    pdf_sha256: str = ""
    parse_key: str = ""
    batch_id: str | None = None
    parser_version: str | None = None
    model: str = "pipeline"
    cached: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "markdown": self.markdown,
            "assets": [{"name": name, "bytes": len(value)} for name, value in self.assets.items()],
            "pdfSha256": self.pdf_sha256,
            "parseKey": self.parse_key,
            "batchId": self.batch_id,
            "parserVersion": self.parser_version,
            "model": self.model,
            "cached": self.cached,
        }


class MinerUService:
    def __init__(
        self,
        transport: ServiceTransport,
        *,
        token: str,
        base_url: str = "https://mineru.net/api/v4",
        model: str = "pipeline",
        cache_directory: Path = Path(".omnischolar/mineru"),
        max_pdf_bytes: int = 200 * 1024 * 1024,
        max_archive_bytes: int = 512 * 1024 * 1024,
        poll_interval_seconds: float = 2,
        poll_timeout_seconds: float = 600,
        allow_external_upload: bool = False,
    ) -> None:
        if not token:
            raise OmniScholarError(
                "credential_required",
                "MinerU credential is not configured",
                category="authentication",
            )
        if model not in {"pipeline", "vlm", "MinerU-HTML"}:
            raise OmniScholarError("invalid_model", "Unsupported MinerU model", category="config")
        self.transport = transport
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.cache_directory = cache_directory
        self.max_pdf_bytes = min(max_pdf_bytes, 200 * 1024 * 1024)
        self.max_archive_bytes = max_archive_bytes
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.allow_external_upload = allow_external_upload

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def _data(payload: Any, stage: str) -> dict[str, Any]:
        if (
            not isinstance(payload, dict)
            or payload.get("code") not in {0, "0"}
            or not isinstance(payload.get("data"), dict)
        ):
            code = payload.get("code") if isinstance(payload, dict) else "malformed"
            raise OmniScholarError(
                "mineru_api_error", f"MinerU {stage} failed with code {code}", category="provider"
            )
        return cast(dict[str, Any], payload["data"])

    def _parse_key(self, pdf_sha256: str, options: dict[str, Any]) -> str:
        payload = {
            "pdfSha256": pdf_sha256,
            "backend": "mineru-precision-v4",
            "model": self.model,
            "options": options,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _cache_paths(self, pdf_sha256: str, parse_key: str) -> tuple[Path, Path]:
        directory = self.cache_directory / pdf_sha256[:2] / pdf_sha256
        return directory / f"{parse_key}.zip", directory / f"{parse_key}.json"

    async def parse_pdf(
        self,
        pdf_path: Path,
        context: ToolExecutionContext,
        *,
        language: str = "en",
        enable_formula: bool = True,
        enable_table: bool = True,
        is_ocr: bool = False,
        force: bool = False,
    ) -> MinerUResult:
        context.check_cancelled()
        pdf = await read_file_bounded(pdf_path, self.max_pdf_bytes)
        if not pdf.startswith(b"%PDF-"):
            raise OmniScholarError(
                "invalid_pdf", "Selected attachment is not a PDF", category="validation"
            )
        pdf_hash = hashlib.sha256(pdf).hexdigest()
        options = {
            "language": language,
            "enableFormula": enable_formula,
            "enableTable": enable_table,
            "isOcr": is_ocr,
        }
        parse_key = self._parse_key(pdf_hash, options)
        archive_path, metadata_path = self._cache_paths(pdf_hash, parse_key)
        if not force and archive_path.is_file() and metadata_path.is_file():
            metadata = json.loads(await read_file_bounded(metadata_path, 1024 * 1024))
            return self._normalize_archive(archive_path, pdf_hash, parse_key, metadata, cached=True)
        if not self.allow_external_upload:
            raise OmniScholarError(
                "upload_disabled",
                "MinerU uploads are disabled by configuration",
                category="authorization",
            )
        context.require_external_upload("MinerU")
        await context.progress(0, 4, "requesting signed upload")
        request = {
            "files": [{"name": pdf_path.name, "data_id": parse_key[:32], "is_ocr": is_ocr}],
            "model_version": self.model,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "language": language,
        }
        creation = self._data(
            await self.transport.json(
                "POST", f"{self.base_url}/file-urls/batch", headers=self.headers, body=request
            ),
            "task creation",
        )
        batch_id = str(creation.get("batch_id", ""))
        urls = creation.get("file_urls")
        signed_url = urls[0] if isinstance(urls, list) and urls and isinstance(urls[0], str) else ""
        if not batch_id or not signed_url:
            raise OmniScholarError(
                "ambiguous_submission",
                "MinerU task creation response was incomplete; do not resubmit automatically",
                category="provider",
            )
        self._validate_remote_url(signed_url, "signed upload URL")
        await context.progress(1, 4, "uploading PDF")
        await self.transport.bytes("PUT", signed_url, content=pdf, max_response_bytes=1024 * 1024)
        await context.progress(2, 4, "waiting for extraction")
        deadline = time.monotonic() + self.poll_timeout_seconds
        completed: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            context.check_cancelled()
            polled = self._data(
                await self.transport.json(
                    "GET", f"{self.base_url}/extract-results/batch/{batch_id}", headers=self.headers
                ),
                "poll",
            )
            rows = polled.get("extract_result")
            candidates = rows if isinstance(rows, list) else []
            row = next(
                (
                    item
                    for item in candidates
                    if isinstance(item, dict) and item.get("data_id") == parse_key[:32]
                ),
                None,
            )
            if row is None and candidates and isinstance(candidates[0], dict):
                row = candidates[0]
            if row is None:
                raise OmniScholarError(
                    "mineru_schema_mismatch",
                    "MinerU poll response omitted the submitted file",
                    category="provider",
                )
            state = row.get("state")
            if state == "failed":
                raise OmniScholarError(
                    "mineru_parse_failed", "MinerU reported extraction failure", category="provider"
                )
            if state == "done":
                completed = row
                break
            await asyncio.sleep(self.poll_interval_seconds)
        if completed is None:
            raise OmniScholarError(
                "mineru_poll_timeout",
                "MinerU extraction did not finish before the deadline",
                category="network",
                retryable=True,
            )
        archive_url = completed.get("full_zip_url")
        if not isinstance(archive_url, str):
            raise OmniScholarError(
                "mineru_schema_mismatch",
                "MinerU completed without an archive URL",
                category="provider",
            )
        self._validate_remote_url(archive_url, "result archive URL")
        await context.progress(3, 4, "downloading result")
        archive = await self.transport.bytes(
            "GET", archive_url, max_response_bytes=self.max_archive_bytes
        )
        async with temporary_path(suffix=".zip") as candidate:
            await atomic_write(candidate.parent, candidate.name, archive)
            validate_zip(candidate, max_uncompressed_bytes=self.max_archive_bytes)
            await atomic_write(archive_path.parent, archive_path.name, archive)
        metadata = {
            "batchId": batch_id,
            "parserVersion": completed.get("version"),
            "model": completed.get("model_version") or self.model,
            "pdfSha256": pdf_hash,
            "parseKey": parse_key,
            "options": options,
        }
        await atomic_write(
            metadata_path.parent, metadata_path.name, json.dumps(metadata, sort_keys=True).encode()
        )
        await context.progress(4, 4, "complete")
        return self._normalize_archive(archive_path, pdf_hash, parse_key, metadata, cached=False)

    @staticmethod
    def _validate_remote_url(value: str, label: str) -> None:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise OmniScholarError(
                "unsafe_remote_url",
                f"MinerU {label} is not a safe HTTPS URL",
                category="authorization",
            )

    def _normalize_archive(
        self,
        archive_path: Path,
        pdf_hash: str,
        parse_key: str,
        metadata: dict[str, Any],
        *,
        cached: bool,
    ) -> MinerUResult:
        validate_zip(archive_path, max_uncompressed_bytes=self.max_archive_bytes)
        assets: dict[str, bytes] = {}
        markdown_candidates: list[tuple[str, str]] = []
        with zipfile.ZipFile(archive_path) as handle:
            for entry in handle.infolist():
                if entry.is_dir():
                    continue
                content = handle.read(entry)
                name = entry.filename.replace("\\", "/")
                if name.lower().endswith(".md"):
                    markdown_candidates.append((name, content.decode("utf-8", errors="replace")))
                elif any(part in name.lower() for part in ("image", "figure", "table", "equation")):
                    assets[name] = content
        if not markdown_candidates:
            raise OmniScholarError(
                "mineru_missing_markdown",
                "MinerU archive contains no Markdown",
                category="provider",
            )
        markdown_candidates.sort(
            key=lambda item: (not item[0].lower().endswith("full.md"), -len(item[1]))
        )
        return MinerUResult(
            markdown_candidates[0][1],
            assets,
            pdf_hash,
            parse_key,
            metadata.get("batchId"),
            metadata.get("parserVersion"),
            metadata.get("model", self.model),
            cached,
        )
