---
name: omnischolar
description: Orchestrate multi-step scholarly work with OmniScholar across literature discovery, read-only Zotero, PDF parsing, citations, materials and chemical data, scientific images, and local publication. Use when a request spans several research workflows or the correct specialist workflow is unclear.
license: MIT
compatibility: Requires OmniScholar and an agent connected to its MCP tools. Network features require the corresponding configured services.
---

# OmniScholar

Choose the smallest workflow that answers the request. Follow the user's language; keep tool names and configuration identifiers in their exact English form.

## Route the request

- Literature, patents, authors, citation graphs, recommendations, journals, snippets, or datasets: follow `scholar-search`.
- Local collections, metadata, notes, annotations, attachments, or PDF selection: follow `zotero-research`.
- Structured PDF text, equations, tables, figures, or close reading: follow `paper-reading`.
- Citation evidence, candidates, formatting, or insertion: follow `academic-citation`.
- Generated or edited illustrations: follow `scientific-figure`.
- Materials Project records and exports: follow `materials-project`.
- CAS substance records and contract status: follow `chemical-data`.

For an unfamiliar environment, call `omnischolar_status`, `omnischolar_capabilities`, and the relevant source-status tool before selecting a provider. If no provider supports the requested capability, report the missing configuration or capability and offer an available non-equivalent workflow only with a clear label.

## Safe multi-stage sequence

1. Search only when discovery is needed; preserve provider provenance and identifiers.
2. Match a local Zotero record by DOI, then normalized title/year/author. Never guess between ambiguous candidates.
3. Read the aggregate Zotero item and identify the intended attachment.
4. Call `omnischolar_sync` with `action=plan` before parsing or changing output.
5. Call `omnischolar_parse` only when structured PDF extraction is necessary and both configuration and the current tool call authorize external upload.
6. Read generated content progressively and verify claims against retrieved evidence.
7. Format citations only after identity and relevance checks.
8. Route image work by declared capability, then inspect the result for scientific errors.

## Boundaries

- Zotero is GET-only and local-only. Never expose port 23119 or request a write operation.
- Ai4Scholar is an explicitly selected paid source, not a silent literature fallback.
- MinerU uploads the selected PDF. A sync recovery action must not trigger a remote upload; repair or reparse may upload only when cache is insufficient and the user explicitly authorizes it.
- Preserve local modifications. On `conflict`, use the `.conflicts/` candidate and ask the user how to reconcile it.
- Never expose credentials, Authorization headers, signed URLs, or local private paths in answers.
- Do not blindly retry authentication failures, rate limits, ambiguous paid submissions, unsafe archives, or terminal jobs.
- AI-generated scientific images are illustrative drafts, never experimental results or measured data.

## Output

Write only beneath the configured output root. The default managed layout is:

```text
<output-root>/Literatures/<paper>/
├── <paper>.md
├── metadata.json
└── assets/
```

Preserve provenance in `metadata.json`, respect the user's citation style and language, and keep missing or uncertain values explicit.
