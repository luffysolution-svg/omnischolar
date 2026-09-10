---
name: zotero-research
description: Search and inspect the user's local Zotero library with OmniScholar. Use for collections, bibliographic metadata, notes, annotations, attachments, indexed text, local-paper matching, or selecting a PDF without modifying Zotero.
license: MIT
compatibility: Requires OmniScholar and a running Zotero desktop instance with local application access enabled.
---

# Read-only Zotero research

Follow the user's language. Zotero is strictly GET-only: never create, edit, tag, move, or delete library data.

## Workflow

1. Use `zotero_collections` to list collections, read one collection, or list its top-level items.
2. Use `zotero_search` with DOI first, then distinctive title terms. Omit `query` or use `*` to browse; bound `limit` and pagination.
3. Match normalized DOI first. Otherwise compare normalized title, year, and first author. Report ambiguity instead of guessing.
4. Use `zotero_item` with `mode=aggregate` for the selected bibliographic parent. Review metadata, notes, annotations, attachments, indexed-text status, and the selected PDF.
5. If several PDFs are plausible, request or explain the `attachmentKey`. Never assume similarly named attachments are equivalent.
6. Treat unavailable or truncated indexed text as incomplete evidence, not an empty paper.
7. Call `omnischolar_sync` with `action=plan` before parsing or changing managed output. `missing`, `excluded`, `conflict`, and `recovery_required` each require their explicit workflow.
8. Call `omnischolar_parse` only for necessary structured content and only after explicit external-upload authorization.

If Zotero is unavailable, ask the user to start Zotero and enable local application access. Keep `http://127.0.0.1:23119/api` on the local machine. If a local item is absent, use `scholar-search` only when online discovery matches the request.
