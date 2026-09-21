# Local synchronization decisions

Read this reference only for an explicit synchronization, repair, exclusion, conflict, or recovery request. A direct `omnischolar_parse` call performs MinerU cache lookup or an authorized upload before publication calls `plan`; do not preflight a parse with `omnischolar_sync` merely to discover these states earlier.

Use `omnischolar_sync` and its structured status; never infer safety from filenames.

- `new`: no managed publication exists yet.
- `up_to_date`: use the existing output; no upload is needed.
- `metadata_changed`: bibliographic metadata changed; it does not by itself require a new parse.
- `parse_changed`: parser inputs differ from the recorded parse. A fresh parse or cache lookup may be required.
- `render_changed`: local rendering rules changed; this does not by itself require a remote call.
- `missing`: managed files are absent. Restore only on explicit request.
- `incomplete`: managed artifacts are incomplete. Repair from valid cache when possible.
- `excluded`: publishing remains blocked until the user explicitly unexcludes the record. Unexcluding does not authorize an upload.
- `conflict`: preserve local managed files and review the candidate under the configured conflict directory.
- `recovery_required`: complete local transaction recovery before another publication attempt. Recovery must not upload a PDF.

Re-plan when inputs or local files changed after a plan. Preserve unmanaged files. Cache clearing and exclusion clearing are distinct. An unknown parser version remains unknown. Zotero stays GET-only throughout.
