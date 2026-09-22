# Changelog

## [0.6.0] - 2026-09-22

- Add the `obsidian-literature-base` Skill for building seven Obsidian Base views over MinerU publications and Zotero reading records.
- Generate per-paper catalogue notes with prefixed or AI-assisted topics, cover images, and foldable galleries containing every parsed image.
- Add an optional topic Wiki with a generated literature hub, shared-topic pages, bidirectional Wikilinks, preserved manual synthesis sections, and stale-page reporting.
- Keep MinerU and Zotero managed artifacts read-only, refuse unsafe overwrites, and cover Base, gallery, topic, Wiki, and refresh behavior with automated tests.

## [0.5.1] - 2026-09-22

- Rewrite `literature-reading` as one concise Agent workflow that defaults to complete paper interpretation and keeps focused evidence retrieval within the same Skill.
- Require figure interpretation to combine visual inspection, captions, and the authors' surrounding discussion, with linked MinerU asset previews in optional Markdown output.
- Keep `paper-reading` responsible only for PDF selection and MinerU publication, and remove the redundant `literature-retrieval` Skill.
- Align parsing guidance with the runtime order: MinerU cache/upload occurs before publication conflict, exclusion, or recovery checks.

## [0.5.0] - 2026-09-22

- Add shared Obsidian-ready bibliographic frontmatter to MinerU Markdown and Zotero reading records, including Zotero deep links.
- Normalize creator names and Zotero tags into Obsidian-compatible list properties while retaining complete source metadata in `metadata.json`.
- Prefix every parsed image filename and rewritten Markdown image link with the source Zotero key.
- Document the published frontmatter and image naming contract and cover it with unit and live Zotero-to-MinerU publication checks.

## [0.4.2] - 2026-09-21

- Pin the release-gate Ruff version and align test helpers with that rule set so validated releases cannot diverge between local and CI environments.

## [0.4.1] - 2026-09-21

- Require explicit user confirmation of `attachmentKey` before parsing or synchronizing Zotero items with multiple PDFs.
- Fix arXiv requests by sending the required Atom and contact headers, and keep Crossref's first search page relevant by omitting the wildcard cursor.
- Mark `omnischolar_status` as network-capable while preserving live image-model discovery.
- Honor configured sync conflict behavior and conflict directories, reject unsafe conflict paths, and wire cache/recovery controls to their runtime behavior.
- Remove obsolete managed assets during republish, preserve unmanaged user files, and prevent distinct Zotero publications with identical stems from sharing a directory.
- Align the Skills, bilingual documentation, tool counts, latest-package commands, runtime user agents, and release validation workflow.

## [0.4.0] - 2026-09-21

- Remove the dedicated literature-reading MCP tools and keep paper interpretation in Skills.
- Keep Zotero access, MinerU parsing, and conservative synchronization as MCP capabilities.
- Rewrite paper-reading, literature-reading, and literature-retrieval Skills around local MinerU Markdown and assets.
- Save interpretation Markdown beside the MinerU source with task-defined filenames and structure.
- Remove fixed structured-analysis output directories, filename templates, and analysis frontmatter generation.
- Keep Zotero reading records under each paper's `source/` directory.

## [0.3.5] - 2026-09-21

- Fix targeted-reading figure/table normalization to be idempotent.
- Prevent duplicate generation of the four figure-analysis fields.
- Remove image width aliases and keep Markdown figure tables at exactly two columns.
- Preserve user-provided figure interpretations and author statements.
- Add regression coverage for Chinese figure titles and complex Markdown table rows.

## [0.3.4] - 2026-09-21

- Fix structured analysis frontmatter so generated documents contain one canonical frontmatter block.
- Render each targeted-reading figure/panel as a two-column Markdown table row using the original MinerU asset embed.
- Keep figure analysis as four ordered fields: title, source location, author statement, and interpretation.
- Remove generated thumbnail asset support and retain only original MinerU images.
- Add regression coverage for repeated frontmatter, table image parsing, original asset links, and ordered figure analysis fields.

## [0.3.3] - 2026-09-20

- Add configurable source PDF and styled Zotero reading-record publication for notes and PDF annotations.
- Add source-fingerprinted `omnischolar_analysis` outputs for single-paper `full-read`/`targeted-reading` and multi-paper `compare`/`review` workflows.
- Improve Obsidian analysis links, canonical Sources sections, figure embeds, Markdown table layouts, and block-math formula output.
- Fix Zotero local API annotation discovery and filter annotations by their actual parent attachment.
- Update SCI literature Skills and release documentation for language-aware structured reading workflows.

## [0.3.2] - 2026-09-20

- Fix Zotero PDF annotation discovery for the local API by querying annotation items by `parentItem` and filtering returned annotations by their actual parent attachment.
- Add regression coverage for annotation colors, pages, comments, tags, and cross-attachment filtering.

## [0.3.1] - 2026-09-20

- Add configurable Zotero source output with copied PDFs and a styled `zotero-reading-record.md` that separates notes from PDF annotations.
- Add `omnischolar_analysis` for source-fingerprinted `full-read`, `targeted-reading`, `compare`, and `review` Markdown outputs under configurable `Analysis/Single` and `Analysis/Multi` directories.
- Update literature Skills with SCI-focused single-paper templates, compact multi-paper comparison/review workflows, language-aware output, and source-conflict rules.

## [0.3.0] - 2026-09-20

- Add bounded local focused retrieval with BM25 + TF-IDF ranking, paragraph locators, section filters, and explicit empty-result behavior.
- Add persistent bounded reading contexts for multi-turn single-paper and multi-paper workflows.
- Extend literature reading with stable paragraph anchors, figure/table analysis context, multi-paper comparison, review evidence, and cache-aware workflows.
- Add the `literature-retrieval` Skill and align all Skill frontmatter with the current validator.
- Keep MCP results protocol-compatible without duplicating full payloads in `structuredContent`; add regression coverage for standard MCP clients.
- Validate real Zotero workflows across three papers, including cache hits, forced reparse/overwrite, full-text pagination, figures, formulas, comparison, review, and fail-closed errors.

## [0.2.0] - 2026-09-18

- Keep full parsed Markdown in the local publication while returning bounded parse metadata to agents.
- Add `omnischolar_read` for cursor-based full-text reading, figures/tables, formulas, paragraph lookup, paper comparison, and literature-review evidence packets.
- Stop duplicating every MCP result in both text and structured content; Pi adapters now keep one canonical result representation.
- Add the `literature-reading` Skill and make metadata-only Zotero item reads the default.

## [0.1.24] - 2026-09-17

- Add named custom provider profiles with independent API keys, endpoints, model capabilities, and image parameter contracts.
- Support custom model-level controls for size, resolution, background, output format, quality, count, and image editing workflows.

## [0.1.23] - 2026-09-17

- Extend OpenAI-compatible image request timeouts to 180 seconds by default, with a bounded custom-provider override.

## [0.1.22] - 2026-09-17

- Move current GPT Image and Gemini image model presets to the custom provider example; official providers continue to use their own model discovery or curated catalogs.

## [0.1.21] - 2026-09-17

- Auto-probe custom OpenAI-compatible providers at `baseUrl/models` when no catalog endpoint is configured, with safe fallback to explicit model contracts.
- Preset the current official GPT Image and Gemini image model IDs in the example configuration.
- Document custom catalog discovery and capability metadata requirements.

## [0.1.20] - 2026-09-17

- Default Fal image generation to official `sync_mode=true` with an explicit opt-out for hosted-URL queue results.
- Add regression coverage and update scientific-figure routing guidance for CDN-independent Fal artifacts.

## [0.1.19] - 2026-09-17

- Distinguished Qwen AI Platform public DashScope endpoints from Bailian workspace endpoints.
- Inferred the Vertex project from `credentialsFile.project_id`, included Vertex auth dependencies by default, and added a long image-generation timeout.
- Exposed verified provider parameter contracts through `omnischolar_image_models` and documented provider-specific image controls.
- Mapped Qwen `resolution`/`aspectRatio` to the native `size` parameter and added regression coverage.

## [0.1.18] - 2026-09-17

- Added Semantic Scholar author search/detail/papers operations, recommendation enrichment, bounded retries, and `Retry-After` handling.
- Added image-provider model discovery, explicit model selection, normalized image options, and verified fallback catalogs for providers without discovery APIs.
- Added native Qwen/DashScope image routing, workspace/region configuration, Fal queue URL normalization, Vertex service-account JSON authentication, global Gemini image generation, and Vertex image extraction.
- Updated image-provider documentation, example configuration, scientific-figure routing guidance, and regression tests.

## [0.1.12] - 2026-09-16

- Switched all documented and installer-generated MCP launchers to the latest PyPI package form.
- Added complete latest-version update and uninstall commands for Python, MCP, Skills, Codex, Claude Code, and Pi.
- Kept Codex TOML and stdio-host MCP configuration shapes separate and valid.

## [0.1.11] - 2026-09-16

- Switched MCP launchers from fixed PyPI versions to `@latest`.
- Added explicit refresh commands for forcing uv cache updates.
- Added complete install, update, and uninstall guidance for MCP, Skills, Codex, Claude Code, and Pi.
- Updated the host installer to write the latest uvx MCP command with host-correct config shapes.

## [0.1.10] - 2026-09-16

- Added `_` as a supported shared filename separator alongside `-` and `+`.
- Added a separate folder-name template for per-publication directories.
- Applied the shared separator to paper, folder, and parsed-image asset naming.

## [0.1.9] - 2026-09-16

- Added title-only and author/title filename template combinations.
- Added configurable attachment image filenames with original-stem and extension variables.
- Added collision and unsafe-name checks for configured attachment filenames.

## [0.1.8] - 2026-09-16

- Added configurable Obsidian output subfolders.
- Added configurable filename templates and `-`/`+` separators for new publications.
- Preserved existing manifest paths when output naming settings change.

## [0.1.7] - 2026-09-16

- Included the complete configuration-template loader in the published Python package.
- Ensured first-run initialization uses the full editable template on installed releases.

## [0.1.6] - 2026-09-16

- Generate the complete editable configuration template on first initialization.
- Reserve direct `apiKey` and optional `apiKeyEnv` fields for every credentialed service.
- Include Vertex project, location, and access-token fields plus all image-provider sections.

## [0.1.5] - 2026-09-16

- Documented and tested direct `apiKey` entries in the user configuration.
- Kept `apiKeyEnv` as an optional environment-variable alternative.

## [0.1.4] - 2026-09-16

- Fixed the user configuration directory to use one cross-platform app directory level.
- Stopped reading legacy nested configuration paths; existing legacy files are left untouched.
- Documented environment-variable-based API key setup and platform-specific user paths.

## [0.1.3] - 2026-09-16

- Fixed release-version drift between Python, MCP launchers, Pi, and plugin manifests.
- Added automatic creation of one user-level configuration file when no config is discoverable.
- Made the Pi Extension launch the matching PyPI MCP through `uvx` instead of requiring a separate global CLI.

## [0.1.2] - 2026-09-16

### Added

- Added the npm-published Pi MCP bridge Extension and Pi Extension + Skills installation flow.
- Added token-free npm trusted publishing through GitHub Actions OIDC.
- Added verified Hermes and WorkBuddy/CodeBuddy MCP templates.
- Included all README-linked documentation in the Pi npm package from version 0.1.1.
- Added a Git-backed Codex marketplace and a one-command plugin MCP path through pinned `uvx`.
- Added a Claude Code marketplace that installs the same eight Skills and pinned local MCP server.

### Fixed

- Removed duplicate paper titles when MinerU already returns a matching top-level heading.
- Renamed parsed figures to deterministic `image-N` files in first-reference order and rewrote Markdown links before publication.
- Flattened nested MinerU asset paths before the sync publisher's filename safety check.
- Bounded long paper stems with deterministic hash suffixes to avoid Windows path-length failures and truncation collisions.
- Made sync repair, restore, and apply operations reuse valid MinerU cache entries instead of forcing a paid re-upload; only explicit reparse bypasses the cache.
- Reported the stored parser cache key in sync plans for existing publications.
- Added workspace-scoped DashScope and Qwen Cloud endpoints to the example configuration and image-provider documentation.

### Changed

- Unified Python, Pi npm, MCP registry, and agent-plugin package versions at `0.1.2`.

## [0.1.0] - 2026-09-10

### Added

- Local Python stdio MCP server with 38 research tools and eight shared Skills.
- Literature search, read-only Zotero, MinerU parsing and Markdown sync.
- Ai4Scholar citation and research tools, Materials Project queries and exports, CAS interface checks, and scientific image generation.
- Host installer with dry-run, backup, rollback, update, uninstall, checksum checks, and MCP handshake validation.
- English and Simplified Chinese user documentation, live validation records, and plugin listing material.

### Security

- Separate approval for paid calls and external uploads.
- Limits for responses, files, paths, pagination, polling, and archive extraction.
- Secret removal from status, errors, logs, and tool results.

### Fixed after live testing

- PubMed identifier handling and PMC OAI-PMH full-text retrieval.
- Zotero attachment, note, annotation, and indexed-text handling.
- Windows newline recovery and render-change detection in sync.
- Materials Project CIF export.
- Ai4Scholar figure timeout and artifact saving.
- fal queue/data-URI results and DashScope workspace endpoint checks.
