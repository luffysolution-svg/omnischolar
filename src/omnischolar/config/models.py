"""Strict schema-versioned configuration models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(item.capitalize() for item in rest)


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, alias_generator=_camel)


class RuntimeConfig(ConfigModel):
    cache_directory: Path = Path(".omnischolar/cache")
    python: str = "python"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    max_output_bytes: int = Field(default=50 * 1024, ge=1024, le=16 * 1024 * 1024)
    max_output_lines: int = Field(default=2_000, ge=10, le=100_000)
    max_response_bytes: int = Field(default=16 * 1024 * 1024, ge=1024, le=512 * 1024 * 1024)
    request_timeout_seconds: float = Field(default=30, ge=1, le=600)
    workspace_roots: list[Path] = Field(default_factory=list)


class ToolGroups(ConfigModel):
    literature: bool = True
    ai4scholar: bool = True
    zotero: bool = True
    parsing: bool = True
    citation: bool = True
    materials: bool = True
    chemistry: bool = True
    media: bool = True


class ToolsConfig(ConfigModel):
    groups: ToolGroups = Field(default_factory=ToolGroups)
    disabled: set[str] = Field(default_factory=set)


class DefaultsConfig(ConfigModel):
    language: str = "en"
    citation_style: str = "apa"
    literature_limit: int = Field(default=20, ge=1, le=1_000)
    preferred_literature_providers: list[str] = Field(
        default_factory=lambda: ["semantic-scholar", "openalex", "crossref"]
    )
    default_image_provider: str | None = None


class CredentialedConfig(ConfigModel):
    api_key: SecretStr | None = None
    api_key_env: str | None = None


class ResearchProviderConfig(CredentialedConfig):
    enabled: bool = True
    base_url: str | None = None
    email: str | None = None
    tool: str = "omnischolar"
    max_pages: int = Field(default=10, ge=1, le=100)
    rate_limit_per_second: float | None = Field(default=None, gt=0, le=1_000)
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("baseUrl must be an absolute HTTP(S) URL")
        return value.rstrip("/")


def _research_providers() -> dict[str, ResearchProviderConfig]:
    return {
        "semantic-scholar": ResearchProviderConfig(),
        "openalex": ResearchProviderConfig(),
        "pubmed": ResearchProviderConfig(),
        "arxiv": ResearchProviderConfig(),
        "crossref": ResearchProviderConfig(),
        "unpaywall": ResearchProviderConfig(enabled=False),
        "easyscholar": ResearchProviderConfig(enabled=False),
    }


class ResearchConfig(ConfigModel):
    providers: dict[str, ResearchProviderConfig] = Field(default_factory=_research_providers)
    fallback: bool = True
    max_pages: int = Field(default=10, ge=1, le=100)
    cache_ttl_seconds: int = Field(default=3_600, ge=0, le=2_592_000)

    @field_validator("providers", mode="before")
    @classmethod
    def merge_default_providers(cls, value: Any) -> Any:
        if value is None:
            return _research_providers()
        if not isinstance(value, dict):
            return value
        defaults: dict[str, Any] = {
            name: provider.model_dump() for name, provider in _research_providers().items()
        }
        defaults.update(value)
        return defaults


class Ai4ScholarConfig(CredentialedConfig):
    enabled: bool = False
    base_url: str = "https://ai4scholar.net"
    timeout_seconds: float = Field(default=60, ge=1, le=600)
    figure_timeout_seconds: float = Field(default=300, ge=1, le=600)
    max_response_bytes: int = Field(default=16 * 1024 * 1024, ge=1024, le=128 * 1024 * 1024)
    max_artifact_bytes: int = Field(default=50 * 1024 * 1024, ge=1024, le=512 * 1024 * 1024)
    artifact_timeout_seconds: float = Field(default=120, ge=1, le=600)
    allow_paid: bool = False


class ZoteroConfig(ConfigModel):
    enabled: bool = True
    base_url: str = "http://127.0.0.1:23119/api"
    max_items: int = Field(default=500, ge=1, le=5_000)
    max_indexed_text_bytes: int = Field(default=16 * 1024, ge=0, le=1024 * 1024)

    @field_validator("base_url")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Zotero baseUrl must use HTTP loopback")
        if parsed.port != 23119 or not parsed.path.rstrip("/").endswith("/api"):
            raise ValueError("Zotero baseUrl must target the local port 23119 /api endpoint")
        return value.rstrip("/")


class MinerUConfig(CredentialedConfig):
    enabled: bool = False
    base_url: str = "https://mineru.net/api/v4"
    lightweight_base_url: str = "https://mineru.net/api/v1/agent"
    model: Literal["pipeline", "vlm", "MinerU-HTML"] = "pipeline"
    cache_directory: Path = Path(".omnischolar/mineru")
    poll_interval_seconds: float = Field(default=2, ge=0.2, le=60)
    poll_timeout_seconds: float = Field(default=600, ge=5, le=7_200)
    max_pdf_bytes: int = Field(default=200 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    allow_external_upload: bool = False
    allow_lightweight_fallback: bool = False


class MaterialsProjectConfig(CredentialedConfig):
    enabled: bool = False
    base_url: str = "https://api.materialsproject.org"
    max_pages: int = Field(default=10, ge=1, le=100)


class CasConfig(CredentialedConfig):
    enabled: bool = False
    base_url: str | None = None
    contract_file: Path | None = None


class DataConfig(ConfigModel):
    materials_project: MaterialsProjectConfig = Field(default_factory=MaterialsProjectConfig)
    cas_common_chemistry: CasConfig = Field(default_factory=CasConfig)


class MediaModelPin(ConfigModel):
    capabilities: set[Literal["text-to-image", "image-to-image", "edit", "multi-reference"]]
    paid: bool = True


class MediaProviderConfig(CredentialedConfig):
    enabled: bool = False
    base_url: str | None = None
    project: str | None = None
    location: str | None = None
    credentials_file: Path | None = None
    models: dict[str, MediaModelPin] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class MediaConfig(ConfigModel):
    providers: dict[str, MediaProviderConfig] = Field(default_factory=dict)
    allow_external_upload: bool = False
    allow_paid: bool = False
    max_input_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    max_artifact_bytes: int = Field(default=50 * 1024 * 1024, ge=1024, le=512 * 1024 * 1024)


class SyncConfig(ConfigModel):
    namespace: str | None = None
    cache_directory: Path = Path(".omnischolar/sync")
    conflict_policy: Literal["preserve-local", "fail"] = "preserve-local"
    recovery: bool = True
    backup: bool = True
    avoid_unnecessary_parse: bool = True


class OutputConfig(ConfigModel):
    root_directory: Path = Path("omnischolar-output")
    conflict_directory: str = ".conflicts"
    safe_writes: bool = True


class OmniScholarConfig(ConfigModel):
    schema_version: Literal[1] = 1
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    ai4scholar: Ai4ScholarConfig = Field(default_factory=Ai4ScholarConfig)
    zotero: ZoteroConfig = Field(default_factory=ZoteroConfig)
    mineru: MinerUConfig = Field(default_factory=MinerUConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    media: MediaConfig = Field(default_factory=MediaConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @model_validator(mode="after")
    def authorization_consistency(self) -> OmniScholarConfig:
        if self.mineru.allow_lightweight_fallback and not self.mineru.allow_external_upload:
            raise ValueError("MinerU lightweight fallback still requires allowExternalUpload")
        return self
