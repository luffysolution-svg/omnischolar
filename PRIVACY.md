# Privacy notice

OmniScholar is open-source software that runs on the user's computer. The maintainers do not operate an OmniScholar service for version 0.1.0.

## Local data

Configuration, cache, output files, and Zotero Local API results remain on the local machine unless a selected tool calls an external service. Zotero access uses GET requests to the local API only.

## Data sent to other services

- Literature and materials tools send search terms, identifiers, and selected filters to the chosen data source.
- Ai4Scholar receives the request needed for the selected Ai4Scholar operation.
- MinerU receives a PDF only after the user approves that file upload.
- Image services receive the prompt and any reference images approved for upload.

Each provider has its own privacy, retention, training, region, and account policies. Review those policies before enabling the provider.

## Credentials

Environment variables are recommended for API keys. OmniScholar removes known secrets from tool results, status, errors, and logs, and does not write provider keys into Agent MCP files. Users are still responsible for protecting configuration files and shell history.

Privacy and security questions: `LuffySolution@gmail.com`.

This notice describes the software's behavior. A marketplace may require additional legal terms before publication.
