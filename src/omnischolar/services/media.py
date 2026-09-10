"""Capability-driven scientific image routing with explicit upload and paid gates."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urljoin, urlparse

from omnischolar.core import (
    OmniScholarError,
    ToolExecutionContext,
    confined_input,
    read_file_bounded,
)

from .artifacts import save_image_payload, validate_public_https
from .transport import ServiceTransport

Capability = Literal["text-to-image", "image-to-image", "edit", "multi-reference"]

# Exact curated descriptors are fallbacks, not model-name heuristics.
CURATED_MODELS: dict[str, dict[str, set[Capability]]] = {
    "openai": {
        "gpt-image-1": {"text-to-image", "image-to-image", "edit", "multi-reference"},
        "gpt-image-1.5": {"text-to-image", "image-to-image", "edit", "multi-reference"},
    },
    "google": {
        "gemini-2.5-flash-image": {"text-to-image", "image-to-image", "edit", "multi-reference"},
    },
    "gemini": {
        "gemini-2.5-flash-image": {"text-to-image", "image-to-image", "edit", "multi-reference"},
    },
    "fal": {
        "fal-ai/flux/schnell": {"text-to-image"},
        "alibaba/qwen-image-3/edit": {"image-to-image", "edit", "multi-reference"},
    },
    "dashscope": {
        "qwen-image-plus": {"text-to-image"},
        "qwen-image-2.0": {"text-to-image", "image-to-image", "edit", "multi-reference"},
    },
    "qwen-cloud": {
        "qwen-image-plus": {"text-to-image"},
        "qwen-image-2.0": {"text-to-image", "image-to-image", "edit", "multi-reference"},
    },
}

_DASHSCOPE_WORKSPACE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}")
_DEPRECATED_DASHSCOPE_BASES = {
    "https://dashscope.aliyuncs.com",
    "https://dashscope.aliyuncs.com/api/v1",
    "https://dashscope-intl.aliyuncs.com",
    "https://dashscope-intl.aliyuncs.com/api/v1",
}

CATALOG_URLS = {
    "openai": "https://api.openai.com/v1/models",
    "xai": "https://api.x.ai/v1/models",
    "google": "https://generativelanguage.googleapis.com/v1beta/models",
}


@dataclass(slots=True)
class MediaProviderSettings:
    id: str
    enabled: bool
    api_key: str | None
    base_url: str | None = None
    models: dict[str, set[Capability]] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    provider: str
    id: str
    capabilities: tuple[Capability, ...]
    source: Literal[
        "config_pin", "official_catalog+curated", "curated_fallback", "official_catalog"
    ]
    usable: bool
    unavailable_reason: str | None = None


class MediaService:
    def __init__(
        self,
        transport: ServiceTransport,
        providers: list[MediaProviderSettings],
        *,
        output_root: Path,
        workspace_roots: tuple[Path, ...],
        allow_external_upload: bool = False,
        allow_paid: bool = False,
        max_input_bytes: int = 25 * 1024 * 1024,
        max_artifact_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self.transport = transport
        self.providers = {provider.id: provider for provider in providers}
        self.output_root = output_root
        self.workspace_roots = workspace_roots
        self.allow_external_upload = allow_external_upload
        self.allow_paid = allow_paid
        self.max_input_bytes = max_input_bytes
        self.max_artifact_bytes = max_artifact_bytes

    def _provider(self, provider_id: str) -> MediaProviderSettings:
        provider = self.providers.get(provider_id)
        if provider is None:
            raise OmniScholarError(
                "unknown_provider", f"Unknown image provider: {provider_id}", category="validation"
            )
        if not provider.enabled:
            raise OmniScholarError(
                "provider_unavailable",
                f"Image provider {provider_id} is disabled",
                category="provider",
            )
        if not provider.api_key and provider_id not in {"vertex"}:
            raise OmniScholarError(
                "credential_required",
                f"Image provider {provider_id} has no credential",
                category="authentication",
            )
        return provider

    async def models(
        self, provider_id: str | None = None, *, discover: bool = False
    ) -> list[ModelDescriptor]:
        selected = (
            [self._provider(provider_id)]
            if provider_id
            else [item for item in self.providers.values() if item.enabled]
        )
        descriptors: list[ModelDescriptor] = []
        for provider in selected:
            pins = provider.models
            contract_error = self._provider_contract_error(provider)
            contract_ready = contract_error is None
            catalog_ids: set[str] = set()
            if discover and provider.id in CATALOG_URLS and provider.api_key:
                catalog_ids = await self._discover_catalog(provider)
            for model_id, capabilities in pins.items():
                descriptors.append(
                    ModelDescriptor(
                        provider.id,
                        model_id,
                        tuple(sorted(capabilities)),
                        "config_pin",
                        contract_ready,
                        contract_error,
                    )
                )
            curated = CURATED_MODELS.get(provider.id, {})
            for model_id, capabilities in curated.items():
                if model_id in pins:
                    continue
                source: Literal["official_catalog+curated", "curated_fallback"] = (
                    "official_catalog+curated" if model_id in catalog_ids else "curated_fallback"
                )
                descriptors.append(
                    ModelDescriptor(
                        provider.id,
                        model_id,
                        tuple(sorted(capabilities)),
                        source,
                        contract_ready,
                        contract_error,
                    )
                )
            for model_id in sorted(catalog_ids - set(pins) - set(curated)):
                descriptors.append(
                    ModelDescriptor(
                        provider.id,
                        model_id,
                        (),
                        "official_catalog",
                        False,
                        "model_capabilities_unpinned",
                    )
                )
        return descriptors

    @staticmethod
    def _provider_contract_error(provider: MediaProviderSettings) -> str | None:
        if provider.id not in {"dashscope", "qwen", "qwen-cloud"}:
            return None
        configured_base = provider.base_url.rstrip("/") if provider.base_url else None
        if configured_base and configured_base not in _DEPRECATED_DASHSCOPE_BASES:
            return None
        workspace = provider.options.get("workspace")
        if isinstance(workspace, str) and _DASHSCOPE_WORKSPACE.fullmatch(workspace) is not None:
            return None
        return "dashscope_workspace_required"

    @classmethod
    def _provider_contract_ready(cls, provider: MediaProviderSettings) -> bool:
        return cls._provider_contract_error(provider) is None

    async def _discover_catalog(self, provider: MediaProviderSettings) -> set[str]:
        url = CATALOG_URLS[provider.id]
        if provider.id == "google":
            payload = await self.transport.json("GET", url, params={"key": provider.api_key})
            values = payload.get("models", []) if isinstance(payload, dict) else []
            return {
                str(item.get("name", "")).removeprefix("models/")
                for item in values
                if isinstance(item, dict) and item.get("name")
            }
        payload = await self.transport.json(
            "GET", url, headers={"Authorization": f"Bearer {provider.api_key}"}
        )
        values = payload.get("data", []) if isinstance(payload, dict) else []
        return {str(item.get("id")) for item in values if isinstance(item, dict) and item.get("id")}

    async def execute(
        self,
        *,
        provider_id: str,
        capability: Capability,
        prompt: str,
        context: ToolExecutionContext,
        model: str | None = None,
        references: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = self._provider(provider_id)
        if not self._provider_contract_ready(provider):
            raise OmniScholarError(
                "dashscope_workspace_required",
                "DashScope current image API requires a workspace-scoped endpoint",
                category="config",
            )
        descriptors = await self.models(provider_id)
        available = [
            item for item in descriptors if capability in item.capabilities and item.usable
        ]
        selected_model = (
            next((item for item in available if item.id == model), None)
            if model
            else (available[0] if available else None)
        )
        if selected_model is None:
            raise OmniScholarError(
                "model_capability_unavailable",
                f"No pinned/catalogued {provider_id} model supports {capability}",
                category="capability",
            )
        if not self.allow_paid:
            raise OmniScholarError(
                "paid_disabled",
                "Image generation is disabled by configuration",
                category="authorization",
            )
        context.require_paid(f"{provider_id} image generation")
        resolved = await self._resolve_references(references or [], context)
        if capability != "text-to-image" and not resolved:
            raise OmniScholarError(
                "reference_required",
                f"{capability} requires at least one reference image",
                category="validation",
            )
        if len(resolved) > 1 and "multi-reference" not in selected_model.capabilities:
            raise OmniScholarError(
                "model_capability_unavailable",
                f"Model {selected_model.id} does not support multiple references",
                category="capability",
            )
        request_options = self._validated_request_options(options or {})
        await context.progress(0, 2, "submitting image operation")
        payload = await self._call_provider(
            provider, selected_model.id, capability, prompt, resolved, request_options
        )
        await context.progress(1, 2, "saving image artifacts")
        artifacts, sanitized_payload = await self._save_artifacts(payload, provider.id)
        await context.progress(2, 2, "complete")
        return {
            "provider": provider.id,
            "model": selected_model.id,
            "capability": capability,
            "artifacts": artifacts,
            "providerResult": sanitized_payload,
            "scientificIntegrityWarning": "AI-generated scientific images are illustrative drafts, not experimental results or measured data. Verify every label, structure, mechanism, and quantitative claim.",
        }

    async def _resolve_references(
        self, references: list[str], context: ToolExecutionContext
    ) -> list[tuple[str, bytes | None, str]]:
        resolved: list[tuple[str, bytes | None, str]] = []
        if references:
            if not self.allow_external_upload:
                raise OmniScholarError(
                    "upload_disabled",
                    "Reference image upload is disabled by configuration",
                    category="authorization",
                )
            context.require_external_upload("image provider")
        for value in references:
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"}:
                await self._validate_public_https(value)
                resolved.append((value, None, "application/octet-stream"))
                continue
            path = confined_input(Path(value), self.workspace_roots)
            content = await read_file_bounded(path, self.max_input_bytes)
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if not mime.startswith("image/"):
                raise OmniScholarError(
                    "unsupported_media_type",
                    f"Reference {path.name} is not an image",
                    category="validation",
                )
            resolved.append((path.name, content, mime))
        return resolved

    @staticmethod
    def _validated_request_options(options: dict[str, Any]) -> dict[str, Any]:
        forbidden = {
            "apikey",
            "authorization",
            "baseurl",
            "endpoint",
            "generationendpoint",
            "editendpoint",
            "headers",
            "images",
            "imageurls",
            "model",
            "prompt",
            "token",
        }
        for key in options:
            normalized = key.lower().replace("-", "").replace("_", "")
            if normalized in forbidden:
                raise OmniScholarError(
                    "reserved_provider_option",
                    f"options.{key} is reserved; use the typed tool parameter or provider config",
                    category="validation",
                )
        return dict(options)

    async def _call_provider(
        self,
        provider: MediaProviderSettings,
        model: str,
        capability: Capability,
        prompt: str,
        references: list[tuple[str, bytes | None, str]],
        options: dict[str, Any],
    ) -> Any:
        if provider.id in {"openai", "custom"}:
            base = provider.base_url or "https://api.openai.com/v1"
            headers = {"Authorization": f"Bearer {provider.api_key}"}
            if references:
                endpoint = self._relative_endpoint(
                    base, provider.options.get("editEndpoint", "images/edits")
                )
                files = [
                    (
                        "image[]",
                        (
                            name,
                            content
                            or await self.transport.bytes(
                                "GET", name, max_response_bytes=self.max_input_bytes
                            ),
                            mime,
                        ),
                    )
                    for name, content, mime in references
                ]
                data = {
                    "model": model,
                    "prompt": prompt,
                    **{key: str(value) for key, value in options.items()},
                }
                return await self.transport.multipart(
                    "POST", endpoint, headers=headers, data=data, files=files
                )
            endpoint = self._relative_endpoint(
                base, provider.options.get("generationEndpoint", "images/generations")
            )
            return await self.transport.json(
                "POST",
                endpoint,
                headers=headers,
                body={**options, "model": model, "prompt": prompt, "response_format": "b64_json"},
            )
        if provider.id == "xai":
            base = provider.base_url or "https://api.x.ai/v1"
            endpoint = self._relative_endpoint(
                base, provider.options.get("generationEndpoint", "images/generations")
            )
            body = {**options, "model": model, "prompt": prompt}
            if references:
                body["images"] = [
                    self._data_uri(name, content, mime) if content else name
                    for name, content, mime in references
                ]
            return await self.transport.json(
                "POST", endpoint, headers={"Authorization": f"Bearer {provider.api_key}"}, body=body
            )
        if provider.id in {"google", "gemini"}:
            base = provider.base_url or "https://generativelanguage.googleapis.com/v1beta"
            endpoint = self._relative_endpoint(
                base, f"models/{quote(model, safe='')}:generateContent"
            )
            parts: list[dict[str, Any]] = [{"text": prompt}]
            parts.extend(
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(content).decode()}}
                if content
                else {"file_data": {"mime_type": mime, "file_uri": name}}
                for name, content, mime in references
            )
            return await self.transport.json(
                "POST",
                endpoint,
                params={"key": provider.api_key},
                body={
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], **options},
                },
            )
        if provider.id == "vertex":
            project, location = (
                provider.options.get("project"),
                provider.options.get("location", "us-central1"),
            )
            if not project:
                raise OmniScholarError(
                    "vertex_project_required",
                    "Vertex provider requires project configuration",
                    category="config",
                )
            base = (
                provider.base_url
                or f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models"
            )
            endpoint = self._relative_endpoint(base, f"{quote(model, safe='')}:predict")
            return await self.transport.json(
                "POST",
                endpoint,
                headers={"Authorization": f"Bearer {provider.api_key}"},
                body={
                    "instances": [
                        {
                            "prompt": prompt,
                            "references": [
                                self._data_uri(name, content, mime) if content else name
                                for name, content, mime in references
                            ],
                        }
                    ],
                    "parameters": options,
                },
            )
        if provider.id == "fal":
            return await self._call_fal(provider, model, prompt, references, options)
        if provider.id in {"dashscope", "qwen", "qwen-cloud"}:
            return await self._call_dashscope(provider, model, prompt, references, options)
        if provider.id == "atlas":
            if not provider.base_url:
                raise OmniScholarError(
                    "provider_base_url_required", "Atlas baseUrl is required", category="config"
                )
            endpoint = self._relative_endpoint(
                provider.base_url, provider.options.get("generationEndpoint", "images/generations")
            )
            return await self.transport.json(
                "POST",
                endpoint,
                headers={"Authorization": f"Bearer {provider.api_key}"},
                body={
                    "model": model,
                    "prompt": prompt,
                    "images": [
                        self._data_uri(name, content, mime) if content else name
                        for name, content, mime in references
                    ],
                    **options,
                },
            )
        raise OmniScholarError(
            "unsupported_provider",
            f"No adapter is implemented for {provider.id}",
            category="capability",
        )

    async def _call_fal(
        self,
        provider: MediaProviderSettings,
        model: str,
        prompt: str,
        references: list[tuple[str, bytes | None, str]],
        options: dict[str, Any],
    ) -> Any:
        if model == "fal-ai/flux/schnell" and references:
            raise OmniScholarError(
                "model_capability_unavailable",
                "fal-ai/flux/schnell does not accept reference images",
                category="capability",
            )
        if model == "alibaba/qwen-image-3/edit" and not 1 <= len(references) <= 3:
            raise OmniScholarError(
                "reference_count_invalid",
                "alibaba/qwen-image-3/edit requires one to three reference images",
                category="validation",
            )
        base = provider.base_url or "https://queue.fal.run"
        endpoint = self._relative_endpoint(base, model)
        headers = {"Authorization": f"Key {provider.api_key}"}
        body = self._payload_options(options)
        body["prompt"] = prompt
        if references:
            body["image_urls"] = [
                self._data_uri(name, content, mime) if content else name
                for name, content, mime in references
            ]
        submitted = await self.transport.json(
            "POST",
            endpoint,
            headers=headers,
            body=body,
            timeout_seconds=60,
            max_response_bytes=1024 * 1024,
        )
        if not isinstance(submitted, dict):
            raise OmniScholarError(
                "invalid_job_response",
                "fal returned an invalid queue submission response",
                category="provider",
            )
        request_id = submitted.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return submitted
        escaped_id = quote(request_id, safe="")
        status_url = self._trusted_authenticated_url(
            submitted.get("status_url"), f"{endpoint}/requests/{escaped_id}/status", endpoint
        )
        response_url = self._trusted_authenticated_url(
            submitted.get("response_url"), f"{endpoint}/requests/{escaped_id}", endpoint
        )
        return await self._poll_fal(
            provider, status_url=status_url, response_url=response_url, headers=headers
        )

    async def _poll_fal(
        self,
        provider: MediaProviderSettings,
        *,
        status_url: str,
        response_url: str,
        headers: dict[str, str],
    ) -> Any:
        deadline = time.monotonic() + self._poll_setting(
            provider, "pollTimeoutSeconds", default=600, maximum=1800
        )
        interval = self._poll_setting(provider, "pollIntervalSeconds", default=1, maximum=60)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OmniScholarError(
                    "provider_job_timeout",
                    "fal image generation did not complete before the configured deadline",
                    category="timeout",
                    retryable=False,
                )
            status = await self.transport.json(
                "GET",
                status_url,
                headers=headers,
                timeout_seconds=min(30, remaining),
                max_response_bytes=1024 * 1024,
            )
            if not isinstance(status, dict):
                raise OmniScholarError(
                    "invalid_job_response",
                    "fal returned an invalid job status response",
                    category="provider",
                )
            state = str(status.get("status", "")).upper()
            if state == "COMPLETED":
                if status.get("error") or status.get("error_type"):
                    raise OmniScholarError(
                        "provider_job_failed",
                        "fal image generation failed",
                        category="provider",
                    )
                return await self.transport.json(
                    "GET",
                    response_url,
                    headers=headers,
                    timeout_seconds=min(60, remaining),
                    max_response_bytes=self.max_artifact_bytes,
                )
            if state not in {"IN_QUEUE", "IN_PROGRESS"}:
                raise OmniScholarError(
                    "unknown_job_status",
                    "fal returned an unknown job status",
                    category="provider",
                )
            await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))

    async def _call_dashscope(
        self,
        provider: MediaProviderSettings,
        model: str,
        prompt: str,
        references: list[tuple[str, bytes | None, str]],
        options: dict[str, Any],
    ) -> Any:
        async_mode = options.get("async") is True
        if async_mode and (model not in {"qwen-image", "qwen-image-plus"} or references):
            raise OmniScholarError(
                "model_capability_unavailable",
                "DashScope async image synthesis supports text-only qwen-image or qwen-image-plus",
                category="capability",
            )
        workspace = provider.options.get("workspace")
        workspace_valid = (
            isinstance(workspace, str) and _DASHSCOPE_WORKSPACE.fullmatch(workspace) is not None
        )
        configured_base = provider.base_url.rstrip("/") if provider.base_url else None
        if configured_base and configured_base not in _DEPRECATED_DASHSCOPE_BASES:
            base = configured_base
        elif workspace_valid:
            region = "ap-southeast-1" if provider.id == "qwen-cloud" else "cn-beijing"
            base = f"https://{workspace}.{region}.maas.aliyuncs.com/api/v1"
        else:
            raise OmniScholarError(
                "dashscope_workspace_required",
                "DashScope current image API requires a workspace-scoped endpoint",
                category="config",
            )
        default_endpoint = (
            "services/aigc/text2image/image-synthesis"
            if async_mode
            else "services/aigc/multimodal-generation/generation"
        )
        endpoint = self._relative_endpoint(
            base, str(provider.options.get("generationEndpoint", default_endpoint))
        )
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        if isinstance(workspace, str) and workspace:
            headers["X-DashScope-WorkSpace"] = workspace
        if async_mode:
            headers["X-DashScope-Async"] = "enable"
        native_options = self._payload_options(options)
        if async_mode:
            body = {
                "model": model,
                "input": {"prompt": prompt},
                "parameters": native_options,
            }
        else:
            content = [
                {
                    "image": self._data_uri(name, data, mime) if data is not None else name,
                }
                for name, data, mime in references
            ]
            content.append({"text": prompt})
            body = {
                "model": model,
                "input": {"messages": [{"role": "user", "content": content}]},
                "parameters": native_options,
            }
        submitted = await self.transport.json(
            "POST",
            endpoint,
            headers=headers,
            body=body,
            timeout_seconds=180,
            max_response_bytes=4 * 1024 * 1024,
        )
        self._raise_provider_payload_error(submitted, provider.id)
        output = submitted.get("output") if isinstance(submitted, dict) else None
        task_id = output.get("task_id") if isinstance(output, dict) else None
        if not isinstance(task_id, str) or not task_id:
            return submitted
        task_url = self._relative_endpoint(base, f"tasks/{quote(task_id, safe='')}")
        return await self._poll_dashscope(provider, task_url=task_url, headers=headers)

    async def _poll_dashscope(
        self,
        provider: MediaProviderSettings,
        *,
        task_url: str,
        headers: dict[str, str],
    ) -> Any:
        deadline = time.monotonic() + self._poll_setting(
            provider, "pollTimeoutSeconds", default=600, maximum=1800
        )
        interval = self._poll_setting(provider, "pollIntervalSeconds", default=5, maximum=60)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OmniScholarError(
                    "provider_job_timeout",
                    "DashScope image generation did not complete before the configured deadline",
                    category="timeout",
                    retryable=False,
                )
            payload = await self.transport.json(
                "GET",
                task_url,
                headers=headers,
                timeout_seconds=min(30, remaining),
                max_response_bytes=4 * 1024 * 1024,
            )
            self._raise_provider_payload_error(payload, provider.id)
            output = payload.get("output") if isinstance(payload, dict) else None
            state = str(output.get("task_status", "")).upper() if isinstance(output, dict) else ""
            if state == "SUCCEEDED":
                return payload
            if state in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise OmniScholarError(
                    "provider_job_failed",
                    "DashScope image generation failed",
                    category="provider",
                )
            if state not in {"PENDING", "RUNNING"}:
                raise OmniScholarError(
                    "unknown_job_status",
                    "DashScope returned an unknown job status",
                    category="provider",
                )
            await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))

    @staticmethod
    def _raise_provider_payload_error(payload: Any, provider: str) -> None:
        if not isinstance(payload, dict):
            raise OmniScholarError(
                "invalid_provider_response",
                f"{provider} returned an invalid response",
                category="provider",
            )
        output = payload.get("output")
        provider_code = payload.get("code")
        if provider_code is None and isinstance(output, dict):
            provider_code = output.get("code")
        if provider_code:
            raise OmniScholarError(
                "provider_operation_failed",
                f"{provider} rejected the image operation",
                category="provider",
            )

    @staticmethod
    def _poll_setting(
        provider: MediaProviderSettings, name: str, *, default: float, maximum: float
    ) -> float:
        value = provider.options.get(name, default)
        if (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or value <= 0
            or value > maximum
        ):
            raise OmniScholarError(
                "invalid_provider_option",
                f"media provider option {name} must be greater than zero and at most {maximum}",
                category="config",
            )
        return float(value)

    @staticmethod
    def _payload_options(options: dict[str, Any]) -> dict[str, Any]:
        controls = {"async", "pollIntervalSeconds", "pollTimeoutSeconds"}
        return {key: value for key, value in options.items() if key not in controls}

    @staticmethod
    def _trusted_authenticated_url(value: object, fallback: str, endpoint: str) -> str:
        candidate = value if isinstance(value, str) and value else fallback
        parsed = urlparse(candidate)
        expected = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or parsed.netloc != expected.netloc
            or parsed.username
            or parsed.password
        ):
            raise OmniScholarError(
                "untrusted_job_url",
                "Provider returned a cross-origin authenticated job URL",
                category="authorization",
            )
        return candidate

    @staticmethod
    def _relative_endpoint(base: str, endpoint: str) -> str:
        parsed_base = urlparse(base)
        parsed_endpoint = urlparse(endpoint)
        if parsed_base.scheme != "https" or not parsed_base.hostname:
            raise OmniScholarError(
                "unsafe_provider_url", "Provider baseUrl must use HTTPS", category="config"
            )
        if parsed_endpoint.scheme or parsed_endpoint.netloc:
            raise OmniScholarError(
                "cross_origin_endpoint",
                "Provider endpoints must be relative to baseUrl",
                category="authorization",
            )
        return urljoin(base.rstrip("/") + "/", endpoint.lstrip("/"))

    @staticmethod
    def _data_uri(name: str, content: bytes | None, mime: str) -> str:
        if content is None:
            return name
        return f"data:{mime};base64,{base64.b64encode(content).decode()}"

    async def _save_artifacts(
        self, payload: Any, provider: str
    ) -> tuple[list[dict[str, Any]], Any]:
        saved = await save_image_payload(
            self.transport,
            payload,
            output_root=self.output_root,
            directory="scientific-figures",
            name_prefix=provider,
            max_bytes=self.max_artifact_bytes,
            url_validator=self._validate_public_https,
        )
        return saved.artifacts, saved.sanitized_payload

    @staticmethod
    async def _validate_public_https(value: str) -> None:
        await validate_public_https(value)

    async def service(self, provider_id: str, action: str, args: dict[str, Any]) -> Any:
        provider = self._provider(provider_id)
        if action == "status":
            return {
                "provider": provider.id,
                "enabled": provider.enabled,
                "credentialConfigured": bool(provider.api_key),
                "models": [asdict(item) for item in await self.models(provider_id)],
            }
        endpoint = provider.options.get("statusEndpoint")
        if action == "job" and endpoint and args.get("jobId"):
            url = self._relative_endpoint(
                provider.base_url or "",
                str(endpoint).replace("{id}", quote(str(args["jobId"]), safe="")),
            )
            return await self.transport.json(
                "GET", url, headers={"Authorization": f"Bearer {provider.api_key}"}
            )
        raise OmniScholarError(
            "unsupported_capability",
            f"Provider {provider_id} does not expose service action {action}",
            category="capability",
        )
