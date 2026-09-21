---
name: literature-retrieval
description: Locate supporting paragraphs, captions, figures, and tables inside a locally parsed MinerU paper.
license: MIT
---

# Local paragraph and figure/table retrieval

Use this Skill when the user asks where a parsed paper discusses a mechanism, method, result, limitation, number, formula, figure, or table. Work from the local MinerU Markdown and sibling assets, not from memory or an unverified summary.

## Workflow

1. Start from the exact `publication.markdownPath` or paper directory. Confirm the paper identity from its frontmatter, Markdown title, and `metadata.json`.
2. Search the Markdown using the host's native text-search or file-reading capability. Search exact phrases first; then search distinctive terms, section headings, figure/table labels, sample names, units, and numbers.
3. Open the matching paragraph together with its heading, preceding/following context, caption, and any linked asset. For a figure or table, inspect the local asset when the host supports images; otherwise state that visual inspection was unavailable.
4. Record a reproducible locator: relative Markdown filename, section heading, line range when available, paragraph excerpt, and figure/table identifier. Do not invent page or line numbers that are not available.
5. Separate extracted text, the authors' explicit statement, direct visual or tabular observation, interpretation, and uncertainty. Preserve contradictions and missing evidence.
6. If the user asks for an interpretation file, write it beside the source Markdown. The user chooses the filename and the content structure; a short list, prose note, table, or mixed format is valid. Never alter the source Markdown.

## Boundaries

- This workflow covers the selected parsed paper and does not claim exhaustive retrieval across a library.
- Zotero notes and PDF annotations are personal reading records; label them separately from original-paper evidence.
