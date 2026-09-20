# Literature, Zotero, and PDFs

[简体中文](RESEARCH.md)

## Literature search

| Tool | Use |
|---|---|
| `research_sources` | Show enabled sources and available operations |
| `literature_search` | Search papers by year, type, or open-access status |
| `literature_get` | Retrieve details by DOI, PMID/PMCID, arXiv ID, or source ID |
| `literature_author` | Search Semantic Scholar authors, author details, or an author's papers |
| `literature_graph` | Find references, citations, or recommendations |
| `journal_metrics` | Retrieve supported journal metrics |
| `literature_fulltext` | Find lawful full-text locations or save an accessible file under the output directory |

The sources serve different purposes:

- Semantic Scholar and OpenAlex cover broad literature and citation relationships.
- PubMed/PMC focuses on biomedical records; PMC also supplies licensed open full text.
- arXiv preserves preprint identifiers and versions.
- Crossref is useful for checking DOI registration metadata.
- Unpaywall finds open-access copies without bypassing subscriptions or access controls.
- easyScholar supplies journal metrics supported by its current interface.
- Ai4Scholar also covers Google Scholar, Google Patents, authors, datasets, and journals. Some calls use account credit.

Start with a small `limit`. Deduplicate by DOI when possible; otherwise compare normalized title, year, and first author. Title similarity can shortlist a paper but cannot establish that it supports a claim.

On HTTP 429, OmniScholar reads `Retry-After` when provided and applies bounded backoff plus optional `rateLimitPerSecond` throttling for Semantic Scholar. Do not submit the same request in a tight loop.

## Zotero

OmniScholar connects only to the local Zotero API:

```text
http://127.0.0.1:23119/api
```

Enable “Allow other applications on this computer to communicate with Zotero” and keep Zotero Desktop running.

| Tool | Content |
|---|---|
| `zotero_collections` | Collections and collection items |
| `zotero_search` | Bibliographic items, notes, annotations, and attachments |
| `zotero_item` | A raw item or a combined paper view |

The combined view can include metadata, notes, annotations, attachment details, indexed text, and a local PDF path. OmniScholar never creates, updates, moves, tags, or deletes Zotero data.

`zotero_item` defaults to metadata-only output; request `mode=aggregate` when notes, annotations, attachments, indexed text, or PDF selection are needed. After parsing, use `omnischolar_read` for cursor-based full-text reading or bounded figure, formula, paragraph, comparison, and review evidence. The complete Markdown remains in the output directory and is not returned to the agent by default.

### Focused retrieval and reading contexts

Use `omnischolar_focus` over parsed local publications for bounded BM25 + TF-IDF vector evidence retrieval. It returns matching paragraphs, headings, character ranges, and `paper.md#Lx-Ly` line locators rather than a complete Markdown document. Restrict it with `keys`, `section`, `topK`, and `maxPerDocument`. The local backend explicitly reports `strategy=hybrid-bm25-tfidf`, `vectorBackend=tfidf-local`, and `semantic=false`, so term-vector similarity is not presented as dense semantic embedding retrieval.

Use `omnischolar_locate` for exact paragraph location in one paper, with phrase or all-term matching and Zotero key, title, section, and stable anchors. Use `omnischolar_read` with `mode=figures` for image paths, table Markdown, captions, and bounded figure/table context. The agent must still distinguish visual observation, caption text, author claims, and interpretation.

For multi-turn reading, call `omnischolar_context` with `open`, then pass its `contextId` to `omnischolar_focus`, `omnischolar_locate`, or `omnischolar_read`. The cache stores selected evidence only; `get` is paginated and bounded, so it does not automatically re-inject a complete paper into the agent. `compare` and `review` can add per-paper evidence to the same context.

Notes and annotations are personal reading context, not evidence from the publication. Check the paper itself before citing a claim.

## MinerU parsing

`omnischolar_parse` validates the PDF, computes SHA-256, and asks MinerU to return text, formulas, tables, and figures. Results are cached; the same file and parser settings can return a cache hit. The tool returns parse metadata and publication paths; use `omnischolar_read` to retrieve bounded content.

After MinerU is enabled and its API key is configured, parsing is directly available; OmniScholar does not upload without credentials.

OmniScholar does not upload a Zotero attachment automatically. Confirm the exact item and file, then approve that upload separately. `force` creates a new parse and upload, so it needs fresh approval.

Before extraction, MinerU archives are checked for unsafe paths, symlinks, excessive entries, and excessive expansion. Failed archives are not published.

## Citations

Citation work has two steps: establish that a source supports the claim, then format its bibliographic record.

1. Find sources with `literature_search` and `literature_get`.
2. Check DOI, PMID, arXiv ID, title, authors, and year.
3. Read the passage relevant to the claim.
4. If paid use is approved, `ai4scholar_citation_candidates` can suggest more candidates.
5. Use `ai4scholar_cite` only for records you have accepted.

A correctly formatted reference does not prove the claim. Ai4Scholar's Google Scholar citation formatter may lack a result ID required by the upstream interface; if it reports `blocked`, do not invent an ID.

## Markdown and Obsidian output

The output location and new-file naming can be customized in the global configuration:

```json
{
  "output": {
    "rootDirectory": "F:/Personal Knowledge Base",
    "literatureDirectory": "Literature/Parsed",
    "folderNameTemplate": "{author}{separator}{year}",
    "filenameTemplate": "{year}{separator}{author}{separator}{title}",
    "filenameSeparator": "+",
    "assetFilenameTemplate": "figure{separator}{index}{separator}{original}{extension}"
  }
}
```

Supported paper filename variables are `{author}`, `{year}`, `{title}`, and `{separator}`; `folderNameTemplate` independently controls each paper directory name. `filenameSeparator` accepts `-`, `+`, and `_`, and is shared by paper, folder, and attachment templates. Attachment images support `assetFilenameTemplate` with `{index}`, `{original}`, `{extension}`, and `{separator}`. New papers are written under `rootDirectory/literatureDirectory`, with images under each paper directory's `assets/` folder. Existing manifest records keep their original paths so changing the configuration does not break incremental synchronization. Here, attachment images means parsed image assets, not the original Zotero PDF attachment.

When `output.source.copyPdf` is enabled, the selected Zotero PDF is copied into each paper's `source/` directory and `zotero-reading-record.md` is generated. The record keeps Zotero notes and PDF annotations in separate sections, including annotation type, color, page, tags, comments, and relative PDF links. These are personal reading records, not independent paper evidence.

Use `omnischolar_analysis` to write structured analyses: `full-read` and `targeted-reading` for one paper, and `compare` and `review` for multiple papers. By default, single-paper analyses are stored under `Analysis/Single/<paper>/` and multi-paper analyses under `Analysis/Multi/`; paths and filename templates are configurable under `output.source` and `output.analysis`.

`omnischolar_sync` shows a plan before writing under `output.rootDirectory`. The directory can be a regular folder or part of an Obsidian vault.

Sync distinguishes new content, no change, metadata changes, parse changes, render changes, missing files, conflicts, exclusions, and interrupted recovery. Metadata repair, rerendering, and transaction recovery do not upload a PDF.

If managed Markdown was edited by hand, the default policy keeps it and writes the incoming version under `.conflicts/`. Review both files before merging.

Before using a real vault, point `output.rootDirectory` at a temporary directory and inspect the folder names, Markdown, and image links.
