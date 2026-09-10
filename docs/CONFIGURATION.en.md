# Configuration

[简体中文](CONFIGURATION.md)

OmniScholar uses JSON with `schemaVersion: 1`. Start with [`omnischolar.config.example.json`](../omnischolar.config.example.json) and remove services you do not use.

## Config file location

The first matching file is used; files are not merged:

1. the path passed with `--config PATH`
2. the file named by `OMNISCHOLAR_CONFIG`
3. `omnischolar.config.json` in the current project
4. `omnischolar/omnischolar.config.json` in the user config directory
5. built-in defaults

Relative paths resolve from the config file. Misspelled fields and invalid values are rejected.

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

## API keys

Keep keys in environment variables and place only the variable name in the config:

```json
{
  "schemaVersion": 1,
  "ai4scholar": {
    "enabled": true,
    "apiKeyEnv": "OMNISCHOLAR_AI4SCHOLAR_API_KEY",
    "allowPaid": false
  },
  "data": {
    "materialsProject": {
      "enabled": true,
      "apiKeyEnv": "OMNISCHOLAR_MATERIALS_PROJECT_API_KEY"
    }
  }
}
```

Credential order is `apiKey`, the variable named by `apiKeyEnv`, then the service's default environment variable. Do not place plaintext keys in agent MCP files, Skills, command lines, or source control.

| Service | Key or account requirement |
|---|---|
| OpenAlex, PubMed, arXiv, Crossref | Basic search works without keys; a PubMed key can raise NCBI request limits |
| Semantic Scholar | Optional key; shared anonymous traffic is more likely to receive 429 |
| Unpaywall | Contact email required |
| easyScholar | API key required |
| Zotero | No key; the local API must be enabled |
| MinerU | API key and explicit PDF upload approval |
| Ai4Scholar | API key; some calls use account credit |
| Materials Project | API key required |
| Image services | Provider key, model, and endpoint as required |
| CAS Common Chemistry | A provider-supplied interface description file is still required |

## Paid calls and uploads

A stored key does not approve spending or upload.

- Ai4Scholar and image generation require `allowPaid` in the config and again in the individual tool call.
- MinerU and reference-image uploads require `allowExternalUpload` in the config and again in the tool call.
- Sync recovery only repairs local files; it does not reuse previous upload approval.
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
    "model": "pipeline",
    "allowExternalUpload": false
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

