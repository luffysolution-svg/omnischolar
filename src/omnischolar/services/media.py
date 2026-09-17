"""Capability-driven scientific image routing with explicit upload and paid gates."""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse

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
ALL_IMAGE_CAPABILITIES: set[Capability] = {
    "text-to-image",
    "image-to-image",
    "edit",
    "multi-reference",
}

# These are capability declarations, not availability pins. They are only
# applied to model IDs returned by the provider's current model catalog.
CATALOG_CAPABILITIES: dict[str, dict[str, set[Capability]]] = {
    "openai": {
        "gpt-image-1": ALL_IMAGE_CAPABILITIES,
        "gpt-image-1-mini": ALL_IMAGE_CAPABILITIES,
        "gpt-image-1.5": ALL_IMAGE_CAPABILITIES,
        "gpt-image-2": ALL_IMAGE_CAPABILITIES,
        "gpt-image-2.5-sunburst": ALL_IMAGE_CAPABILITIES,
        "gpt-image-2.5-flare": ALL_IMAGE_CAPABILITIES,
    },
    "google": {
        "gemini-2.5-flash-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3.1-flash-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3.1-flash-lite-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3-pro-image": ALL_IMAGE_CAPABILITIES,
    },
    "gemini": {
        "gemini-2.5-flash-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3.1-flash-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3.1-flash-lite-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3-pro-image": ALL_IMAGE_CAPABILITIES,
    },
}

# These providers do not expose a reliable universal image-model catalog to
# this adapter; entries are official model IDs used as capability-safe fallbacks.
CURATED_MODELS: dict[str, dict[str, set[Capability]]] = {
    "fal": {
        "fal-ai/nano-banana-2": ALL_IMAGE_CAPABILITIES,
        "openai/gpt-image-2": {"text-to-image"},
        "openai/gpt-image-2/edit": {"image-to-image", "edit", "multi-reference"},
        "openai/gpt-image-2.5/flare/text-to-image": {"text-to-image"},
        "openai/gpt-image-2.5/flare/edit": {"image-to-image", "edit", "multi-reference"},
        "openai/gpt-image-2.5/sunburst/text-to-image": {"text-to-image"},
        "openai/gpt-image-2.5/sunburst/edit": {"image-to-image", "edit", "multi-reference"},
    },
    "atlas": {
        "google/nano-banana-2/text-to-image": {"text-to-image"},
        "google/nano-banana-2/edit": {"image-to-image", "edit", "multi-reference"},
        "openai/gpt-image-2/text-to-image": {"text-to-image"},
        "openai/gpt-image-2/edit": {"image-to-image", "edit", "multi-reference"},
        "openai/gpt-image-2.5/flare/text-to-image": {"text-to-image"},
        "openai/gpt-image-2.5/flare/edit": {"image-to-image", "edit", "multi-reference"},
        "openai/gpt-image-2.5/sunburst/text-to-image": {"text-to-image"},
        "openai/gpt-image-2.5/sunburst/edit": {"image-to-image", "edit", "multi-reference"},
    },
    "dashscope": {
        "qwen-image-3.0-pro": {"text-to-image", "image-to-image", "edit", "multi-reference"},
        "qwen-image-3.0": {"text-to-image", "image-to-image", "edit", "multi-reference"},
        "wan2.7-image-pro": {"text-to-image"},
        "wan2.7-image": {"text-to-image"},
        "z-image-turbo": {"text-to-image"},
    },
    "qwen": {
        "qwen-image-3.0-pro": {"text-to-image", "image-to-image", "edit", "multi-reference"},
        "qwen-image-3.0": {"text-to-image", "image-to-image", "edit", "multi-reference"},
        "wan2.7-image-pro": {"text-to-image"},
        "wan2.7-image": {"text-to-image"},
        "z-image-turbo": {"text-to-image"},
    },
    "qwen-cloud": {
        "qwen-image-3.0-pro": {"text-to-image", "image-to-image", "edit", "multi-reference"},
        "qwen-image-3.0": {"text-to-image", "image-to-image", "edit", "multi-reference"},
        "wan2.7-image-pro": {"text-to-image"},
        "wan2.7-image": {"text-to-image"},
        "z-image-turbo": {"text-to-image"},
    },
    "vertex": {
        "gemini-2.5-flash-image": ALL_IMAGE_CAPABILITIES,
        "gemini-2.5-flash-image-preview": ALL_IMAGE_CAPABILITIES,
        "gemini-3.1-flash-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3.1-flash-lite-image": ALL_IMAGE_CAPABILITIES,
        "gemini-3-pro-image": ALL_IMAGE_CAPABILITIES,
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
    "xai-image": "https://api.x.ai/v1/image-generation-models",
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
    credentials_file: Path | None = None


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    provider: str
    id: str
    capabilities: tuple[Capability, ...]
    source: Literal[
        "config_pin", "official_catalog", "model_catalog", "curated_fallback"
    ]
    usable: bool
    unavailable_reason: str | None = None
    created: int | None = None
    supported_parameters: tuple[str, ...] = ()


# Provider parameter contracts are based on the current official API schemas.
# These are separate from modality capabilities: a model can support editing
# while its provider still rejects a particular output control.
PROVIDER_PARAMETER_SUPPORT: dict[str, tuple[str, ...]] = {
    "openai": ("size", "resolution", "background", "outputFormat", "quality", "n"),
    "google": ("aspectRatio", "resolution", "outputFormat"),
    "gemini": ("aspectRatio", "resolution", "outputFormat"),
    "vertex": ("aspectRatio", "resolution", "outputFormat", "n"),
    "fal": ("size", "aspectRatio", "resolution", "background", "outputFormat", "quality", "n", "seed"),
    "atlas": ("size", "resolution", "quality", "outputFormat", "n"),
    "dashscope": ("size", "resolution", "n", "negativePrompt", "seed"),
    "qwen": ("size", "resolution", "n", "negativePrompt", "seed"),
    "qwen-cloud": ("size", "resolution", "n", "negativePrompt", "seed"),
}


def supported_parameters(provider_id: str, model_id: str) -> tuple[str, ...]:
    if provider_id == "fal" and model_id == "fal-ai/nano-banana-2":
        return ("aspectRatio", "resolution", "outputFormat", "n", "seed")
    if provider_id == "fal" and model_id.startswith("openai/gpt-image"):
        return ("size", "resolution", "background", "outputFormat", "quality", "n")
    if provider_id in {"dashscope", "qwen", "qwen-cloud"} and not model_id.startswith(
        "qwen-image"
    ):
        return ("size", "resolution", "n")
    return PROVIDER_PARAMETER_SUPPORT.get(provider_id, ())


class MediaService:
    def __init__(
        self,
        transport: ServiceTransport,
        providers: list[MediaProviderSettings],
        *,
        output_root: Path,
        workspace_roots: tuple[Path, ...],
        max_input_bytes: int = 25 * 1024 * 1024,
        max_artifact_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self.transport = transport
        self.providers = {provider.id: provider for provider in providers}
        self.output_root = output_root
        self.workspace_roots = workspace_roots
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
            credential_error = self._provider_credential_error(provider)
            usable = contract_ready and credential_error is None
            unavailable_reason = credential_error or contract_error
            catalog_models: dict[str, tuple[set[Capability], int | None]] = {}
            if discover and provider.api_key:
                catalog_models = await self._discover_catalog(provider)
            for model_id, capabilities in pins.items():
                descriptors.append(
                    ModelDescriptor(
                        provider.id,
                        model_id,
                        tuple(sorted(capabilities)),
                        "config_pin",
                        usable,
                        unavailable_reason,
                        supported_parameters=supported_parameters(provider.id, model_id),
                    )
                )
            for model_id, (capabilities, created) in catalog_models.items():
                if model_id in pins:
                    continue
                known_capabilities = capabilities or self._catalog_capabilities(
                    provider.id, model_id
                )
                catalog_usable = usable and bool(known_capabilities)
                descriptors.append(
                    ModelDescriptor(
                        provider.id,
                        model_id,
                        tuple(sorted(known_capabilities)),
                        "official_catalog"
                        if provider.id in {"openai", "xai", "google", "gemini"}
                        else "model_catalog",
                        catalog_usable,
                        unavailable_reason if not usable else (
                            None if known_capabilities else "model_capabilities_unpinned"
                        ),
                        created,
                        supported_parameters(provider.id, model_id),
                    )
                )
            for model_id, capabilities in CURATED_MODELS.get(provider.id, {}).items():
                if model_id in pins or model_id in catalog_models:
                    continue
                descriptors.append(
                    ModelDescriptor(
                        provider.id,
                        model_id,
                        tuple(sorted(capabilities)),
                        "curated_fallback",
                        usable,
                        unavailable_reason,
                        supported_parameters=supported_parameters(provider.id, model_id),
                    )
                )
        return descriptors

    @staticmethod
    def _provider_contract_error(provider: MediaProviderSettings) -> str | None:
        if provider.id in {"atlas", "custom"} and not provider.base_url:
            return "provider_base_url_required"
        if provider.id not in {"dashscope", "qwen", "qwen-cloud"}:
            return None
        if provider.id == "qwen-cloud":
            return None
        configured_base = provider.base_url.rstrip("/") if provider.base_url else None
        if configured_base and "your-workspace" not in configured_base and (
            configured_base not in _DEPRECATED_DASHSCOPE_BASES
            or provider.options.get("allowLegacyBaseUrl", True)
        ):
            return None
        workspace = provider.options.get("workspace")
        if isinstance(workspace, str) and _DASHSCOPE_WORKSPACE.fullmatch(workspace) is not None:
            return None
        return "dashscope_workspace_required"

    @staticmethod
    def _provider_credential_error(provider: MediaProviderSettings) -> str | None:
        if provider.id == "vertex" and (provider.api_key or provider.credentials_file):
            return None
        if not provider.api_key:
            return "credential_required"
        return None

    @classmethod
    def _provider_contract_ready(cls, provider: MediaProviderSettings) -> bool:
        return cls._provider_contract_error(provider) is None

    @staticmethod
    def _catalog_capabilities(provider_id: str, model_id: str) -> set[Capability]:
        if provider_id == "xai":
            return set(ALL_IMAGE_CAPABILITIES)
        exact = CATALOG_CAPABILITIES.get(provider_id, {}).get(model_id)
        if exact:
            return set(exact)
        if provider_id == "openai" and model_id.startswith(
            ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare", "gpt-image-2")
        ):
            return set(ALL_IMAGE_CAPABILITIES)
        return set()

    async def _discover_catalog(
        self, provider: MediaProviderSettings
    ) -> dict[str, tuple[set[Capability], int | None]]:
        catalog_key = (
            "xai-image"
            if provider.id == "xai"
            else "google"
            if provider.id == "gemini"
            else provider.id
        )
        url = CATALOG_URLS.get(catalog_key) or provider.options.get("modelCatalogEndpoint")
        if provider.id == "custom" and not url and provider.base_url:
            url = self._relative_endpoint(provider.base_url, "models")
        if not isinstance(url, str) or not url:
            return {}
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        params: dict[str, Any] | None = None
        if provider.id in {"google", "gemini"}:
            headers = {}
            params = {"key": provider.api_key}
        try:
            payload = await self.transport.json("GET", url, params=params, headers=headers)
        except OmniScholarError:
            if provider.id == "custom":
                return {}
            raise
        values = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            values = payload.get("models", []) if isinstance(payload, dict) else []
        discovered: dict[str, tuple[set[Capability], int | None]] = {}
        for item in values:
            if not isinstance(item, dict):
                continue
            model_id = str(
                item.get("id") or item.get("model_id") or item.get("name") or ""
            ).removeprefix("models/")
            if not model_id:
                continue
            raw_capabilities = item.get("capabilities") or item.get("supportedCapabilities")
            capabilities = {
                str(value)
                for value in raw_capabilities
                if str(value) in ALL_IMAGE_CAPABILITIES
            } if isinstance(raw_capabilities, list) else set()
            created = item.get("created") if isinstance(item.get("created"), int) else None
            discovered[model_id] = (capabilities, created)
        return discovered

    async def execute(
        self,
        *,
        provider_id: str | None,
        capability: Capability,
        prompt: str,
        context: ToolExecutionContext,
        model: str | None = None,
        references: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = self._provider(provider_id) if provider_id else None
        if provider is None:
            candidates = await self.models(discover=True)
            available = [
                item
                for item in candidates
                if capability in item.capabilities and item.usable
                and (model is None or item.id == model)
            ]
            if not available:
                raise OmniScholarError(
                    "model_selection_required",
                    "No usable image model was discovered; specify a provider/model or configure a model catalog",
                    category="capability",
                    details={
                        "models": [asdict(item) for item in candidates],
                        "requestedCapability": capability,
                    },
                )
            selected_model = max(
                available,
                key=lambda item: (item.created if item.created is not None else -1, item.id),
            )
            provider = self._provider(selected_model.provider)
        else:
            selected_model = None
        if not self._provider_contract_ready(provider):
            raise OmniScholarError(
                "dashscope_workspace_required",
                "DashScope current image API requires a workspace-scoped endpoint",
                category="config",
            )
        if selected_model is None:
            descriptors = await self.models(provider.id, discover=True)
            available = [
                item
                for item in descriptors
                if capability in item.capabilities and item.usable
                and (model is None or item.id == model)
            ]
            selected_model = max(
                available,
                key=lambda item: (item.created if item.created is not None else -1, item.id),
                default=None,
            )
        if selected_model is None:
            raise OmniScholarError(
                "model_capability_unavailable",
                f"No configured/discovered {provider.id} model supports {capability}",
                category="capability",
                details={"provider": provider.id, "model": model, "requestedCapability": capability},
            )
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

    @staticmethod
    def _map_provider_options(
        provider: MediaProviderSettings, options: dict[str, Any]
    ) -> dict[str, Any]:
        mapped = dict(options)
        if provider.id in {"openai", "custom"}:
            if "resolution" in mapped:
                if "size" in mapped:
                    raise OmniScholarError(
                        "parameter_conflict",
                        "Specify only one of size and resolution",
                        category="validation",
                    )
                mapped["size"] = mapped.pop("resolution")
            if "aspect_ratio" in mapped:
                raise OmniScholarError(
                    "parameter_unsupported",
                    "OpenAI Images uses size rather than aspect_ratio",
                    category="capability",
                )
            if mapped.get("background") == "transparent" and mapped.get("output_format") not in {
                "png", "webp"
            }:
                raise OmniScholarError(
                    "parameter_conflict",
                    "Transparent OpenAI images require outputFormat png or webp",
                    category="validation",
                )
        if provider.id in {"xai"}:
            unsupported = {"size", "background", "output_format"} & mapped.keys()
            if unsupported:
                raise OmniScholarError(
                    "parameter_unsupported",
                    f"xAI does not support image parameters: {', '.join(sorted(unsupported))}",
                    category="capability",
                )
        if provider.id in {"google", "gemini"}:
            unsupported = {"size", "background", "quality", "n", "seed"} & mapped.keys()
            if unsupported:
                raise OmniScholarError(
                    "parameter_unsupported",
                    f"Gemini image interactions do not support: {', '.join(sorted(unsupported))}",
                    category="capability",
                )
        if provider.id == "vertex":
            unsupported = {"size", "background", "quality", "seed"} & mapped.keys()
            if unsupported:
                raise OmniScholarError(
                    "parameter_unsupported",
                    f"Vertex Imagen does not support: {', '.join(sorted(unsupported))}",
                    category="capability",
                )
            if "n" in mapped:
                if isinstance(mapped["n"], int) and mapped["n"] > 4:
                    raise OmniScholarError(
                        "parameter_out_of_range",
                        "Vertex Imagen supports at most 4 output images",
                        category="validation",
                    )
                mapped["sampleCount"] = mapped.pop("n")
            if "aspect_ratio" in mapped:
                mapped["aspectRatio"] = mapped.pop("aspect_ratio")
            if "output_format" in mapped:
                mapped["outputOptions"] = {
                    "mimeType": f"image/{mapped.pop('output_format')}"
                }
        if provider.id == "fal":
            if "size" in mapped:
                mapped["image_size"] = mapped.pop("size")
            if "n" in mapped:
                mapped["num_images"] = mapped.pop("n")
        if provider.id == "atlas" and "n" in mapped:
            mapped["num_images"] = mapped.pop("n")
        if provider.id in {"dashscope", "qwen", "qwen-cloud"}:
            if "resolution" in mapped:
                if "size" in mapped:
                    raise OmniScholarError(
                        "parameter_conflict",
                        "Specify only one of size and resolution",
                        category="validation",
                    )
                resolution = mapped.pop("resolution")
                if not isinstance(resolution, str) or "x" not in resolution.lower():
                    raise OmniScholarError(
                        "parameter_unsupported",
                        "Qwen resolution must be a WIDTHxHEIGHT value and is mapped to size",
                        category="capability",
                    )
                mapped["size"] = resolution
            if "aspect_ratio" in mapped:
                if "size" in mapped:
                    raise OmniScholarError(
                        "parameter_conflict",
                        "Specify only one of aspectRatio and size for DashScope/Qwen",
                        category="validation",
                    )
                aspect_sizes = {
                    "1:1": "2048*2048",
                    "2:3": "1365*2048",
                    "3:2": "2048*1365",
                    "3:4": "1536*2048",
                    "4:3": "2048*1536",
                    "4:5": "1638*2048",
                    "5:4": "2048*1638",
                    "9:16": "1152*2048",
                    "16:9": "2048*1152",
                }
                aspect_ratio = mapped.pop("aspect_ratio")
                if aspect_ratio not in aspect_sizes:
                    raise OmniScholarError(
                        "parameter_unsupported",
                        "Qwen aspectRatio must be a supported standard ratio",
                        category="capability",
                    )
                mapped["size"] = aspect_sizes[aspect_ratio]
            unsupported = {"background", "output_format", "quality"} & mapped.keys()
            if unsupported:
                raise OmniScholarError(
                    "parameter_unsupported",
                    f"DashScope/Qwen does not support: {', '.join(sorted(unsupported))}",
                    category="capability",
                )
            compatible = provider.options.get("protocol") == "openai-compatible"
            if not compatible and "size" in mapped and isinstance(mapped["size"], str):
                mapped["size"] = mapped["size"].replace("x", "*")
            if isinstance(mapped.get("n"), int) and mapped["n"] > 6:
                raise OmniScholarError(
                    "parameter_out_of_range",
                    "Qwen Image supports at most 6 output images",
                    category="validation",
                )
        return mapped

    @staticmethod
    def _vertex_project(provider: MediaProviderSettings) -> str | None:
        configured = provider.options.get("project")
        if isinstance(configured, str) and configured.strip() and configured != "your-project":
            return configured.strip()
        path = provider.credentials_file
        if path is None:
            return None
        try:
            if path.stat().st_size > 4 * 1024 * 1024:
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        project = payload.get("project_id") if isinstance(payload, dict) else None
        return project.strip() if isinstance(project, str) and project.strip() else None

    @staticmethod
    def _vertex_authorization(provider: MediaProviderSettings) -> str:
        if provider.credentials_file:
            try:
                from google.auth.transport.requests import Request
                from google.oauth2 import service_account
            except ImportError as exc:
                raise OmniScholarError(
                    "credential_dependency_required",
                    "Vertex JSON credentials require the google-auth and requests dependencies",
                    category="configuration",
                    cause=exc,
                ) from exc
            if not provider.credentials_file.is_file():
                raise OmniScholarError(
                    "credentials_file_missing",
                    "Vertex credentialsFile does not exist",
                    category="configuration",
                )
            try:
                from requests import Session

                credentials = service_account.Credentials.from_service_account_file(
                    str(provider.credentials_file),
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                session = Session()
                request_method = session.request

                def request_with_timeout(method: str, url: str, **kwargs: Any) -> Any:
                    kwargs.setdefault("timeout", 20)
                    return request_method(method, url, **kwargs)

                session.request = request_with_timeout  # type: ignore[method-assign]
                credentials.refresh(Request(session))
            except Exception as exc:
                raise OmniScholarError(
                    "vertex_auth_failed",
                    "Vertex service-account authentication failed",
                    category="authentication",
                    retryable=True,
                    cause=exc,
                ) from exc
            if not credentials.token:
                raise OmniScholarError(
                    "vertex_token_missing",
                    "Vertex credentials did not yield an access token",
                    category="authentication",
                )
            return f"Bearer {credentials.token}"
        if provider.api_key:
            return f"Bearer {provider.api_key}"
        raise OmniScholarError(
            "credential_required",
            "Vertex requires credentialsFile or an OAuth bearer token",
            category="authentication",
        )

    @staticmethod
    def _dashscope_base(provider: MediaProviderSettings) -> str:
        configured = provider.base_url.rstrip("/") if provider.base_url else None
        workspace = provider.options.get("workspace")
        region = provider.options.get(
            "region", "ap-southeast-1" if provider.id == "qwen-cloud" else "cn-beijing"
        )
        workspace_valid = isinstance(workspace, str) and _DASHSCOPE_WORKSPACE.fullmatch(workspace)
        protocol = provider.options.get("protocol", "native")
        if provider.id == "qwen-cloud":
            if configured and "your-workspace" not in configured:
                if protocol != "openai-compatible":
                    return configured.replace("/compatible-mode/v1", "/api/v1")
                return configured
            return (
                "https://dashscope.aliyuncs.com/compatible-mode/v1"
                if protocol == "openai-compatible"
                else "https://dashscope.aliyuncs.com/api/v1"
            )
        if workspace_valid and (
            not configured or "your-workspace" in configured
        ):
            suffix = "compatible-mode/v1" if protocol == "openai-compatible" else "api/v1"
            return f"https://{workspace}.{region}.maas.aliyuncs.com/{suffix}"
        if configured and protocol != "openai-compatible":
            return configured.replace("/compatible-mode/v1", "/api/v1")
        if configured:
            return configured
        raise OmniScholarError(
            "dashscope_endpoint_required",
            "DashScope/Qwen requires baseUrl or a valid workspace and region",
            category="config",
        )

    async def _call_provider(
        self,
        provider: MediaProviderSettings,
        model: str,
        capability: Capability,
        prompt: str,
        references: list[tuple[str, bytes | None, str]],
        options: dict[str, Any],
    ) -> Any:
        options = self._map_provider_options(provider, options)
        if provider.id in {"openai", "custom"}:
            base = provider.base_url or "https://api.openai.com/v1"
            headers = {"Authorization": f"Bearer {provider.api_key}"}
            if references:
                endpoint = self._relative_endpoint(
                    base, provider.options.get("editEndpoint", "images/edits")
                )
                field_name = "image" if len(references) == 1 else "image[]"
                files = [
                    (
                        field_name,
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
                    "POST",
                    endpoint,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout_seconds=self._image_request_timeout(provider),
                )
            endpoint = self._relative_endpoint(
                base, provider.options.get("generationEndpoint", "images/generations")
            )
            return await self.transport.json(
                "POST",
                endpoint,
                headers=headers,
                body={**options, "model": model, "prompt": prompt},
                timeout_seconds=self._image_request_timeout(provider),
            )
        if provider.id == "xai":
            base = provider.base_url or "https://api.x.ai/v1"
            endpoint = self._relative_endpoint(
                base, provider.options.get("generationEndpoint", "images/generations")
            )
            body = {**options, "model": model, "prompt": prompt}
            if references:
                images = [
                    {"type": "image_url", "url": self._data_uri(name, content, mime) if content else name}
                    for name, content, mime in references
                ]
                if len(images) == 1:
                    body["image"] = images[0]
                else:
                    body["images"] = images
            return await self.transport.json(
                "POST", endpoint, headers={"Authorization": f"Bearer {provider.api_key}"}, body=body
            )
        if provider.id in {"google", "gemini"}:
            base = provider.base_url or "https://generativelanguage.googleapis.com/v1beta"
            if provider.options.get("protocol", "interactions") == "interactions":
                endpoint = self._relative_endpoint(
                    base, provider.options.get("generationEndpoint", "interactions")
                )
                input_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
                input_parts.extend(
                    {"type": "image", "mime_type": mime, "data": base64.b64encode(content).decode()}
                    if content
                    else {"type": "image", "uri": name, "mime_type": mime}
                    for name, content, mime in references
                )
                response_format: dict[str, Any] = {"type": "image"}
                if "aspect_ratio" in options:
                    response_format["aspect_ratio"] = options.pop("aspect_ratio")
                if "resolution" in options:
                    response_format["image_size"] = options.pop("resolution")
                if "output_format" in options:
                    response_format["mime_type"] = (
                        f"image/{options.pop('output_format')}"
                    )
                return await self.transport.json(
                    "POST",
                    endpoint,
                    headers={"x-goog-api-key": str(provider.api_key)},
                    body={
                        "model": model,
                        "input": input_parts,
                        "response_format": response_format,
                        **options,
                    },
                )
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
                self._vertex_project(provider),
                provider.options.get("location", "global"),
            )
            if not project:
                raise OmniScholarError(
                    "vertex_project_required",
                    "Vertex provider requires project configuration",
                    category="config",
                )
            base = provider.base_url or (
                f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models"
                if location == "global"
                else f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models"
            )
            if model.startswith("gemini-") or provider.options.get("protocol") == "gemini":
                endpoint = self._relative_endpoint(base, f"{quote(model, safe='')}:generateContent")
                parts: list[dict[str, Any]] = [{"text": prompt}]
                parts.extend(
                    {"inlineData": {"mimeType": mime, "data": base64.b64encode(content).decode()}}
                    if content
                    else {"fileData": {"mimeType": mime, "fileUri": name}}
                    for name, content, mime in references
                )
                generation_config: dict[str, Any] = {**options, "responseModalities": ["TEXT", "IMAGE"]}
                if "sampleCount" in generation_config:
                    generation_config["candidateCount"] = generation_config.pop("sampleCount")
                image_config: dict[str, Any] = {}
                if "aspectRatio" in generation_config:
                    image_config["aspectRatio"] = generation_config.pop("aspectRatio")
                if "outputOptions" in generation_config:
                    image_config["imageOutputOptions"] = generation_config.pop("outputOptions")
                if image_config:
                    generation_config["imageConfig"] = image_config
                return await self.transport.json(
                    "POST",
                    endpoint,
                    headers={"Authorization": self._vertex_authorization(provider)},
                    body={
                        "contents": [{"role": "user", "parts": parts}],
                        "generationConfig": generation_config,
                    },
                    timeout_seconds=180,
                    max_response_bytes=self.max_artifact_bytes,
                )
            endpoint = self._relative_endpoint(base, f"{quote(model, safe='')}:predict")
            instance: dict[str, Any] = {"prompt": prompt}
            if references:
                if "capability" in model:
                    instance["referenceImages"] = [
                        {
                            "referenceType": "REFERENCE_TYPE_RAW",
                            "referenceId": index,
                            "referenceImage": {
                                "bytesBase64Encoded": base64.b64encode(content or b"").decode()
                            },
                        }
                        for index, (_name, content, _mime) in enumerate(references, 1)
                    ]
                else:
                    instance["image"] = {
                        "bytesBase64Encoded": base64.b64encode(references[0][1] or b"").decode()
                    }
            return await self.transport.json(
                "POST",
                endpoint,
                headers={"Authorization": self._vertex_authorization(provider)},
                body={
                    "instances": [instance],
                    "parameters": options,
                },
                timeout_seconds=180,
                max_response_bytes=self.max_artifact_bytes,
            )
        if provider.id == "fal":
            return await self._call_fal(provider, model, prompt, references, options)
        if provider.id in {"dashscope", "qwen", "qwen-cloud"}:
            return await self._call_dashscope(provider, model, prompt, references, options)
        if provider.id == "atlas":
            return await self._call_atlas(provider, model, prompt, references, options)
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
        if base.rstrip("/") == "https://fal.run":
            base = "https://queue.fal.run"
        endpoint = self._relative_endpoint(base, model)
        headers = {"Authorization": f"Key {provider.api_key}"}
        body = self._payload_options(options)
        if "sync_mode" not in body:
            body["sync_mode"] = True
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

    async def _call_atlas(
        self,
        provider: MediaProviderSettings,
        model: str,
        prompt: str,
        references: list[tuple[str, bytes | None, str]],
        options: dict[str, Any],
    ) -> Any:
        base = provider.base_url or "https://api.atlascloud.ai/api/v1"
        endpoint = self._relative_endpoint(
            base, str(provider.options.get("generationEndpoint", "model/generateImage"))
        )
        body = {"model": model, "prompt": prompt, **self._payload_options(options)}
        if references:
            body["images"] = [
                self._data_uri(name, content, mime) if content else name
                for name, content, mime in references
            ]
        submitted = await self.transport.json(
            "POST",
            endpoint,
            headers={"Authorization": f"Bearer {provider.api_key}"},
            body=body,
            timeout_seconds=60,
            max_response_bytes=1024 * 1024,
        )
        self._raise_atlas_payload_error(submitted)
        data = submitted.get("data") if isinstance(submitted, dict) else None
        if not isinstance(data, dict):
            data = submitted if isinstance(submitted, dict) else {}
        prediction_id = data.get("id") or data.get("prediction_id") or data.get("request_id")
        if not isinstance(prediction_id, str) or not prediction_id:
            return submitted
        poll_endpoint = self._relative_endpoint(
            base,
            f"{provider.options.get('pollEndpoint', 'model/prediction')}/{quote(prediction_id, safe='')}",
        )
        return await self._poll_atlas(provider, poll_endpoint)

    async def _poll_atlas(
        self, provider: MediaProviderSettings, poll_endpoint: str
    ) -> Any:
        deadline = time.monotonic() + self._poll_setting(
            provider, "pollTimeoutSeconds", default=600, maximum=1800
        )
        interval = self._poll_setting(provider, "pollIntervalSeconds", default=2, maximum=60)
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OmniScholarError(
                    "provider_job_timeout",
                    "Atlas image generation did not complete before the configured deadline",
                    category="timeout",
                    retryable=False,
                )
            payload = await self.transport.json(
                "GET",
                poll_endpoint,
                headers=headers,
                timeout_seconds=min(30, remaining),
                max_response_bytes=self.max_artifact_bytes,
            )
            self._raise_atlas_payload_error(payload)
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                data = payload if isinstance(payload, dict) else {}
            state = str(data.get("status", "")).lower()
            if state in {"completed", "succeeded", "success"}:
                return payload
            if state in {"failed", "canceled", "cancelled", "error"}:
                raise OmniScholarError(
                    "provider_job_failed", "Atlas image generation failed", category="provider"
                )
            if state not in {"processing", "pending", "queued", "in_progress", "in-queue"}:
                raise OmniScholarError(
                    "unknown_job_status", "Atlas returned an unknown job status", category="provider"
                )
            await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))

    @staticmethod
    def _raise_atlas_payload_error(payload: Any) -> None:
        if not isinstance(payload, dict):
            raise OmniScholarError(
                "invalid_provider_response", "Atlas returned an invalid response", category="provider"
            )
        data = payload.get("data")
        if isinstance(data, dict) and (data.get("error") or data.get("error_code")):
            raise OmniScholarError(
                "provider_operation_failed", "Atlas rejected the image operation", category="provider"
            )
        if payload.get("error") or payload.get("code") not in {None, 0, 200}:
            raise OmniScholarError(
                "provider_operation_failed", "Atlas rejected the image operation", category="provider"
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
        compatible = provider.options.get("protocol") == "openai-compatible"
        if compatible:
            if async_mode:
                raise OmniScholarError(
                    "parameter_unsupported",
                    "Qwen OpenAI-compatible image generation is synchronous only",
                    category="capability",
                )
            base = self._dashscope_base(provider)
            endpoint = self._relative_endpoint(
                base, str(provider.options.get("generationEndpoint", "images/generations"))
            )
            body: dict[str, Any] = {"model": model, "prompt": prompt, **options}
            if references:
                images = [
                    self._data_uri(name, data, mime) if data is not None else name
                    for name, data, mime in references
                ]
                body["image"] = images[0] if len(images) == 1 else images
            return await self.transport.json(
                "POST",
                endpoint,
                headers={"Authorization": f"Bearer {provider.api_key}"},
                body=body,
                timeout_seconds=180,
                max_response_bytes=4 * 1024 * 1024,
            )
        if async_mode and (model not in {"qwen-image-3.0-pro", "qwen-image-3.0"} or references):
            raise OmniScholarError(
                "model_capability_unavailable",
                "DashScope async image synthesis supports text-only qwen-image-3.0 models",
                category="capability",
            )
        workspace = provider.options.get("workspace")
        base = self._dashscope_base(provider)
        default_endpoint = (
            "services/aigc/image-generation/generation"
            if async_mode
            else "services/aigc/multimodal-generation/generation"
        )
        endpoint = self._relative_endpoint(
            base, str(provider.options.get("generationEndpoint", default_endpoint))
        )
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        if isinstance(workspace, str) and workspace and provider.options.get("sendWorkspaceHeader"):
            headers["X-DashScope-WorkSpace"] = workspace
        if async_mode:
            headers["X-DashScope-Async"] = "enable"
        native_options = self._payload_options(options)
        content = [
            {"image": self._data_uri(name, data, mime) if data is not None else name}
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
    def _image_request_timeout(provider: MediaProviderSettings) -> float:
        value = provider.options.get("imageTimeoutSeconds", 180)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 180.0
        return max(1.0, min(float(value), 1_800.0))

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
        if parsed_endpoint.netloc or "://" in endpoint:
            raise OmniScholarError(
                "cross_origin_endpoint",
                "Provider endpoints must be relative to baseUrl",
                category="authorization",
            )
        return f"{base.rstrip('/')}/{endpoint.lstrip('/')}"

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
                "credentialConfigured": bool(
                    provider.api_key
                    or (provider.credentials_file is not None and provider.credentials_file.is_file())
                ),
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
