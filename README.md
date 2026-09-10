# OmniScholar

<!-- mcp-name: io.github.luffysolution-svg/omnischolar -->

English | [简体中文](README.zh-CN.md)

OmniScholar adds literature search, local Zotero reading, PDF parsing, citation tools, materials data, and scientific image generation to coding agents through a local Python MCP server.

It can search public indexes, combine online records with your Zotero notes, send an approved PDF to MinerU, and publish Markdown into a regular folder or an Obsidian vault. Zotero access is read-only.

## Features

- Search Semantic Scholar, OpenAlex, PubMed/PMC, arXiv, Crossref, Unpaywall, easyScholar, Google Scholar, and Google Patents
- Retrieve paper details, authors, citations, references, recommendations, snippets, datasets, and journal metrics
- Read Zotero collections, items, notes, annotations, attachments, indexed text, and local PDF paths without changing the library
- Parse selected PDFs with MinerU and keep text, formulas, tables, and figures together
- Find citation candidates, check bibliographic identity, and format accepted references
- Query Materials Project and export JSON, CSV, Markdown, or CIF
- Generate or edit scientific illustrations with configured image services
- Preserve local Markdown edits and place incoming conflict versions in `.conflicts/`

OmniScholar exposes 38 tools. See the [tool list](docs/TOOLS.en.md).

## Install

Python 3.11 or newer is required:

```sh
uv tool install luffysolution-omnischolar
# or
pipx install luffysolution-omnischolar
# or
python -m pip install luffysolution-omnischolar
```

For development from a source checkout, replace the package name with `.`.

The distribution name is `luffysolution-omnischolar`; the command and Python package are `omnischolar`.

Check the installation:

```sh
omnischolar --version
omnischolar doctor --json
```

## Connect an agent

### Codex app and Codex CLI plugin

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first, then add the OmniScholar Git marketplace and install the plugin:

```sh
codex plugin marketplace add luffysolution-svg/omnischolar --ref main
codex plugin add omnischolar@omnischolar
```

In the ChatGPT desktop app, restart the app, open **Plugins**, select the **OmniScholar** marketplace, and install or enable **OmniScholar**. In Codex CLI, run `/plugins` to browse the same marketplace.

The plugin bundles all eight Skills and starts its local MCP server with the pinned PyPI release:

```sh
uvx --from luffysolution-omnischolar==0.1.0 omnischolar mcp
```

No separate `pip install` is required for this plugin path. The first MCP start needs network access so `uvx` can download and cache the package. Provider credentials and optional service settings remain in your OmniScholar configuration; plugin installation does not collect them.

### Claude Code plugin

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first. In Claude Code, add the GitHub marketplace and install the plugin:

```text
/plugin marketplace add luffysolution-svg/omnischolar
/plugin install omnischolar@omnischolar
```

For scripts or a regular terminal, use the non-interactive shell commands:

```sh
claude plugin marketplace add luffysolution-svg/omnischolar
claude plugin install omnischolar@omnischolar --scope user
```

Run `/reload-plugins` if the install summary asks for it, then start a new session. The plugin automatically starts the same pinned `uvx` MCP server and exposes namespaced Skills such as `/omnischolar:scholar-search`. No separate Python installation is required.

### Host configuration installer

Preview the files that will change, then install the local MCP entry and Skills:

```sh
omnischolar install --dry-run claude
omnischolar install claude
```

Replace `claude` with `codex`, `cursor`, `opencode`, `hermes`, `pi`, or `workbuddy`. Codex, Claude Code, Cursor, OpenCode, Pi, and WorkBuddy/CodeBuddy support both user and project scopes. Hermes supports user-level MCP configuration; project-level installation adds Skills and reports that MCP setup is manual.

```sh
omnischolar install cursor --scope project
omnischolar update cursor --scope project
omnischolar uninstall cursor --scope project
```

For Pi, the full installer runs `pi install npm:@luffysolution/omnischolar-pi` and installs the bundled Skills separately. The npm Extension starts `omnischolar mcp`, discovers its tools, and registers them with Pi. You can also install the Extension directly:

```sh
pi install npm:@luffysolution/omnischolar-pi
```

WorkBuddy/CodeBuddy uses `~/.codebuddy/.mcp.json` for user scope and `.mcp.json` for project scope. It does not publish a portable Skills path, so its installer configures MCP and reports Skills as `manual_required`.

The MCP command is:

```sh
omnischolar mcp
```

Normally the agent starts this process from its MCP configuration. The installer checks `initialize`, `tools/list`, and `omnischolar_status` after writing a supported configuration.

Full host and update instructions are in [Installation](docs/INSTALLATION.en.md).

## Try it

```text
Find five recent reviews about solid-state battery interfaces. Deduplicate by DOI and show open-access copies.

Find this DOI in my Zotero library and summarize my notes and annotations without changing Zotero.

After I approve the upload, parse this PDF with MinerU and save a reading note in my Obsidian vault.

Query stable Li-Fe-P-O materials in Materials Project and export the selected records as CSV and CIF.

Create a labelled illustration of this mechanism. Treat it as a draft, not experimental data.
```

## Configuration

Copy [`omnischolar.config.example.json`](omnischolar.config.example.json) to `omnischolar.config.json`. Keep API keys in environment variables and refer to their names with `apiKeyEnv`.

A small local configuration can start with Zotero and the output directory:

```json
{
  "schemaVersion": 1,
  "runtime": { "workspaceRoots": ["./research-inputs"] },
  "zotero": {
    "enabled": true,
    "baseUrl": "http://127.0.0.1:23119/api"
  },
  "output": { "rootDirectory": "./research-output" }
}
```

OpenAlex, PubMed, arXiv, and Crossref work without API keys. Other services are enabled separately. Configuration fields and provider examples are in [Configuration](docs/CONFIGURATION.en.md).

## Files, uploads, and charges

- Zotero requests go only to the local API on port `23119` and use GET.
- MinerU receives a PDF only when `allowExternalUpload` is enabled in the config and confirmed again in that tool call.
- Image services receive prompts and any reference images selected for upload. Generation may use account credit.
- Ai4Scholar calls may use account credit. A stored key does not by itself approve a paid call.
- A failed paid request is not retried automatically when the provider may already have accepted it.
- Generated images are illustrations. They are not measurements, experimental evidence, or scientific results.

See [`PRIVACY.md`](PRIVACY.md) and [Configuration](docs/CONFIGURATION.en.md) before enabling uploads or paid services.

## Included Skills

| Skill | Use |
|---|---|
| `omnischolar` | Choose and combine tools for a research request |
| `scholar-search` | Literature, patents, authors, citation graphs, journals, and datasets |
| `zotero-research` | Local Zotero matching, notes, annotations, and attachments |
| `paper-reading` | MinerU parsing and close reading of text, formulas, tables, and figures |
| `academic-citation` | Evidence checks, citation candidates, formatting, and bibliographies |
| `scientific-figure` | Image generation, editing, review, and scientific labelling |
| `materials-project` | Materials screening, properties, provenance, phase data, and export |
| `chemical-data` | CAS Common Chemistry records when an official interface description is configured |

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
