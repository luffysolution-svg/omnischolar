# Changelog

## [Unreleased]

- Added the npm-published Pi MCP bridge Extension and Pi Extension + Skills installation flow.
- Added verified Hermes and WorkBuddy/CodeBuddy MCP templates.

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
