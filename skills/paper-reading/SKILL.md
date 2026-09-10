---
name: paper-reading
description: Parse and analyze a selected local PDF with OmniScholar and MinerU. Use when the task needs structured full text, equations, tables, figures, captions, or close reading beyond metadata and Zotero notes.
license: MIT
compatibility: Requires OmniScholar; Zotero-based reading needs local Zotero, and external parsing needs configured MinerU access plus explicit upload authorization.
---

# PDF parsing and close reading

Follow the user's language. MinerU receives PDF bytes over the network and may consume quota; do not parse metadata-only questions.

## Workflow

1. Resolve the bibliographic parent and intended PDF with `zotero_item` in aggregate mode. Require an explicit `attachmentKey` when selection is ambiguous.
2. Use `omnischolar_sync` with `action=plan`. Reuse `up_to_date` output. `metadata_changed` and `render_changed` do not by themselves require a new upload.
3. Call `omnischolar_parse` only when the plan requires parsing and both gates are satisfied:
   - MinerU upload is enabled in configuration;
   - the current request explicitly sets upload authorization.
4. Do not use `force` to bypass a conflict. Do not automatically resubmit an ambiguous or timed-out task.
5. Read generated Markdown progressively: headings first, then the relevant sections, figures, tables, and equations.
6. Use `metadata.json` for attachment identity, parse key, parser metadata, and provenance. An unknown parser version remains unknown.
7. Distinguish extracted text, visual observation, captions, and author claims. Cite exact sections or numbered objects where possible.
8. State OCR, equation, table, or layout limitations that affect confidence.

Read [sync.md](references/sync.md) for managed-output states. If MinerU is unavailable, use bounded Zotero indexed text and notes when sufficient; otherwise report that structured full-text parsing is blocked. Never upload a different attachment as a fallback without explicit selection and authorization.
