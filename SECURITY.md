# Security policy

## Supported version

Security fixes target the latest released OmniScholar version. Version 0.1.0 is the current release.

## Report a vulnerability

Email `LuffySolution@gmail.com` with the affected version, reproduction steps, and expected impact. Do not include API keys, signed URLs, private papers, or personal Zotero data.

Please do not open a public issue before a vulnerability is fixed. This open-source project does not promise a fixed response time.

## Security properties

- Zotero is local and GET-only.
- Paid calls and uploads require approval in both configuration and the individual call.
- Local file access stays within configured roots.
- MinerU archives are checked before extraction.
- Known secrets are removed from status, errors, logs, and tool results.
- Host installers do not write provider keys.

Provider accounts, retention policies, service availability, and provider endpoints are controlled by their operators.
