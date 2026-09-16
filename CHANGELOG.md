# Changelog

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
