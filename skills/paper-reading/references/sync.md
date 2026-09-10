# Local synchronization decisions

Use `omnischolar_sync` and its structured status; never infer safety from filenames.

- `new`: parsing may be required. Confirm the selected PDF and external-upload authorization.
- `up_to_date`: read the existing output; no upload is needed.
- `metadata_changed`: refresh local metadata where possible; this does not require parsing by itself.
- `parse_changed`: parser inputs changed. A new MinerU call requires explicit upload authorization.
- `render_changed`: regenerate local presentation without a remote call.
- `missing`: ordinary synchronization stops. Restore only on explicit request.
- `incomplete`: repair missing managed artifacts from a valid cache when possible. If cache is absent, obtain upload authorization before parsing again.
- `excluded`: skip until the user explicitly unexcludes it. Unexclude does not authorize download or upload.
- `conflict`: preserve local managed files and review the generated `.conflicts/` candidate.
- `recovery_required`: call `omnischolar_sync` with `action=recover` before further publication. Recovery is local and must not upload a PDF.

Re-plan whenever inputs or local files changed after planning. Unmanaged files must be preserved. Cache clearing and exclusion clearing are distinct. An unknown parser version remains unknown. Zotero stays GET-only throughout.
