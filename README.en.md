# OmniScholar

<!-- mcp-name: io.github.luffysolution-svg/omnischolar -->

[中文](README.md) | English

OmniScholar adds literature search, local Zotero reading, PDF parsing, citation tools, materials data, and scientific image generation to coding agents through a local Python MCP server.

It can search public indexes, combine online records with your Zotero notes, send an approved PDF to MinerU, and publish Markdown into a regular folder or an Obsidian vault. Zotero access is read-only.

## Features

- Search Semantic Scholar, OpenAlex, PubMed/PMC, arXiv, Crossref, Unpaywall, easyScholar, Google Scholar, and Google Patents
- Retrieve paper details, authors, citations, references, recommendations, snippets, datasets, and journal metrics
- Read Zotero collections, items, notes, annotations, attachments, indexed text, and local PDF paths without changing the library
- Read parsed papers by full-text cursor, figures, formulas, paragraphs, comparison, or review mode without loading the entire body into one context
- Parse selected PDFs with MinerU and keep text, formulas, tables, and figures together
- Find citation candidates, check bibliographic identity, and format accepted references
- Query Materials Project and export JSON, CSV, Markdown, or CIF
- Generate or edit scientific illustrations with configured image services
- Preserve local Markdown edits and place incoming conflict versions in `.conflicts/`

OmniScholar exposes 38 tools. See the [tool list](docs/TOOLS.en.md).

<details>
<summary>Install and connect an agent</summary>

Python 3.11 or newer is required:

```sh
uv tool install luffysolution-omnischolar
# or
pipx install luffysolution-omnischolar
# or
python -m pip install luffysolution-omnischolar
```

Check, update, or uninstall the Python command:

```sh
omnischolar --version
omnischolar doctor --json
uv tool upgrade luffysolution-omnischolar
uv tool uninstall luffysolution-omnischolar
```

Codex plugin:

```sh
codex plugin marketplace add luffysolution-svg/omnischolar --ref main
codex plugin add omnischolar@omnischolar
```

Update the installed Codex plugin:

```sh
codex plugin marketplace upgrade omnischolar
codex plugin remove omnischolar@omnischolar
codex plugin add omnischolar@omnischolar
```

Claude Code plugin:

```text
/plugin marketplace add luffysolution-svg/omnischolar
/plugin install omnischolar@omnischolar
```

Pi package:

```sh
pi install npm:@luffysolution/omnischolar-pi
pi update npm:@luffysolution/omnischolar-pi
pi remove npm:@luffysolution/omnischolar-pi
```

The standalone Skills CLI is optional because the plugins bundle their Skills:

```sh
npx skills add luffysolution-svg/omnischolar --skill '*' --agent codex --global --yes
npx skills update --global --yes
npx skills remove --skill '*' --agent codex --global --yes
```

The plugin and host configurations start the latest PyPI MCP with:

```sh
uvx --refresh-package luffysolution-omnischolar --from luffysolution-omnischolar@latest omnischolar mcp
```

</details>

## Agent configuration prompt

Use this as a starting prompt for an agent:

```text
You are my research assistant using OmniScholar. Search and cite reliable scholarly sources, verify DOI and bibliographic identity, and clearly distinguish evidence from inference. You may read Zotero but must never modify it. Ask before uploading any PDF or reference image to an external service or making a paid request. For PDF reading, use MinerU only after I approve the upload. Save approved literature notes and generated artifacts to the configured output directory, preserve local edits, and report the exact output paths. Treat generated scientific figures as illustrations, never as experimental evidence.
```

## Configuration and examples

On the first MCP start or installer run, OmniScholar creates a complete user-level `omnischolar.config.json` template. Services in the template are enabled by default; after you provide an API key, the corresponding service is ready to use, while services without credentials do not make requests automatically. API keys can be entered directly as `apiKey`, or supplied through the named `apiKeyEnv` environment variable.

Enable the service and fill in its API key to use Ai4Scholar, image generation, MinerU, and reference-image uploads directly.

The root [`mcp.json`](mcp.json) is a reusable MCP stdio example. It intentionally contains no API keys: the MCP process reads the global [`omnischolar.config.example.json`](omnischolar.config.example.json), which can be created with `omnischolar config init`. The plugin copy is [`.mcp.json`](.mcp.json).

Configure the Obsidian output location, paper folders, Markdown files, and parsed image assets with `output.rootDirectory`, `output.literatureDirectory`, `output.folderNameTemplate`, `output.filenameTemplate`, `output.filenameSeparator`, and `output.assetFilenameTemplate`; see [literature and output configuration](docs/RESEARCH.en.md).

## Try it

```text
Find five recent reviews about solid-state battery interfaces. Deduplicate by DOI and show open-access copies.

Find this DOI in my Zotero library and summarize my notes and annotations without changing Zotero.

After I approve the upload, parse this PDF with MinerU and save a reading note in my Obsidian vault.

Query stable Li-Fe-P-O materials in Materials Project and export the selected records as CSV and CIF.

Create a labelled illustration of this mechanism. Treat it as a draft, not experimental data.
```

## Documentation

- [Installation and agent setup](docs/INSTALLATION.en.md)
- [Configuration and service credentials](docs/CONFIGURATION.en.md)
- [Literature, Zotero, MinerU, citations, and output](docs/RESEARCH.en.md)
- [Materials and chemistry](docs/MATERIALS.en.md)
- [Scientific image providers](docs/IMAGE_PROVIDERS.en.md)
- [Tool list](docs/TOOLS.en.md)

## Support and license

OmniScholar is open source under the [MIT License](LICENSE). Open a [GitHub issue](https://github.com/luffysolution-svg/omnischolar/issues) or email `LuffySolution@gmail.com`. Remove keys, signed URLs, private paper content, and personal Zotero data before sending a report.

Third-party services and datasets keep their own terms and licenses. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
