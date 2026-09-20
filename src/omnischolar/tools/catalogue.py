"""Definitions for every OmniScholar tool."""

from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Any

from omnischolar.core import OmniScholarError, ToolExecutionContext, atomic_write
from omnischolar.providers.literature import SearchRequest
from omnischolar.registry import (
    CostClass,
    SideEffects,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
    ToolGroup,
)


def obj(properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = list(required)
    return schema


def string_enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


STRING = {"type": "string"}
BOOL = {"type": "boolean"}
POSITIVE = {"type": "integer", "minimum": 1}
NONNEGATIVE = {"type": "integer", "minimum": 0}
OUTPUT_SCHEMA = obj({"ok": BOOL, "data": {}, "error": {}, "output": {}}, ("ok",))


def _services(app: Any) -> Any:
    return app.require_services()


def _required(value: Any, name: str, service: str) -> Any:
    if value is None:
        raise OmniScholarError(
            "service_unavailable", f"{service} is disabled or not configured", category="config"
        )
    return value


_IMAGE_LINK = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")


def _normalized_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _prepare_publication_content(
    title: str,
    markdown: str,
    assets: dict[str, bytes],
    *,
    asset_filename_template: str = "image-{index}{extension}",
    asset_filename_separator: str = "-",
) -> tuple[str, dict[str, bytes]]:
    body = markdown.lstrip("\ufeff\r\n")
    first_line, separator, remainder = body.partition("\n")
    if first_line.startswith("# "):
        similarity = difflib.SequenceMatcher(
            None,
            _normalized_title(title),
            _normalized_title(first_line[2:].strip()),
        ).ratio()
        if similarity >= 0.9:
            body = remainder.lstrip("\r\n") if separator else ""

    target_to_asset: dict[str, str] = {}
    normalized_names: dict[str, str] = {}
    for original_name in assets:
        normalized_name = original_name.replace("\\", "/")
        basename = Path(normalized_name).name
        normalized_names[original_name] = normalized_name
        for target in (
            normalized_name,
            f"./{normalized_name}",
            basename,
            f"assets/{basename}",
        ):
            existing = target_to_asset.get(target)
            if existing is not None and existing != original_name:
                raise OmniScholarError(
                    "asset_name_collision",
                    "Generated assets have ambiguous reference names",
                    category="filesystem",
                )
            target_to_asset[target] = original_name

    ordered_assets: list[str] = []
    for match in _IMAGE_LINK.finditer(body):
        original_name = target_to_asset.get(match.group(2).strip())
        if original_name is not None and original_name not in ordered_assets:
            ordered_assets.append(original_name)
    ordered_assets.extend(
        sorted(
            (name for name in assets if name not in ordered_assets),
            key=lambda name: normalized_names[name],
        )
    )

    renamed: dict[str, str] = {}
    used_names: set[str] = set()
    for index, original_name in enumerate(ordered_assets, start=1):
        original_path = Path(normalized_names[original_name])
        original_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", original_path.stem).strip(" .")
        candidate = asset_filename_template.format(
            index=index,
            original=original_stem or f"image-{index}",
            extension=original_path.suffix.lower() or ".bin",
            separator=asset_filename_separator,
        )
        candidate = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", candidate).strip(" .")
        if not candidate or Path(candidate).name != candidate:
            raise OmniScholarError(
                "unsafe_asset_name", "Configured asset filename is unsafe", category="filesystem"
            )
        if candidate in used_names:
            raise OmniScholarError(
                "asset_name_collision", "Configured asset filenames are not unique", category="filesystem"
            )
        renamed[original_name] = candidate
        used_names.add(candidate)

    def replace_reference(match: re.Match[str]) -> str:
        original_name = target_to_asset.get(match.group(2).strip())
        if original_name is None:
            return match.group(0)
        return f"{match.group(1)}assets/{renamed[original_name]}{match.group(3)}"

    body = _IMAGE_LINK.sub(replace_reference, body)
    prepared_assets = {renamed[name]: assets[name] for name in ordered_assets}
    return f"# {title}\n\n{body}", prepared_assets


def _sync_parse_arguments(arguments: dict[str, Any], action: str) -> dict[str, Any]:
    publish_force = action in {"repair", "restore", "reparse"} or arguments.get("force", False)
    return {
        **arguments,
        "_parseForce": action == "reparse",
        "_publishForce": publish_force,
    }


async def status_tool(_arguments: dict[str, Any], _context: ToolExecutionContext, app: Any) -> Any:
    return await app.status()


async def research_sources(
    _arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return [asdict(item) for item in _services(app).literature.statuses()]


async def literature_search(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    config = app.loaded.config
    providers = arguments.get("providers") or (
        [arguments["provider"]]
        if arguments.get("provider")
        else config.defaults.preferred_literature_providers
    )
    request = SearchRequest(
        arguments["query"],
        arguments.get("limit", config.defaults.literature_limit),
        arguments.get("cursor"),
        arguments.get("page"),
        arguments.get("yearFrom"),
        arguments.get("yearTo"),
        arguments.get("openAccessOnly", False),
        tuple(arguments.get("fields", [])),
    )
    return await _services(app).literature.search(
        request, providers, fallback=arguments.get("fallback", config.research.fallback)
    )


async def literature_get(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).literature.get(arguments["provider"], arguments["id"])


async def literature_author(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).literature.author(
        arguments["provider"],
        arguments["action"],
        author_id=arguments.get("authorId"),
        query=arguments.get("query"),
        limit=arguments.get("limit", 20),
        offset=arguments.get("offset", 0),
        fields=tuple(arguments.get("fields", [])),
    )


async def literature_graph(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).literature.graph(
        arguments["provider"],
        arguments["id"],
        arguments["kind"],
        limit=arguments.get("limit", 20),
        cursor=arguments.get("cursor"),
    )


async def journal_metrics(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).literature.journal_metrics(
        arguments["provider"], arguments["query"]
    )


async def literature_fulltext(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    result = await _services(app).literature.fulltext(
        arguments["provider"], arguments["id"], fetch=arguments.get("fetch", False)
    )
    content = result.pop("content", None)
    if content is not None:
        raw = content if isinstance(content, bytes) else str(content).encode()
        digest = hashlib.sha256(raw).hexdigest()
        extension = ".pdf" if raw.startswith(b"%PDF-") else ".xml"
        path = await atomic_write(
            app.loaded.config.output.root_directory, f"fulltext/{digest}{extension}", raw
        )
        result["artifact"] = {"path": str(path), "bytes": len(raw)}
    return result


async def zotero_collections(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).zotero.collections(
        arguments.get("action", "list"), key=arguments.get("key"), limit=arguments.get("limit", 500)
    )


async def zotero_search(arguments: dict[str, Any], _context: ToolExecutionContext, app: Any) -> Any:
    return await _services(app).zotero.search(
        arguments.get("query", ""),
        collection_key=arguments.get("collectionKey"),
        item_type=arguments.get("itemType"),
        sort=arguments.get("sort"),
        direction=arguments.get("direction"),
        limit=arguments.get("limit", 50),
    )


async def zotero_item(arguments: dict[str, Any], _context: ToolExecutionContext, app: Any) -> Any:
    return await _services(app).zotero.item(
        arguments["key"],
        aggregate=arguments.get("mode", "item") == "aggregate",
        attachment_key=arguments.get("attachmentKey"),
    )


async def literature_read(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).reader.read(arguments)


async def literature_focus(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).retriever.search(arguments)


async def literature_locate(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).reader.locate(arguments)


async def literature_context(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).reading_context.execute(arguments)


async def parse_tool(arguments: dict[str, Any], context: ToolExecutionContext, app: Any) -> Any:
    services = _services(app)
    mineru = _required(services.mineru, "mineru", "MinerU")
    paper = await services.zotero.item(
        arguments["key"], attachment_key=arguments.get("attachmentKey")
    )
    selected = paper.get("selectedPdf")
    if not selected or not selected.get("localPath"):
        raise OmniScholarError(
            "pdf_unavailable", "Selected Zotero PDF is not locally readable", category="filesystem"
        )
    parsed = await mineru.parse_pdf(
        Path(selected["localPath"]),
        context,
        language=arguments.get("language", app.loaded.config.defaults.language),
        enable_formula=arguments.get("enableFormula", True),
        enable_table=arguments.get("enableTable", True),
        is_ocr=arguments.get("isOcr", False),
        force=arguments.get("_parseForce", arguments.get("force", False)),
    )
    markdown, assets = _prepare_publication_content(
        paper.get("title", "Untitled"),
        parsed.markdown,
        parsed.assets,
        asset_filename_template=app.loaded.config.output.asset_filename_template,
        asset_filename_separator=app.loaded.config.output.filename_separator,
    )
    published = await services.sync.publish(
        paper,
        markdown,
        assets,
        parse_key=parsed.parse_key,
        parser_version=parsed.parser_version,
        force=arguments.get("_publishForce", arguments.get("force", False)),
    )
    return {**parsed.summary(), "publication": published}


async def sync_tool(arguments: dict[str, Any], context: ToolExecutionContext, app: Any) -> Any:
    services = _services(app)
    action = arguments["action"]
    if action == "status" and not arguments.get("key"):
        return await services.sync.manifest()
    if action == "recover":
        return await services.sync.recover()
    if not arguments.get("key"):
        raise OmniScholarError(
            "key_required", f"Sync action {action} requires a Zotero key", category="validation"
        )
    paper = await services.zotero.item(
        arguments["key"], attachment_key=arguments.get("attachmentKey")
    )
    plan = await services.sync.plan(paper)
    if action in {"status", "plan"}:
        return asdict(plan)
    if action == "exclude":
        return await services.sync.exclude(plan.publication_id, reason=arguments.get("reason"))
    if action == "unexclude":
        return await services.sync.unexclude(plan.publication_id)
    if action in {"apply", "repair", "restore", "reparse"}:
        if action == "apply" and arguments.get("force") is not True:
            raise OmniScholarError(
                "force_required", "Sync apply requires force=true", category="authorization"
            )
        parse_args = _sync_parse_arguments(arguments, action)
        return await parse_tool(parse_args, context, app)
    raise OmniScholarError(
        "invalid_action", f"Unknown sync action: {action}", category="validation"
    )


async def _ai(
    method: str, arguments: dict[str, Any], context: ToolExecutionContext, app: Any
) -> Any:
    service = _required(_services(app).ai4scholar, "ai4scholar", "Ai4Scholar")
    return await getattr(service, method)(arguments, context)


async def ai_search(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("search", a, c, app)


async def ai_paper(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("paper", a, c, app)


async def ai_author(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("author", a, c, app)


async def ai_batch(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("batch", a, c, app)


async def ai_recommend(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("recommend", a, c, app)


async def ai_cite(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("cite", a, c, app)


async def ai_snippets(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("snippets", a, c, app)


async def ai_dataset(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("dataset", a, c, app)


async def ai_journal(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("journal", a, c, app)


async def ai_candidates(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("citation_candidates", a, c, app)


async def ai_figure(a: dict[str, Any], c: ToolExecutionContext, app: Any) -> Any:
    return await _ai("figure", a, c, app)


async def ai_credits(_arguments: dict[str, Any], context: ToolExecutionContext, app: Any) -> Any:
    service = _required(_services(app).ai4scholar, "ai4scholar", "Ai4Scholar")
    return await service.credits(context)


async def materials_capabilities(
    _arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    service = _required(_services(app).materials, "materials", "Materials Project")
    return service.capabilities()


async def materials_search(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    service = _required(_services(app).materials, "materials", "Materials Project")
    return await service.search(
        arguments.get("filters", {}),
        fields=arguments.get("fields"),
        limit=arguments.get("limit", 20),
        page=arguments.get("page", 1),
    )


async def materials_route_search(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    service = _required(_services(app).materials, "materials", "Materials Project")
    return await service.route_search(
        arguments["route"],
        arguments.get("filters", {}),
        fields=arguments.get("fields"),
        limit=arguments.get("limit", 20),
        page=arguments.get("page", 1),
    )


async def materials_get(arguments: dict[str, Any], _context: ToolExecutionContext, app: Any) -> Any:
    service = _required(_services(app).materials, "materials", "Materials Project")
    return await service.get(
        arguments["materialId"],
        fields=arguments.get("fields"),
        route=arguments.get("route", "summary"),
    )


async def materials_advanced(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    service = _required(_services(app).materials, "materials", "Materials Project")
    return await service.advanced(arguments["action"], arguments)


async def materials_export(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    service = _required(_services(app).materials, "materials", "Materials Project")
    return await service.export(
        arguments["records"],
        format=arguments["format"],
        output_root=app.loaded.config.output.root_directory,
        relative_path=arguments["path"],
    )


async def chemical_sources(
    _arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return _services(app).chemistry.sources()


async def chemical_search(
    arguments: dict[str, Any], _context: ToolExecutionContext, app: Any
) -> Any:
    return await _services(app).chemistry.search(
        arguments["query"], limit=arguments.get("limit", 20)
    )


async def chemical_get(arguments: dict[str, Any], _context: ToolExecutionContext, app: Any) -> Any:
    return await _services(app).chemistry.get(arguments["id"])


async def image_models(arguments: dict[str, Any], _context: ToolExecutionContext, app: Any) -> Any:
    return [
        asdict(item)
        for item in await _services(app).media.models(
            arguments.get("provider"), discover=arguments.get("discover", True)
        )
    ]


def _image_request_options(arguments: dict[str, Any]) -> dict[str, Any]:
    options = dict(arguments.get("options") or {})
    aliases = {
        "size": "size",
        "aspectRatio": "aspect_ratio",
        "resolution": "resolution",
        "background": "background",
        "outputFormat": "output_format",
        "quality": "quality",
        "n": "n",
        "negativePrompt": "negative_prompt",
        "seed": "seed",
    }
    for argument, option in aliases.items():
        if argument in arguments:
            options[option] = arguments[argument]
    return options


async def image_generate(arguments: dict[str, Any], context: ToolExecutionContext, app: Any) -> Any:
    references = arguments.get("references", [])
    capability = "image-to-image" if references else "text-to-image"
    return await _services(app).media.execute(
        provider_id=arguments.get("provider") or app.loaded.config.defaults.default_image_provider,
        capability=capability,
        prompt=arguments["prompt"],
        context=context,
        model=arguments.get("model"),
        references=references,
        options=_image_request_options(arguments),
    )


async def image_edit(arguments: dict[str, Any], context: ToolExecutionContext, app: Any) -> Any:
    return await _services(app).media.execute(
        provider_id=arguments.get("provider") or app.loaded.config.defaults.default_image_provider,
        capability="edit",
        prompt=arguments["prompt"],
        context=context,
        model=arguments.get("model"),
        references=arguments["references"],
        options=_image_request_options(arguments),
    )


async def image_service(arguments: dict[str, Any], _context: ToolExecutionContext, app: Any) -> Any:
    return await _services(app).media.service(arguments["provider"], arguments["action"], arguments)


def create_tool_definitions() -> list[ToolDefinition]:
    definitions: list[ToolDefinition] = []

    def add(
        name: str,
        description: str,
        schema: dict[str, Any],
        execute: ToolExecutor,
        *,
        group: ToolGroup,
        capabilities: tuple[str, ...],
        network: bool = False,
        credentials: tuple[str, ...] = (),
        side: SideEffects = "none",
        cost: CostClass = "free",
        interaction: bool = False,
    ) -> None:
        definitions.append(
            ToolDefinition(
                name=name,
                description=description,
                input_schema=schema,
                output_schema=OUTPUT_SCHEMA,
                execute=execute,
                group=group,
                capabilities=capabilities,
                requires_network=network,
                requires_credentials=credentials,
                side_effects=side,
                cost_class=cost,
                annotations=ToolAnnotations(
                    side == "none",
                    network,
                    False,
                    description,
                    interaction,
                ),
            )
        )

    add(
        "omnischolar_status",
        "Report configuration source, enabled groups, provider and credential presence, local services, defaults, and runtime without revealing secrets.",
        obj({}),
        status_tool,
        group="runtime",
        capabilities=("runtime.status",),
    )

    async def capabilities_tool(_a: dict[str, Any], _c: ToolExecutionContext, app: Any) -> Any:
        return [
            {
                "name": item.name,
                "group": item.group,
                "capabilities": item.capabilities,
                "sideEffects": item.side_effects,
                "requiresNetwork": item.requires_network,
                "requiresCredentials": item.requires_credentials,
                "costClass": item.cost_class,
                "enabled": app.registry.is_enabled(item) if hasattr(app, "registry") else True,
            }
            for item in definitions
        ]

    add(
        "omnischolar_capabilities",
        "List available tools with their capabilities, effects, credentials, and cost classes.",
        obj({}),
        capabilities_tool,
        group="runtime",
        capabilities=("runtime.capabilities",),
    )
    add(
        "research_sources",
        "List first-party literature providers and verified capability status without network access.",
        obj({}),
        research_sources,
        group="literature",
        capabilities=("literature.sources",),
    )
    add(
        "literature_search",
        "Search selected official literature APIs with bounded pagination and ordered retryable fallback.",
        obj(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 2000},
                "provider": STRING,
                "providers": {"type": "array", "items": STRING, "maxItems": 8},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                "cursor": STRING,
                "page": POSITIVE,
                "yearFrom": {"type": "integer", "minimum": 1000, "maximum": 3000},
                "yearTo": {"type": "integer", "minimum": 1000, "maximum": 3000},
                "openAccessOnly": BOOL,
                "fields": {"type": "array", "items": STRING, "maxItems": 50},
                "fallback": BOOL,
            },
            ("query",),
        ),
        literature_search,
        group="literature",
        capabilities=("literature.search",),
        network=True,
    )
    add(
        "literature_get",
        "Fetch one normalized literature record from an explicitly selected provider.",
        obj({"provider": STRING, "id": STRING}, ("provider", "id")),
        literature_get,
        group="literature",
        capabilities=("literature.lookup",),
        network=True,
    )
    add(
        "literature_author",
        "Search a Semantic Scholar author, fetch author details, or list the author's papers.",
        obj(
            {
                "provider": STRING,
                "action": string_enum("search", "detail", "papers"),
                "authorId": STRING,
                "query": STRING,
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                "offset": {"type": "integer", "minimum": 0},
                "fields": {"type": "array", "items": STRING, "maxItems": 50},
            },
            ("provider", "action"),
        ),
        literature_author,
        group="literature",
        capabilities=("literature.lookup",),
        network=True,
    )
    add(
        "literature_graph",
        "Fetch bounded references, citations, or recommendations from a selected provider.",
        obj(
            {
                "provider": STRING,
                "id": STRING,
                "kind": string_enum("references", "citations", "recommendations"),
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                "cursor": STRING,
            },
            ("provider", "id", "kind"),
        ),
        literature_graph,
        group="literature",
        capabilities=(
            "literature.references",
            "literature.citations",
            "literature.recommendations",
        ),
        network=True,
    )
    add(
        "journal_metrics",
        "Retrieve journal metrics only from a provider with a verified contract.",
        obj({"provider": STRING, "query": STRING}, ("provider", "query")),
        journal_metrics,
        group="literature",
        capabilities=("journal.metrics",),
        network=True,
    )
    add(
        "literature_fulltext",
        "Resolve or fetch legally available full text without bypassing provider entitlements.",
        obj({"provider": STRING, "id": STRING, "fetch": BOOL}, ("provider", "id")),
        literature_fulltext,
        group="literature",
        capabilities=("fulltext.resolve", "fulltext.fetch"),
        network=True,
        side="filesystem",
    )
    add(
        "zotero_collections",
        "List/read local Zotero collections and collection items through GET-only loopback API.",
        obj(
            {
                "action": string_enum("list", "read", "items"),
                "key": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5000},
            }
        ),
        zotero_collections,
        group="zotero",
        capabilities=("zotero.collections",),
        network=True,
    )
    add(
        "zotero_search",
        "Search or browse top-level Zotero items through the read-only Local API.",
        obj(
            {
                "query": STRING,
                "collectionKey": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "itemType": STRING,
                "sort": string_enum("dateAdded", "dateModified", "title", "creator", "date"),
                "direction": string_enum("asc", "desc"),
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            }
        ),
        zotero_search,
        group="zotero",
        capabilities=("zotero.search",),
        network=True,
    )
    add(
        "zotero_item",
        "Read one Zotero item (metadata by default) or explicitly aggregate notes, annotations, attachments, indexed text and PDF location.",
        obj(
            {
                "key": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "mode": string_enum("item", "aggregate"),
                "attachmentKey": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
            },
            ("key",),
        ),
        zotero_item,
        group="zotero",
        capabilities=("zotero.item", "zotero.aggregate"),
        network=True,
    )
    add(
        "omnischolar_read",
        "Read bounded, mode-aware excerpts from locally published papers without returning the full document by default.",
        obj(
            {
                "key": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "keys": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                    "minItems": 1,
                    "maxItems": 8,
                },
                "attachmentKey": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "mode": string_enum("full", "figures", "formulas", "paragraphs", "compare", "review"),
                "section": {"type": "string", "maxLength": 500},
                "query": {"type": "string", "maxLength": 1000},
                "cursor": NONNEGATIVE,
                "maxChars": {"type": "integer", "minimum": 500, "maximum": 12000},
                "maxItems": {"type": "integer", "minimum": 1, "maximum": 50},
                "contextId": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
            },
            ("mode",),
        ),
        literature_read,
        group="literature",
        capabilities=("literature.read", "literature.fulltext", "literature.figures", "literature.formulas"),
    )
    add(
        "omnischolar_focus",
        "Search locally published Zotero papers for bounded evidence paragraphs with stable line locators; does not return full documents.",
        obj(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                "keys": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                    "maxItems": 50,
                },
                "section": {"type": "string", "maxLength": 500},
                "topK": {"type": "integer", "minimum": 1, "maximum": 50},
                "maxChars": {"type": "integer", "minimum": 500, "maximum": 8000},
                "maxPerDocument": {"type": "integer", "minimum": 1, "maximum": 10},
                "includeContext": BOOL,
                "contextId": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
            },
            ("query",),
        ),
        literature_focus,
        group="literature",
        capabilities=("literature.focus", "literature.retrieval", "literature.evidence"),
    )
    add(
        "omnischolar_locate",
        "Locate matching paragraphs in one parsed Zotero paper and return bounded text with heading, line, and character anchors.",
        obj(
            {
                "key": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "attachmentKey": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                "section": {"type": "string", "maxLength": 500},
                "matchMode": string_enum("allTerms", "phrase"),
                "maxItems": {"type": "integer", "minimum": 1, "maximum": 50},
                "maxChars": {"type": "integer", "minimum": 500, "maximum": 8000},
                "contextId": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
            },
            ("key", "query"),
        ),
        literature_locate,
        group="literature",
        capabilities=("literature.locate", "literature.paragraphs", "literature.evidence"),
    )
    add(
        "omnischolar_context",
        "Open, append, list, page, or clear bounded local evidence contexts for multi-turn literature work.",
        obj(
            {
                "action": string_enum("open", "add", "list", "get", "clear"),
                "contextId": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
                "title": {"type": "string", "maxLength": 200},
                "cursor": NONNEGATIVE,
                "maxItems": {"type": "integer", "minimum": 1, "maximum": 50},
                "maxChars": {"type": "integer", "minimum": 500, "maximum": 12000},
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 50,
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "maxLength": 4000},
                            "excerpt": {"type": "string", "maxLength": 4000},
                            "source": {"type": "object", "additionalProperties": {"type": "string"}},
                            "zoteroKey": {"type": "string"},
                            "title": {"type": "string"},
                            "heading": {"type": "string"},
                            "locator": {"type": "string"},
                            "markdownPath": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            ("action",),
        ),
        literature_context,
        group="literature",
        capabilities=("literature.context.open", "literature.context.append", "literature.context.read"),
        side="filesystem",
    )
    parse_schema = obj(
        {
            "key": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
            "attachmentKey": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
            "language": STRING,
            "enableFormula": BOOL,
            "enableTable": BOOL,
            "isOcr": BOOL,
            "force": BOOL,
        },
        ("key",),
    )
    add(
        "omnischolar_parse",
        "Parse a Zotero PDF through MinerU v4 with deterministic cache and transactional local publication.",
        parse_schema,
        parse_tool,
        group="parsing",
        capabilities=("pdf.parse", "sync.publish"),
        network=True,
        credentials=("mineru",),
        side="external-upload",
        cost="metered",
        interaction=True,
    )
    add(
        "omnischolar_sync",
        "Plan and control conservative incremental sync, conflict, recovery, exclude, restore, repair and reparse actions.",
        obj(
            {
                "action": string_enum(
                    "status",
                    "plan",
                    "apply",
                    "repair",
                    "restore",
                    "exclude",
                    "unexclude",
                    "reparse",
                    "recover",
                ),
                "key": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "attachmentKey": {"type": "string", "pattern": "^[A-Z0-9]{8}$"},
                "reason": {"type": "string", "maxLength": 500},
                "force": BOOL,
            },
            ("action",),
        ),
        sync_tool,
        group="parsing",
        capabilities=("sync.plan", "sync.apply", "sync.recovery"),
        network=True,
        side="filesystem",
        interaction=True,
    )

    ai_common: dict[str, Any] = {}
    add(
        "ai4scholar_search",
        "Search Semantic Scholar, PubMed, Google Scholar, or Google Patents through explicitly selected paid Ai4Scholar.",
        obj(
            {
                **ai_common,
                "source": string_enum(
                    "semantic_scholar", "pubmed", "google_scholar", "google_patents"
                ),
                "query": STRING,
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "offset": NONNEGATIVE,
                "page": POSITIVE,
                "fields": STRING,
                "semanticMode": string_enum("relevance", "bulk", "match", "autocomplete"),
                "token": STRING,
                "publicationTypes": STRING,
                "publicationDateOrYear": STRING,
                "minDate": STRING,
                "maxDate": STRING,
                "yearFrom": NONNEGATIVE,
                "yearTo": NONNEGATIVE,
                "sort": STRING,
                "openAccessOnly": BOOL,
                "minCitationCount": NONNEGATIVE,
                "venue": STRING,
                "fieldsOfStudy": STRING,
                "cites": STRING,
                "cluster": STRING,
                "reviewOnly": BOOL,
                "sortByDate": BOOL,
                "status": string_enum("GRANT", "APPLICATION"),
                "patentType": string_enum("PATENT", "DESIGN"),
                "country": STRING,
                "language": STRING,
                "inventor": STRING,
                "assignee": STRING,
                "before": STRING,
                "after": STRING,
            },
            ("source", "query"),
        ),
        ai_search,
        group="ai4scholar",
        capabilities=("ai4scholar.search",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_paper",
        "Read Ai4Scholar paper detail, graph, authors, related records, or recommendations.",
        obj(
            {
                **ai_common,
                "source": string_enum("semantic_scholar", "pubmed"),
                "action": string_enum(
                    "detail", "citations", "references", "related", "authors", "recommendations"
                ),
                "id": STRING,
                "fields": STRING,
                "limit": POSITIVE,
                "offset": NONNEGATIVE,
                "recommendationPool": string_enum("recent", "all-cs"),
                "publicationDateOrYear": STRING,
            },
            ("source", "action", "id"),
        ),
        ai_paper,
        group="ai4scholar",
        capabilities=("ai4scholar.paper",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_author",
        "Search and inspect Semantic Scholar or Google Scholar authors through Ai4Scholar.",
        obj(
            {
                **ai_common,
                "source": string_enum("semantic_scholar", "google_scholar"),
                "action": string_enum("search", "detail", "papers"),
                "query": STRING,
                "authorId": STRING,
                "fields": STRING,
                "limit": POSITIVE,
                "offset": NONNEGATIVE,
                "sort": STRING,
                "afterAuthor": STRING,
                "publicationDateOrYear": STRING,
            },
            ("source", "action"),
        ),
        ai_author,
        group="ai4scholar",
        capabilities=("ai4scholar.author",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_batch",
        "Fetch bounded Semantic Scholar/PubMed batch records through Ai4Scholar.",
        obj(
            {
                **ai_common,
                "source": string_enum("semantic_papers", "semantic_authors", "pubmed_papers"),
                "ids": {"type": "array", "items": STRING, "minItems": 1, "maxItems": 1000},
                "fields": STRING,
            },
            ("source", "ids"),
        ),
        ai_batch,
        group="ai4scholar",
        capabilities=("ai4scholar.batch",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_recommend",
        "Recommend papers from positive and negative seed IDs through Ai4Scholar.",
        obj(
            {
                **ai_common,
                "positivePaperIds": {"type": "array", "items": STRING, "minItems": 1},
                "negativePaperIds": {"type": "array", "items": STRING},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                "fields": STRING,
            },
            ("positivePaperIds",),
        ),
        ai_recommend,
        group="ai4scholar",
        capabilities=("ai4scholar.recommend",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_cite",
        "Retrieve citation formats for a Google Scholar result through Ai4Scholar.",
        obj({**ai_common, "paperId": STRING, "language": STRING}, ("paperId",)),
        ai_cite,
        group="citation",
        capabilities=("citation.format",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_snippets",
        "Search Semantic Scholar full-text snippets through Ai4Scholar.",
        obj(
            {
                **ai_common,
                "query": STRING,
                "fields": STRING,
                "paperIds": STRING,
                "authors": STRING,
                "year": STRING,
                "publicationDateOrYear": STRING,
                "venue": STRING,
                "fieldsOfStudy": STRING,
                "minCitationCount": NONNEGATIVE,
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            ("query",),
        ),
        ai_snippets,
        group="ai4scholar",
        capabilities=("ai4scholar.snippets",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_credits",
        "Check Ai4Scholar credit balance using its documented free endpoint.",
        obj({}),
        ai_credits,
        group="ai4scholar",
        capabilities=("ai4scholar.credits",),
        network=True,
        credentials=("ai4scholar",),
    )
    add(
        "ai4scholar_dataset",
        "Inspect Semantic Scholar dataset releases/downloads/diffs through Ai4Scholar.",
        obj(
            {
                **ai_common,
                "action": string_enum(
                    "list_releases", "release_detail", "dataset_download", "diffs"
                ),
                "releaseId": STRING,
                "datasetName": STRING,
                "startReleaseId": STRING,
                "endReleaseId": STRING,
            },
            ("action",),
        ),
        ai_dataset,
        group="ai4scholar",
        capabilities=("ai4scholar.dataset",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_journal",
        "Search JCR/CAS metrics or recommend journals through Ai4Scholar.",
        obj(
            {
                **ai_common,
                "action": string_enum("search", "detail", "categories", "recommend"),
                "id": STRING,
                "query": STRING,
                "category": STRING,
                "jcrQuartile": STRING,
                "casQuartile": STRING,
                "minImpactFactor": {"type": "number", "minimum": 0},
                "maxImpactFactor": {"type": "number", "minimum": 0},
                "isOpenAccess": BOOL,
                "title": STRING,
                "abstract": STRING,
                "limit": NONNEGATIVE,
                "offset": NONNEGATIVE,
                "sort": STRING,
                "fieldGroup": STRING,
                "topN": POSITIVE,
                "fields": {"type": "array", "items": STRING, "maxItems": 100},
                "categories": {"type": "array", "items": STRING, "maxItems": 100},
                "filters": {"type": "object"},
            },
            ("action",),
        ),
        ai_journal,
        group="ai4scholar",
        capabilities=("ai4scholar.journal",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_citation_candidates",
        "Find review-required citation candidates for claims; never inserts citations automatically.",
        obj(
            {
                **ai_common,
                "text": {"type": "string", "minLength": 20, "maxLength": 10000},
                "mode": string_enum("markers", "statements"),
                "maxClaims": {"type": "integer", "minimum": 1, "maximum": 20},
                "candidatesPerClaim": {"type": "integer", "minimum": 1, "maximum": 5},
                "year": STRING,
                "fieldsOfStudy": STRING,
                "citationStyle": STRING,
            },
            ("text",),
        ),
        ai_candidates,
        group="citation",
        capabilities=("citation.candidates",),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "ai4scholar_figure",
        "Generate or revise scientific figure drafts through Ai4Scholar Nano with integrity warning.",
        obj(
            {
                **ai_common,
                "action": string_enum(
                    "smart",
                    "generate",
                    "edit",
                    "style",
                    "compose",
                    "iterate",
                    "critic",
                    "vectorize",
                ),
                "prompt": STRING,
                "model": STRING,
                "imageSize": STRING,
                "aspectRatio": STRING,
                "images": {"type": "array", "items": STRING, "maxItems": 8},
                "stylePreset": STRING,
                "lang": STRING,
                "vectorizeMode": STRING,
            },
            ("action",),
        ),
        ai_figure,
        group="media",
        capabilities=("media.generate", "media.edit", "media.vectorize"),
        network=True,
        credentials=("ai4scholar",),
        side="paid",
        cost="paid",
        interaction=True,
    )

    fields = {"type": "array", "items": STRING, "maxItems": 100}
    add(
        "materials_capabilities",
        "Report implemented Materials Project routes, fields and local derived limitations.",
        obj({}),
        materials_capabilities,
        group="materials",
        capabilities=("materials.capabilities",),
        credentials=("materials-project",),
    )
    add(
        "materials_search",
        "Search Materials Project summary records with bounded filters and explicit field status.",
        obj(
            {
                "filters": {"type": "object"},
                "fields": fields,
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                "page": POSITIVE,
            }
        ),
        materials_search,
        group="materials",
        capabilities=("materials.search",),
        network=True,
        credentials=("materials-project",),
    )
    add(
        "materials_route_search",
        "Search one verified Materials Project REST route.",
        obj(
            {
                "route": STRING,
                "filters": {"type": "object"},
                "fields": fields,
                "limit": POSITIVE,
                "page": POSITIVE,
            },
            ("route",),
        ),
        materials_route_search,
        group="materials",
        capabilities=("materials.route-search",),
        network=True,
        credentials=("materials-project",),
    )
    add(
        "materials_get",
        "Fetch one material record by Materials Project ID.",
        obj({"materialId": STRING, "route": STRING, "fields": fields}, ("materialId",)),
        materials_get,
        group="materials",
        capabilities=("materials.lookup",),
        network=True,
        credentials=("materials-project",),
    )
    add(
        "materials_advanced",
        "Retrieve consistently-defined phase data or invoke explicit optional local calculations.",
        obj(
            {
                "action": string_enum("phase_diagram", "xrd"),
                "chemsys": STRING,
                "limit": POSITIVE,
                "materialId": STRING,
            },
            ("action",),
        ),
        materials_advanced,
        group="materials",
        capabilities=("materials.phase-diagram", "materials.xrd"),
        network=True,
        credentials=("materials-project",),
    )
    add(
        "materials_export",
        "Write Materials records atomically beneath the configured output root.",
        obj(
            {
                "records": {"type": "array", "items": {"type": "object"}, "maxItems": 1000},
                "format": string_enum("json", "csv", "markdown", "cif"),
                "path": STRING,
            },
            ("records", "format", "path"),
        ),
        materials_export,
        group="materials",
        capabilities=("materials.export",),
        side="filesystem",
    )
    add(
        "chemical_sources",
        "Report CAS Common Chemistry contract/credential/license status without guessing endpoints.",
        obj({}),
        chemical_sources,
        group="chemistry",
        capabilities=("chemistry.sources",),
    )
    add(
        "chemical_search",
        "Search CAS only when a provider-issued contract is configured; otherwise fail closed.",
        obj(
            {"query": STRING, "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            ("query",),
        ),
        chemical_search,
        group="chemistry",
        capabilities=("chemistry.search",),
        network=True,
        credentials=("cas",),
    )
    add(
        "chemical_get",
        "Fetch a CAS substance only under an explicit provider-issued contract.",
        obj({"id": STRING}, ("id",)),
        chemical_get,
        group="chemistry",
        capabilities=("chemistry.lookup",),
        network=True,
        credentials=("cas",),
    )

    add(
        "omnischolar_image_models",
        "Discover image models and return only catalog/pin/curated capability declarations.",
        obj({"provider": STRING, "discover": BOOL}),
        image_models,
        group="media",
        capabilities=("media.models",),
        network=True,
    )
    image_base = {
        "provider": STRING,
        "model": STRING,
        "prompt": {"type": "string", "minLength": 1, "maxLength": 20000},
        "references": {"type": "array", "items": STRING, "maxItems": 8},
        "size": STRING,
        "aspectRatio": STRING,
        "resolution": STRING,
        "background": string_enum("transparent", "opaque", "auto"),
        "outputFormat": string_enum("png", "jpeg", "webp"),
        "quality": STRING,
        "n": {"type": "integer", "minimum": 1, "maximum": 10},
        "negativePrompt": STRING,
        "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
        "options": {"type": "object"},
    }
    add(
        "omnischolar_image_generate",
        "Discover/select a usable image model and generate a scientific image draft. Omit provider/model to auto-select the newest discovered model.",
        obj(image_base, ("prompt",)),
        image_generate,
        group="media",
        capabilities=("text-to-image", "image-to-image", "multi-reference"),
        network=True,
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "omnischolar_image_edit",
        "Discover/select a usable image model and edit scientific image references.",
        obj(image_base, ("prompt", "references")),
        image_edit,
        group="media",
        capabilities=("media.edit", "multi-reference"),
        network=True,
        side="paid",
        cost="paid",
        interaction=True,
    )
    add(
        "omnischolar_image_service",
        "Inspect provider status or a configured asynchronous image job.",
        obj(
            {"provider": STRING, "action": string_enum("status", "job"), "jobId": STRING},
            ("provider", "action"),
        ),
        image_service,
        group="media",
        capabilities=("media.service",),
        network=True,
    )
    return definitions
