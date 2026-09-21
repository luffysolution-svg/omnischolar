---
name: paper-reading
description: Select and parse a local Zotero PDF with MinerU, then hand the published Markdown and assets to a flexible SCI interpretation workflow.
license: MIT
---

# PDF parsing and close reading

Use this Skill when the user needs structured text, equations, tables, figures, captions, or close reading from a selected local PDF. Parsing is the data-preparation step; `literature-reading` and `literature-retrieval` handle interpretation after publication.

## Workflow

1. Resolve the bibliographic parent and intended PDF with `zotero_item` in aggregate mode. When more than one PDF is available, show the attachment keys and filenames, ask the user which PDF to use, and do not call parse or sync actions until the user confirms an explicit `attachmentKey`.
2. Call `omnischolar_sync` with `action=plan` and reuse an up-to-date publication. Do not upload a different attachment as a fallback.
3. Call `omnischolar_parse` only when parsing is necessary, MinerU is enabled, and the user has authorized the external PDF upload. Do not use `force` to bypass a conflict or automatically resubmit an ambiguous or timed-out task.
4. Read the returned `publication.markdownPath`, `metadata.json`, and sibling assets with the host's local file and image capabilities. The complete parsed Markdown stays on disk.
5. For SCI interpretation, follow `literature-reading`. For exact paragraph, figure, or table location, follow `literature-retrieval`.
6. Write the interpretation as a new Markdown file beside the MinerU Markdown. Use a user-chosen filename and an evidence-driven structure; do not write into the MinerU source file.
7. State OCR, equation, table, image, or layout limitations that affect confidence. Report the saved sidecar path.

If MinerU is unavailable, use Zotero indexed text only when it is sufficient for the user's question and label the limitation. Do not claim full-paper interpretation from metadata, notes, or annotations alone.
