# Configuration

[简体中文](CONFIGURATION.md)

OmniScholar uses JSON with `schemaVersion: 1`. Start with [`omnischolar.config.example.json`](../omnischolar.config.example.json) and remove services you do not use.

## Config file location

The first matching file is used; files are not merged:

1. the path passed with `--config PATH`
2. the file named by `OMNISCHOLAR_CONFIG`
3. `omnischolar.config.json` in the current project
4. `omnischolar.config.json` in the user config directory
5. built-in defaults

Relative paths resolve from the config file. Misspelled fields and invalid values are rejected.

Services in the example configuration are enabled by default. Fill in the relevant API key to use them directly.

If none of the first four sources exists, the first MCP start or installer run creates a complete user-level configuration template. The template includes all service sections, `apiKey`, `apiKeyEnv`, and Vertex fields such as `project` and `location`. On Windows this is normally `%LOCALAPPDATA%\\omnischolar\\omnischolar.config.json`, on Linux `~/.config/omnischolar/omnischolar.config.json`, and on macOS `~/Library/Application Support/omnischolar/omnischolar.config.json`. You can also run `omnischolar config init`. Existing configuration is never overwritten. Nested files created by older versions are not migrated or read automatically; copy settings manually if needed.

## Minimal config

```json
{
  "schemaVersion": 1,
  "runtime": {
    "workspaceRoots": ["./research-inputs"],
    "requestTimeoutSeconds": 30
  },
  "zotero": {
    "enabled": true,
    "baseUrl": "http://127.0.0.1:23119/api"
  },
  "output": {
    "rootDirectory": "./research-output"
  }
}
```

`workspaceRoots` limits local file reads. `output.rootDirectory` limits file writes. To use Obsidian, set the output directory to a folder inside the vault.

The core services support Windows, Linux, and macOS. Zotero features require Zotero Desktop on the local machine; XRD calculation requires the optional `pymatgen` backend.

`omnischolar_status` does not display the absolute config path. Use `omnischolar config path` when the path is needed.

The new-paper subfolder and file name can be customized as well:

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

Paper and folder templates support `{author}`, `{year}`, `{title}`, and `{separator}`; `folderNameTemplate` controls each paper directory name. The shared separator accepts `-`, `+`, and `_` and is available to paper, folder, and attachment templates. Attachment filenames support `{index}`, `{original}`, `{extension}`, and `{separator}`. These settings affect new publications only; existing sync records keep the path stored in the manifest. Here, attachment means a parsed image asset, not the original Zotero PDF attachment.

## Zotero reading records and structured analyses

```json
{
  "output": {
    "source": {
      "directory": "source",
      "copyPdf": true,
      "pdfFilenameTemplate": "paper.pdf",
      "zoteroReadingRecordFilename": "zotero-reading-record.md",
      "embedPdf": true
    },
    "analysis": {
      "singleDirectory": "Analysis/Single",
      "multiDirectory": "Analysis/Multi",
      "singleFilenameTemplate": "{analysisType}",
      "comparisonFilenameTemplate": "{date}{separator}{topic}{separator}compare",
      "reviewFilenameTemplate": "{date}{separator}{topic}{separator}review"
    }
  }
}
```

The reading record keeps Zotero notes and PDF annotations in separate sections. `omnischolar_analysis` writes `full-read` or `targeted-reading` under the single-paper directory, and `compare` or `review` under the multi-paper directory. It records source fingerprints and relative links and does not overwrite local analysis edits by default.

## API keys

API keys may be entered directly in the provider's `apiKey` field:

```json
{
  "schemaVersion": 1,
  "ai4scholar": {
    "enabled": true,
    "apiKey": "paste Ai4Scholar API key here"
  },
  "data": {
    "materialsProject": {
      "enabled": true,
      "apiKey": "paste Materials Project API key here"
    }
  }
}
```

Alternatively, set `apiKeyEnv` to read the key from an environment variable:

```json
{
  "mineru": {
    "enabled": true,
    "apiKeyEnv": "OMNISCHOLAR_MINERU_API_KEY"
  }
}
```

Credential order is `apiKey`, the variable named by `apiKeyEnv`, then the service's default environment variable. Direct config entry is the simplest local setup, but the file then contains a secret: restrict its permissions and never commit it or copy it into agent MCP configuration.

| Service | Key or account requirement |
|---|---|
| OpenAlex, PubMed, arXiv, Crossref | Basic search works without keys; a PubMed key can raise NCBI request limits |
| Semantic Scholar | Optional key; shared anonymous traffic is more likely to receive 429 |
| Unpaywall | Contact email required |
| easyScholar | API key required |
| Zotero | No key; the local API must be enabled |
| MinerU | API key |
| Ai4Scholar | API key; some calls use account credit |
| Materials Project | API key required |
| Image services | Provider key, model, and endpoint as required |
| CAS Common Chemistry | A provider-supplied interface description file is still required |

## Paid calls and uploads

After the relevant API key is configured, Ai4Scholar, image generation, MinerU, and reference-image uploads work directly. Providers without keys do not make requests automatically.
- Sync recovery only repairs local files.
- If a paid request times out after the provider may have accepted it, OmniScholar does not retry automatically.

## Literature search

```json
{
  "schemaVersion": 1,
  "research": {
    "fallback": true,
    "maxPages": 5,
    "providers": {
      "openalex": { "enabled": true, "email": "researcher@example.org" },
      "pubmed": { "enabled": true, "email": "researcher@example.org" },
      "arxiv": { "enabled": true },
      "crossref": { "enabled": true, "email": "researcher@example.org" },
      "unpaywall": { "enabled": true, "email": "researcher@example.org" }
    }
  }
}
```

`fallback` moves only to another service that supports the same operation. HTTP 429 is returned as a rate-limit result and does not start an immediate retry loop.

## MinerU

```json
{
  "schemaVersion": 1,
  "mineru": {
    "enabled": true,
    "apiKeyEnv": "OMNISCHOLAR_MINERU_API_KEY",
    "model": "pipeline"
  }
}
```

The MinerU v1 fallback is off by default. Provider documentation currently gives inconsistent page limits, so OmniScholar does not switch APIs on its own.

## Check the config

```sh
omnischolar config path
omnischolar config schema
omnischolar status
omnischolar doctor --json
```

