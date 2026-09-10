# Tool list

[简体中文](TOOLS.md)

Tool and capability names match the values returned to agents.

| Tool | Group | Capabilities | Side effects | Network | Credentials | Cost |
|---|---|---|---|---:|---|---|
| `omnischolar_status` | runtime | `runtime.status` | none | no | none | free |
| `omnischolar_capabilities` | runtime | `runtime.capabilities` | none | no | none | free |
| `research_sources` | literature | `literature.sources` | none | no | none | free |
| `literature_search` | literature | `literature.search` | none | yes | none | free |
| `literature_get` | literature | `literature.lookup` | none | yes | none | free |
| `literature_graph` | literature | `literature.references`, `literature.citations`, `literature.recommendations` | none | yes | none | free |
| `journal_metrics` | literature | `journal.metrics` | none | yes | none | free |
| `literature_fulltext` | literature | `fulltext.resolve`, `fulltext.fetch` | filesystem | yes | none | free |
| `zotero_collections` | zotero | `zotero.collections` | none | yes | none | free |
| `zotero_search` | zotero | `zotero.search` | none | yes | none | free |
| `zotero_item` | zotero | `zotero.item`, `zotero.aggregate` | none | yes | none | free |
| `omnischolar_parse` | parsing | `pdf.parse`, `sync.publish` | external-upload | yes | mineru | metered |
| `omnischolar_sync` | parsing | `sync.plan`, `sync.apply`, `sync.recovery` | filesystem | yes | none | free |
| `ai4scholar_search` | ai4scholar | `ai4scholar.search` | paid | yes | ai4scholar | paid |
| `ai4scholar_paper` | ai4scholar | `ai4scholar.paper` | paid | yes | ai4scholar | paid |
| `ai4scholar_author` | ai4scholar | `ai4scholar.author` | paid | yes | ai4scholar | paid |
| `ai4scholar_batch` | ai4scholar | `ai4scholar.batch` | paid | yes | ai4scholar | paid |
| `ai4scholar_recommend` | ai4scholar | `ai4scholar.recommend` | paid | yes | ai4scholar | paid |
| `ai4scholar_cite` | citation | `citation.format` | paid | yes | ai4scholar | paid |
| `ai4scholar_snippets` | ai4scholar | `ai4scholar.snippets` | paid | yes | ai4scholar | paid |
| `ai4scholar_credits` | ai4scholar | `ai4scholar.credits` | none | yes | ai4scholar | free |
| `ai4scholar_dataset` | ai4scholar | `ai4scholar.dataset` | paid | yes | ai4scholar | paid |
| `ai4scholar_journal` | ai4scholar | `ai4scholar.journal` | paid | yes | ai4scholar | paid |
| `ai4scholar_citation_candidates` | citation | `citation.candidates` | paid | yes | ai4scholar | paid |
| `ai4scholar_figure` | media | `media.generate`, `media.edit`, `media.vectorize` | paid | yes | ai4scholar | paid |
| `materials_capabilities` | materials | `materials.capabilities` | none | no | materials-project | free |
| `materials_search` | materials | `materials.search` | none | yes | materials-project | free |
| `materials_route_search` | materials | `materials.route-search` | none | yes | materials-project | free |
| `materials_get` | materials | `materials.lookup` | none | yes | materials-project | free |
| `materials_advanced` | materials | `materials.phase-diagram`, `materials.xrd` | none | yes | materials-project | free |
| `materials_export` | materials | `materials.export` | filesystem | no | none | free |
| `chemical_sources` | chemistry | `chemistry.sources` | none | no | none | free |
| `chemical_search` | chemistry | `chemistry.search` | none | yes | cas | free |
| `chemical_get` | chemistry | `chemistry.lookup` | none | yes | cas | free |
| `omnischolar_image_models` | media | `media.models` | none | yes | none | free |
| `omnischolar_image_generate` | media | `text-to-image`, `image-to-image`, `multi-reference` | paid | yes | none | paid |
| `omnischolar_image_edit` | media | `media.edit`, `multi-reference` | paid | yes | none | paid |
| `omnischolar_image_service` | media | `media.service` | none | yes | none | free |

Arguments not declared in a tool's input schema are rejected.
Paid or upload-capable tools require both configuration and per-call authorization.
