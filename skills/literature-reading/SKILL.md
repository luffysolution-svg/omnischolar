---
name: literature-reading
description: Interpret a MinerU-parsed SCI paper from its local Markdown and assets, locate supporting paragraphs and figures or tables, and write a flexible interpretation sidecar beside the source.
license: MIT
---

# SCI interpretation from MinerU output

Use this Skill after a paper has been published locally by MinerU. The source of truth is the parsed Markdown, its metadata, and its sibling image and table assets. The reading checklist guides the reasoning; it does not prescribe a document template.

## Source and output

- Read the parsed Markdown frontmatter, `metadata.json`, and relevant sibling assets with the host's local file, search, and image-viewing capabilities.
- Preserve the MinerU Markdown and extracted assets exactly as published.
- Write the interpretation as a new Markdown file in the same directory as the MinerU Markdown. Use the filename requested by the user or choose a concise descriptive filename when none is provided.
- Keep links relative to the paper directory when possible. Do not include absolute local paths, credentials, signed URLs, or private Zotero data in the visible document.
- Adapt the organization, headings, tables, and level of detail to the user's question. Frontmatter is optional and only belongs in the output when the user requests it.

## Interpretation workflow

1. Confirm the paper identity, source Markdown path, DOI, parser metadata, and asset directory.
2. Read the Markdown structure first. Then search and open the sections, paragraphs, captions, formulas, tables, and figures relevant to the user's question. For a broad interpretation, cover the paper progressively and state the scope that was read.
3. Use the SCI checklist as prompts: research question and gap, objective, materials or data, controls, methods and conditions, quantitative results, contribution, limitations, reproducibility, applicability, and conclusion. Include only the parts relevant to the request.
4. Attach a source locator to important claims: section heading, line range, paragraph excerpt, figure/table identifier, caption, or relative link. Report missing values as unreported or unavailable.
5. For a paragraph, figure, or table, distinguish extracted text, the authors' explicit statement, direct visual or tabular observation, interpretation, and uncertainty caused by OCR, layout, missing context, or asset quality.
6. Write the requested interpretation beside the source file. A list, prose note, compact table, or mixed format is appropriate when it improves clarity.
7. Re-open the saved file and verify source links, image links, paragraph locators, and formulas. Report the exact output path.

## Evidence discipline

- A caption does not establish an observation that the asset or nearby text does not support.
- Do not present an inference as an author claim. Label interpretation and confidence clearly.
- Preserve units, conditions, sample names, statistical values, formulas, chemical names, gene/protein names, and instrument/model names unless translation is requested.
- Treat Zotero notes and PDF annotations as personal reading records, not independent paper evidence.
- If the source Markdown or assets cannot be opened, report the missing capability or path instead of reconstructing the paper from memory.
