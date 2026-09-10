"""Composition root for host-neutral services."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Self

from omnischolar.config import LoadedConfig, resolve_credential
from omnischolar.core import BoundedHttpClient
from omnischolar.providers.literature import (
    ArxivProvider,
    CoreLiteratureTransport,
    CrossrefProvider,
    EasyScholarProvider,
    LiteratureRouter,
    OpenAlexProvider,
    PubMedProvider,
    SemanticScholarProvider,
    UnpaywallProvider,
)

from .ai4scholar import Ai4ScholarService
from .chemistry import ChemistryService
from .materials import MaterialsProjectService
from .media import MediaProviderSettings, MediaService
from .mineru import MinerUService
from .sync import SyncService
from .transport import CoreServiceTransport
from .zotero import ZoteroService


@dataclass(slots=True)
class ApplicationServices:
    literature: LiteratureRouter
    zotero: ZoteroService
    sync: SyncService
    chemistry: ChemistryService
    ai4scholar: Ai4ScholarService | None
    mineru: MinerUService | None
    materials: MaterialsProjectService | None
    media: MediaService


class OmniScholarApplication:
    def __init__(self, loaded: LoadedConfig) -> None:
        self.loaded = loaded
        self.http: BoundedHttpClient | None = None
        self.services: ApplicationServices | None = None
        self.registry: Any = None
        self.credential_status: dict[str, dict[str, Any]] = {}
        self.known_secrets: tuple[str, ...] = ()

    async def __aenter__(self) -> Self:
        config = self.loaded.config
        credentials: dict[str, Any] = {}

        def credential(service: str, section: Any) -> str | None:
            resolved = resolve_credential(
                service, api_key=section.api_key, api_key_env=section.api_key_env
            )
            credentials[service] = resolved
            self.credential_status[service] = resolved.status()
            return resolved.reveal()

        research_keys = {
            name: credential(name, section) for name, section in config.research.providers.items()
        }
        ai_key = credential("ai4scholar", config.ai4scholar)
        mineru_key = credential("mineru", config.mineru)
        materials_key = credential("materials-project", config.data.materials_project)
        cas_key = credential("cas", config.data.cas_common_chemistry)
        media_keys = {
            name: credential(name, section) for name, section in config.media.providers.items()
        }
        secrets = tuple(value for resolved in credentials.values() if (value := resolved.reveal()))
        self.known_secrets = secrets
        self.http = BoundedHttpClient(
            timeout_seconds=config.runtime.request_timeout_seconds,
            max_response_bytes=config.runtime.max_response_bytes,
            known_secrets=secrets,
        )
        await self.http.__aenter__()
        service_transport = CoreServiceTransport(self.http)
        literature_transport = CoreLiteratureTransport(self.http)
        rp = config.research.providers
        literature = LiteratureRouter(
            [
                SemanticScholarProvider(
                    literature_transport,
                    api_key=research_keys.get("semantic-scholar"),
                    enabled=rp["semantic-scholar"].enabled,
                ),
                OpenAlexProvider(
                    literature_transport,
                    api_key=research_keys.get("openalex"),
                    email=rp["openalex"].email,
                    enabled=rp["openalex"].enabled,
                ),
                PubMedProvider(
                    literature_transport,
                    api_key=research_keys.get("pubmed"),
                    email=rp["pubmed"].email,
                    tool=rp["pubmed"].tool,
                    enabled=rp["pubmed"].enabled,
                ),
                ArxivProvider(literature_transport, enabled=rp["arxiv"].enabled),
                CrossrefProvider(
                    literature_transport, email=rp["crossref"].email, enabled=rp["crossref"].enabled
                ),
                UnpaywallProvider(
                    literature_transport,
                    email=rp["unpaywall"].email,
                    enabled=rp["unpaywall"].enabled,
                ),
                EasyScholarProvider(
                    literature_transport,
                    api_key=research_keys.get("easyscholar"),
                    enabled=rp["easyscholar"].enabled,
                ),
            ]
        )
        ai4scholar = (
            Ai4ScholarService(
                service_transport,
                api_key=ai_key,
                base_url=config.ai4scholar.base_url,
                allow_paid=config.ai4scholar.allow_paid,
                timeout_seconds=config.ai4scholar.timeout_seconds,
                figure_timeout_seconds=config.ai4scholar.figure_timeout_seconds,
                max_response_bytes=config.ai4scholar.max_response_bytes,
                output_root=config.output.root_directory,
                max_artifact_bytes=config.ai4scholar.max_artifact_bytes,
                artifact_timeout_seconds=config.ai4scholar.artifact_timeout_seconds,
            )
            if config.ai4scholar.enabled and ai_key
            else None
        )
        mineru = (
            MinerUService(
                service_transport,
                token=mineru_key,
                base_url=config.mineru.base_url,
                model=config.mineru.model,
                cache_directory=config.mineru.cache_directory,
                max_pdf_bytes=config.mineru.max_pdf_bytes,
                poll_interval_seconds=config.mineru.poll_interval_seconds,
                poll_timeout_seconds=config.mineru.poll_timeout_seconds,
                allow_external_upload=config.mineru.allow_external_upload,
            )
            if config.mineru.enabled and mineru_key
            else None
        )
        materials = (
            MaterialsProjectService(
                service_transport,
                api_key=materials_key,
                base_url=config.data.materials_project.base_url,
                max_pages=config.data.materials_project.max_pages,
            )
            if config.data.materials_project.enabled and materials_key
            else None
        )
        chemistry = ChemistryService(
            service_transport,
            api_key=cas_key,
            base_url=config.data.cas_common_chemistry.base_url,
            contract_file=config.data.cas_common_chemistry.contract_file,
        )
        media_settings = []
        for name, section in config.media.providers.items():
            options = dict(section.options)
            if section.project:
                options["project"] = section.project
            if section.location:
                options["location"] = section.location
            media_settings.append(
                MediaProviderSettings(
                    name,
                    section.enabled,
                    media_keys.get(name),
                    section.base_url,
                    {model: set(pin.capabilities) for model, pin in section.models.items()},
                    options,
                )
            )
        media = MediaService(
            service_transport,
            media_settings,
            output_root=config.output.root_directory,
            workspace_roots=tuple(config.runtime.workspace_roots),
            allow_external_upload=config.media.allow_external_upload,
            allow_paid=config.media.allow_paid,
            max_input_bytes=config.media.max_input_bytes,
            max_artifact_bytes=config.media.max_artifact_bytes,
        )
        self.services = ApplicationServices(
            literature,
            ZoteroService(
                service_transport,
                base_url=config.zotero.base_url,
                max_items=config.zotero.max_items,
                max_indexed_text_bytes=config.zotero.max_indexed_text_bytes,
            ),
            SyncService(
                config.output.root_directory,
                namespace=config.sync.namespace,
                backup=config.sync.backup,
            ),
            chemistry,
            ai4scholar,
            mineru,
            materials,
            media,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self.http is not None:
            await self.http.__aexit__(*args)
        self.http = None
        self.services = None

    def require_services(self) -> ApplicationServices:
        if self.services is None:
            raise RuntimeError("OmniScholarApplication is not running")
        return self.services

    async def status(self) -> dict[str, Any]:
        services = self.require_services()
        config = self.loaded.config
        providers = [asdict(status) for status in services.literature.statuses()]
        media_models = [asdict(item) for item in await services.media.models()]
        return {
            "configSource": self.loaded.source.status(),
            "enabledToolGroups": config.tools.groups.model_dump(by_alias=True),
            "disabledTools": sorted(config.tools.disabled),
            "providers": providers,
            "credentials": self.credential_status,
            "zotero": {
                "enabled": config.zotero.enabled,
                "baseUrl": config.zotero.base_url,
                "readOnly": True,
                "liveStatus": "not_checked",
            },
            "mineru": {
                "enabled": config.mineru.enabled,
                "configured": services.mineru is not None,
                "model": config.mineru.model,
            },
            "materials": {
                "enabled": config.data.materials_project.enabled,
                "configured": services.materials is not None,
            },
            "chemistry": services.chemistry.sources(),
            "imageProviders": media_models,
            "defaults": {
                "citationStyle": config.defaults.citation_style,
                "imageProvider": config.defaults.default_image_provider,
                "language": config.defaults.language,
            },
            "runtime": {
                "python": config.runtime.python,
                "maxOutputBytes": config.runtime.max_output_bytes,
                "maxOutputLines": config.runtime.max_output_lines,
                "requestTimeoutSeconds": config.runtime.request_timeout_seconds,
            },
        }
