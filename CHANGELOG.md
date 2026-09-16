# Changelog

## [Unreleased]

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
