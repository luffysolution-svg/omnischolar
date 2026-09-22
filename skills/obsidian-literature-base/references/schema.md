# Generated literature catalogue schema

Read this reference when generating or changing an OmniScholar literature Base.

## Source discovery

A publication directory is valid when its `metadata.json` contains:

```json
{
  "schemaVersion": 1,
  "publication": {"id": "zotero:...", "namespace": "..."},
  "zotero": {},
  "parse": {}
}
```

The directory normally contains one top-level Markdown file with `recordType: mineru-publication`, an `assets/` directory, and `source/zotero-reading-record.md`. Do not count these as separate papers.

## Generated index properties

Each `literature-index.md` is fully generated and uses these stable keys:

| Property | Meaning |
|---|---|
| `recordType` | Always `literature-index` |
| `generatedBy` | Ownership marker used for safe refreshes |
| `title` | Zotero title |
| `authors` | All creator display names |
| `firstAuthor` | First author used for grouping |
| `year` | Four-digit year derived from Zotero year/date |
| `publicationTitle` | Journal or proceedings title |
| `topics` | Normalized prefixed-tag or AI topics |
| `topicLinks` | Wikilinks to generated shared-topic pages when Wiki mode is enabled |
| `topicSource` | `zotero-tag`, `ai`, or `missing` |
| `tags` | Source Zotero tags normalized for Obsidian |
| `abstract` | Zotero abstract |
| `cover` | First referenced MinerU image as an Obsidian embed link |
| `imageCount` | Number of previewable local images |
| `mineruDocument` | Link to the parsed Markdown |
| `zoteroRecord` | Link to the Zotero notes/annotations record |
| `zoteroLink` | `zotero://` item link |
| `publicationId`, `zoteroKey`, `DOI`, `URL` | Stable source identifiers |

The body links to the managed source documents and uses a default-collapsed callout for all images. Images are rendered at a compact width and remain openable at full size.

## Topic precedence

Default Zotero tag prefixes are `topic/` and `主题/`. Matching is case-insensitive; the stored topic preserves the suffix text. For example:

- `topic/Solid-state batteries` becomes `Solid-state batteries`.
- `主题/界面化学` becomes `界面化学`.

If at least one prefixed tag exists, ignore AI topics for that paper. Otherwise the optional AI mapping may provide 1–3 topics. Do not infer an AI topic when evidence is too weak; leave it missing.

The AI topics file is a JSON object keyed by publication ID, Zotero key, DOI, or exact title:

```json
{
  "PAPER123": ["固态电池", "界面化学"],
  "10.1000/example": ["催化", "原位表征"]
}
```

## Base views

All catalogue views operate on `recordType == "literature-index"`. The raw-products view instead includes `mineru-publication` and `zotero-reading-record`.

| View | Layout | Grouping |
|---|---|---|
| 文献总表 | table | none |
| 原始产物 | table | `recordType` |
| 按年份 | table | `year`, descending |
| 按作者 | table | `firstAuthor` |
| 按期刊 | table | `publicationTitle` |
| 按主题 | cards | `topics`, using `cover` as the image |
| 按标签 | table | `tags` |

Obsidian Base files are YAML. Keep formulas quoted, reference the card image as `note.cover`, and validate every formula/property referenced by a view.

## Optional Wiki output

`--wiki` creates `文献知识库.md` and topic pages under `Literature Wiki/Topics/` by default. Both paths are configurable. A topic page is created only when at least `--wiki-min-papers` papers share the topic; the default threshold is two.

The Wiki hub is fully generated and embeds `Literature.base#按主题` and `Literature.base#文献总表`. Each topic page has two explicitly marked regions:

- `MANUAL`: definitions, key questions, consensus, disputes, gaps, and related topics. Preserve it during every refresh.
- `AUTO`: related-paper links and current source metadata. Replace it during refresh.

Every claim added by AI to consensus or dispute sections must link supporting `literature-index.md` notes. Topic pages that no longer meet the threshold are reported as stale and retained until the user explicitly authorizes deletion.
