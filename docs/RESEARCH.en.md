# Literature, Zotero, and PDFs

[简体中文](RESEARCH.md)

## Literature search

| Tool | Use |
|---|---|
| `research_sources` | Show enabled sources and available operations |
| `literature_search` | Search papers by year, type, or open-access status |
| `literature_get` | Retrieve details by DOI, PMID/PMCID, arXiv ID, or source ID |
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

On HTTP 429, OmniScholar returns a rate-limit result. Wait for the provider's backoff period or choose another source that supports the same operation. Do not submit the same request in a tight loop.

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

Notes and annotations are personal reading context, not evidence from the publication. Check the paper itself before citing a claim.

## MinerU parsing

`omnischolar_parse` validates the PDF, computes SHA-256, and asks MinerU to return text, formulas, tables, and figures. Results are cached; the same file and parser settings can return a cache hit.

Upload requires both approvals:

1. `mineru.allowExternalUpload` is `true` in the config;
2. `allowExternalUpload` is `true` in the individual `omnischolar_parse` call.

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

`omnischolar_sync` shows a plan before writing under `output.rootDirectory`. The directory can be a regular folder or part of an Obsidian vault.

Sync distinguishes new content, no change, metadata changes, parse changes, render changes, missing files, conflicts, exclusions, and interrupted recovery. Metadata repair, rerendering, and transaction recovery do not upload a PDF.

If managed Markdown was edited by hand, the default policy keeps it and writes the incoming version under `.conflicts/`. Review both files before merging.

Before using a real vault, point `output.rootDirectory` at a temporary directory and inspect the folder names, Markdown, and image links.
