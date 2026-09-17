---
name: literature-reading
description: Interpret parsed scholarly papers from OmniScholar with bounded full-text, figure, formula, paragraph, comparison, and review workflows. Use when the user wants to understand, compare, or synthesize papers rather than only retrieve metadata.
license: MIT
---

# Literature reading and interpretation

Follow the user's language. Keep the original paper and generated Markdown on disk; expose only the evidence needed for the current reading mode.

## Select a mode

- `full`: read the entire paper progressively with `omnischolar_read`, following `nextCursor` until `hasMore` is false. Summarize each section before moving on.
- `figures`: retrieve figure/table asset paths, captions, and section context. Inspect the referenced local assets when the host supports image input; distinguish visual observations from captions and author claims.
- `formulas`: retrieve bounded displayed formulas with their section headings. Explain symbols and assumptions only when supported by nearby text.
- `paragraphs`: use `query` and optionally `section` to retrieve matching paragraphs instead of loading the document.
- `compare`: pass multiple Zotero keys and retrieve compact, comparable metadata, abstracts, headings, and requested evidence.
- `review`: pass multiple Zotero keys and build a literature-review evidence matrix. Preserve differences in methods, population/materials, outcomes, limitations, and confidence; do not merge claims merely because titles are similar.

## Workflow

1. Match a Zotero record by DOI, then normalized title/year/author; report ambiguity.
2. Use `zotero_item` with `mode=item` for metadata and `mode=aggregate` only when notes, annotations, or attachment selection are needed.
3. Confirm the selected PDF and run `omnischolar_sync` with `action=plan` before parsing.
4. Parse only when structured content is necessary and external upload is authorized. `omnischolar_parse` returns a local publication path and parse metadata, not the full Markdown body.
5. Use `omnischolar_read` for bounded evidence retrieval. Record Zotero key, Markdown path, heading, figure/table/formula identifier, and cursor where relevant.
6. State OCR, layout, formula, table, and missing-text limitations. Never treat Zotero notes or annotations as independent evidence without labeling them.

Full-text mode is intentionally paginated. Never bypass pagination by requesting an oversized result. If a retrieved excerpt is truncated, continue with its cursor rather than guessing the missing text.

## Output

Separate original evidence, interpretation, and uncertainty. For comparisons and reviews, use a table or evidence matrix with per-paper provenance. Do not expose credentials, signed URLs, or unrelated local files.
