---
name: literature-retrieval
description: Find focused evidence in parsed local papers, locate paragraphs, compare selected papers, and maintain a bounded reading context without loading whole documents.
license: MIT
---

# Focused literature retrieval

Use this workflow when the task is to find where a paper discusses a concept, method, result, limitation, or comparison dimension. Retrieval is evidence selection; it is not itself a scientific conclusion.

## Workflow

1. Match the Zotero parent by DOI first, then normalized title/year/author. If the match or PDF attachment is ambiguous, stop and report the choices.
2. Use `zotero_item` with `mode=item` for identity. Use `mode=aggregate` only when attachment selection or annotations are needed.
3. Confirm local parsed output with `omnischolar_sync` and `action=plan`. Parse only when structured content is needed and an external upload is authorized.
4. Call `omnischolar_focus` with a short research concept, optional `keys`, `section`, `topK`, and `includeContext`. Treat returned `excerpt`, heading, paragraph ID, and line locator as the evidence packet.
5. Call `omnischolar_locate` when the user needs exact paragraphs in one paper. Prefer `matchMode=phrase` for a quoted phrase and `allTerms` for a concept.
6. Use `omnischolar_context` with `action=open` before a long multi-turn task. Pass its `contextId` to focus, locate, and `omnischolar_read`; retrieve the cache later with a bounded `get` call.
7. For several papers, use `omnischolar_read` with `mode=compare` or `mode=review`, pass `contextId` when continuity is needed, and preserve per-paper provenance.

## Retrieval policy

- The current local retriever uses bounded BM25-style lexical retrieval plus a transparent TF-IDF vector score. It does not claim dense semantic embedding support; `semantic` remains `false` until a real embedding backend is configured.
- Exact identifiers, formulas, material names, gene/protein names, numbers, and quoted phrases should be verified with `omnischolar_locate` or a section read even when focused search returns a hit.
- `markdownPath` is a local provenance field. Do not expose unrelated local files, credentials, or Zotero private data.
- A cache stores selected excerpts only. Never add an entire paper or an unbounded tool response to a context.
- Distinguish extracted text, caption/table content, visual observations, author claims, interpretation, and uncertainty in the final answer.

## Handoff to reading modes

- `full`: follow `nextCursor` with `omnischolar_read`; never request an oversized page.
- `figures`: use `omnischolar_read` with `mode=figures`; inspect the referenced asset when the host supports images, then separate caption, visual observation, and claim.
- `formulas`: use `mode=formulas` and explain symbols only with nearby evidence.
- `compare`/`review`: use bounded per-paper evidence and an evidence matrix; do not merge similar claims without checking methods and populations/materials.
