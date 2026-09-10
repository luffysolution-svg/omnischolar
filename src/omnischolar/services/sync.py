"""Transactional output publication and conservative incremental synchronization."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import anyio

from omnischolar.core import OmniScholarError, atomic_write, confined_path

SyncStatus = Literal[
    "new",
    "up_to_date",
    "metadata_changed",
    "parse_changed",
    "render_changed",
    "incomplete",
    "missing",
    "excluded",
    "conflict",
    "recovery_required",
]


def stable_hash(value: Any) -> str:
    if isinstance(value, bytes):
        data = value
    elif isinstance(value, str):
        data = value.encode()
    else:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def metadata_fingerprint(paper: dict[str, Any]) -> str:
    selected = {
        key: paper.get(key)
        for key in (
            "zoteroKey",
            "zoteroVersion",
            "itemType",
            "title",
            "creators",
            "date",
            "doi",
            "isbn",
            "issn",
            "publicationTitle",
            "volume",
            "issue",
            "pages",
            "url",
            "abstract",
            "tags",
            "collections",
            "notes",
            "annotations",
        )
    }
    raw_attachments = paper.get("attachments")
    attachments = raw_attachments if isinstance(raw_attachments, list) else []
    selected["attachments"] = [
        {
            key: attachment.get(key)
            for key in (
                "key",
                "version",
                "title",
                "filename",
                "contentType",
                "md5",
                "mtime",
                "selected",
            )
        }
        for attachment in attachments
        if isinstance(attachment, dict)
    ]
    return stable_hash(selected)


def render_key(markdown: str, options: dict[str, Any] | None = None) -> str:
    return stable_hash({"markdown": stable_hash(markdown), "options": options or {}})


def publication_id(paper: dict[str, Any], namespace: str) -> str:
    attachment = (paper.get("selectedPdf") or {}).get("key", "no-attachment")
    return f"zotero:{namespace}:{paper.get('zoteroKey')}:{attachment}"


def _safe_component(value: str, fallback: str) -> str:
    text = unicodedata.normalize("NFC", re.sub(r"<[^>]*>", "", value))
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .") or fallback
    if re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", text, re.IGNORECASE):
        text = f"_{text}"
    while len(text.encode()) > 200:
        text = text[:-1]
    return text or fallback


def paper_stem(paper: dict[str, Any]) -> str:
    raw_creators = paper.get("creators")
    creators: list[Any] = raw_creators if isinstance(raw_creators, list) else []
    author = next(
        (
            item
            for item in creators
            if isinstance(item, dict) and item.get("creatorType") == "author"
        ),
        {},
    )
    author_name = author.get("lastName") or author.get("name") or "UnknownAuthor"
    year = str(paper.get("year") or paper.get("date") or "UnknownYear")[:4]
    return _safe_component(f"{author_name}-{year}-{paper.get('title') or 'Untitled'}", "Untitled")


@dataclass(slots=True)
class SyncPlan:
    publication_id: str
    status: SyncStatus
    action: str
    reason: str
    metadata_fingerprint: str
    parse_key: str | None
    relative_path: str | None
    user_modified: list[str]
    missing_files: list[str]
    remote_call: Literal["none", "mineru"]
    render_key: str | None = None


class SyncService:
    schema_version = 1

    def __init__(
        self, output_root: Path, *, namespace: str | None = None, backup: bool = True
    ) -> None:
        self.root = output_root.resolve()
        self.namespace = namespace or f"vault-{stable_hash(str(self.root))[:16]}"
        self.backup = backup
        self.state_root = self.root / ".omnischolar"
        self.manifest_path = self.state_root / "manifest.json"
        self.transaction_root = self.state_root / "transactions"
        self.backup_root = self.state_root / "backups"
        self.conflict_root = self.root / ".conflicts"

    def _empty_manifest(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "revision": 0,
            "entries": {},
            "exclusions": {},
        }

    async def manifest(self) -> dict[str, Any]:
        try:
            raw = await anyio.Path(self.manifest_path).read_bytes()
        except FileNotFoundError:
            return self._empty_manifest()
        except OSError as exc:
            raise OmniScholarError(
                "manifest_read_failed",
                "Sync manifest could not be read",
                category="filesystem",
                cause=exc,
            ) from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OmniScholarError(
                "manifest_invalid",
                "Sync manifest is invalid JSON",
                category="filesystem",
                cause=exc,
            ) from exc
        if (
            not isinstance(value, dict)
            or value.get("schemaVersion") != 1
            or not isinstance(value.get("entries"), dict)
        ):
            raise OmniScholarError(
                "manifest_invalid", "Sync manifest schema is invalid", category="filesystem"
            )
        for identifier, entry in value["entries"].items():
            if not isinstance(entry, dict) or entry.get("publicationId") != identifier:
                raise OmniScholarError(
                    "manifest_invalid", "Sync manifest identity is invalid", category="filesystem"
                )
            confined_path(self.root, entry.get("relativePath", ""))
        return value

    async def _write_manifest(self, manifest: dict[str, Any]) -> None:
        await atomic_write(
            self.state_root,
            "manifest.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
        )

    async def _artifact_state(self, entry: dict[str, Any]) -> tuple[list[str], list[str]]:
        directory = confined_path(self.root, entry["relativePath"])
        baseline = entry.get("baseline", {})
        missing: list[str] = []
        modified: list[str] = []
        for relative, expected in baseline.items():
            target = confined_path(directory, relative)
            if not target.is_file():
                missing.append(relative)
                continue
            actual = stable_hash(await anyio.Path(target).read_bytes())
            if actual != expected:
                modified.append(relative)
        return missing, modified

    async def plan(
        self,
        paper: dict[str, Any],
        *,
        parse_key: str | None = None,
        candidate_render_key: str | None = None,
    ) -> SyncPlan:
        manifest = await self.manifest()
        identifier = publication_id(paper, self.namespace)
        fingerprint = metadata_fingerprint(paper)
        entry = manifest["entries"].get(identifier)
        if identifier in manifest.get("exclusions", {}) or (entry and entry.get("excluded")):
            return SyncPlan(
                identifier,
                "excluded",
                "skip",
                "Publication is explicitly excluded",
                fingerprint,
                parse_key,
                entry.get("relativePath") if entry else None,
                [],
                [],
                "none",
            )
        if list(self.transaction_root.glob("*.json")) if self.transaction_root.exists() else []:
            return SyncPlan(
                identifier,
                "recovery_required",
                "recover",
                "An unfinished transaction requires recovery",
                fingerprint,
                parse_key,
                entry.get("relativePath") if entry else None,
                [],
                [],
                "none",
            )
        if entry is None:
            return SyncPlan(
                identifier,
                "new",
                "parse",
                "No managed publication exists",
                fingerprint,
                parse_key,
                None,
                [],
                [],
                "mineru",
            )
        directory = confined_path(self.root, entry["relativePath"])
        if not directory.exists():
            return SyncPlan(
                identifier,
                "missing",
                "skip",
                "Published directory is missing; explicit restore is required",
                fingerprint,
                parse_key,
                entry["relativePath"],
                [],
                [entry["relativePath"]],
                "none",
            )
        missing, modified = await self._artifact_state(entry)
        if modified:
            return SyncPlan(
                identifier,
                "conflict",
                "skip",
                "Local managed files differ from their baseline",
                fingerprint,
                parse_key,
                entry["relativePath"],
                modified,
                missing,
                "none",
            )
        if missing:
            return SyncPlan(
                identifier,
                "incomplete",
                "repair",
                "Managed files are missing",
                fingerprint,
                parse_key,
                entry["relativePath"],
                [],
                missing,
                "none",
            )
        if parse_key and parse_key != entry.get("parseKey"):
            return SyncPlan(
                identifier,
                "parse_changed",
                "parse",
                "PDF or effective parser options changed",
                fingerprint,
                parse_key,
                entry["relativePath"],
                [],
                [],
                "mineru",
            )
        if candidate_render_key and candidate_render_key != entry.get("renderKey"):
            return SyncPlan(
                identifier,
                "render_changed",
                "render",
                "Local rendering inputs changed",
                fingerprint,
                parse_key,
                entry["relativePath"],
                [],
                [],
                "none",
                candidate_render_key,
            )
        if fingerprint != entry.get("metadataFingerprint"):
            return SyncPlan(
                identifier,
                "metadata_changed",
                "refresh_metadata",
                "Zotero metadata changed",
                fingerprint,
                parse_key,
                entry["relativePath"],
                [],
                [],
                "none",
                entry.get("renderKey"),
            )
        return SyncPlan(
            identifier,
            "up_to_date",
            "skip",
            "Inputs and managed files match",
            fingerprint,
            parse_key,
            entry["relativePath"],
            [],
            [],
            "none",
            entry.get("renderKey"),
        )

    async def publish(
        self,
        paper: dict[str, Any],
        markdown: str,
        assets: dict[str, bytes],
        *,
        parse_key: str,
        parser_version: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        candidate_render_key = render_key(markdown)
        plan = await self.plan(
            paper,
            parse_key=parse_key,
            candidate_render_key=candidate_render_key,
        )
        if plan.status in {"conflict", "recovery_required", "excluded"}:
            candidate = await self._save_conflict(plan.publication_id, markdown, assets)
            raise OmniScholarError(
                "sync_conflict",
                f"{plan.reason}; candidate saved at {candidate}",
                category="conflict",
            )
        if plan.status == "missing" and not force:
            raise OmniScholarError("restore_required", plan.reason, category="authorization")
        stem = paper_stem(paper)
        relative = plan.relative_path or f"Literatures/{stem}"
        destination = confined_path(self.root, relative)
        staging = confined_path(self.state_root, f"staging/{uuid.uuid4()}")
        journal = confined_path(self.transaction_root, f"{uuid.uuid4()}.json")
        await anyio.to_thread.run_sync(lambda: staging.mkdir(parents=True, exist_ok=False))
        backup: Path | None = None
        try:
            if destination.exists():
                await anyio.to_thread.run_sync(
                    lambda: shutil.copytree(destination, staging, dirs_exist_ok=True)
                )
            managed: dict[str, str] = {}
            markdown_name = f"{stem}.md"
            await atomic_write(staging, markdown_name, markdown.encode())
            managed[markdown_name] = stable_hash(markdown)
            for name, content in assets.items():
                if Path(name).name != name:
                    raise OmniScholarError(
                        "unsafe_asset_name", "Generated asset name is unsafe", category="filesystem"
                    )
                await atomic_write(staging, f"assets/{name}", content)
                managed[f"assets/{name}"] = stable_hash(content)
            sidecar = {
                "schemaVersion": 1,
                "publication": {"id": plan.publication_id, "namespace": self.namespace},
                "zotero": paper,
                "parse": {"key": parse_key, "parserVersion": parser_version},
            }
            sidecar_bytes = (
                json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode()
            await atomic_write(staging, "metadata.json", sidecar_bytes)
            managed["metadata.json"] = stable_hash(sidecar_bytes)
            transaction = {
                "publicationId": plan.publication_id,
                "state": "prepared",
                "destination": relative,
                "staging": str(staging.relative_to(self.root)),
                "backup": None,
            }
            await atomic_write(
                self.transaction_root, journal.name, json.dumps(transaction).encode()
            )
            await anyio.to_thread.run_sync(
                lambda: destination.parent.mkdir(parents=True, exist_ok=True)
            )
            if destination.exists():
                backup = confined_path(self.backup_root, f"{int(time.time())}-{uuid.uuid4()}")
                await anyio.to_thread.run_sync(
                    lambda: backup.parent.mkdir(parents=True, exist_ok=True)
                )
                await anyio.to_thread.run_sync(os.replace, destination, backup)
                transaction.update(
                    {"state": "original_staged", "backup": str(backup.relative_to(self.root))}
                )
                await atomic_write(
                    self.transaction_root, journal.name, json.dumps(transaction).encode()
                )
            await anyio.to_thread.run_sync(os.replace, staging, destination)
            transaction["state"] = "new_installed"
            await atomic_write(
                self.transaction_root, journal.name, json.dumps(transaction).encode()
            )
            manifest = await self.manifest()
            manifest["revision"] += 1
            manifest["entries"][plan.publication_id] = {
                "publicationId": plan.publication_id,
                "relativePath": relative.replace("\\", "/"),
                "metadataFingerprint": metadata_fingerprint(paper),
                "parseKey": parse_key,
                "renderKey": candidate_render_key,
                "parserVersion": parser_version,
                "baseline": managed,
                "excluded": False,
                "updatedAt": time.time(),
            }
            manifest.get("exclusions", {}).pop(plan.publication_id, None)
            await self._write_manifest(manifest)
            await anyio.Path(journal).unlink(missing_ok=True)
            if backup and not self.backup:
                await anyio.to_thread.run_sync(shutil.rmtree, backup, True)
            return {
                "publicationId": plan.publication_id,
                "directory": str(destination),
                "status": "up_to_date",
                "revision": manifest["revision"],
            }
        except BaseException:
            if staging.exists():
                await anyio.to_thread.run_sync(shutil.rmtree, staging, True)
            raise

    async def _save_conflict(
        self, identifier: str, markdown: str, assets: dict[str, bytes]
    ) -> Path:
        directory = confined_path(
            self.conflict_root, f"{_safe_component(identifier, 'publication')}-{uuid.uuid4()}"
        )
        await atomic_write(directory, "candidate.md", markdown.encode())
        for name, content in assets.items():
            await atomic_write(directory, f"assets/{Path(name).name}", content)
        return directory

    async def exclude(self, identifier: str, *, reason: str | None = None) -> dict[str, Any]:
        manifest = await self.manifest()
        manifest["revision"] += 1
        manifest.setdefault("exclusions", {})[identifier] = {"reason": reason, "at": time.time()}
        if identifier in manifest["entries"]:
            manifest["entries"][identifier]["excluded"] = True
        await self._write_manifest(manifest)
        return manifest

    async def unexclude(self, identifier: str) -> dict[str, Any]:
        manifest = await self.manifest()
        manifest["revision"] += 1
        manifest.setdefault("exclusions", {}).pop(identifier, None)
        if identifier in manifest["entries"]:
            manifest["entries"][identifier]["excluded"] = False
        await self._write_manifest(manifest)
        return manifest

    async def recover(self) -> list[dict[str, str]]:
        recovered: list[dict[str, str]] = []
        if not self.transaction_root.exists():
            return recovered
        for path in self.transaction_root.glob("*.json"):
            try:
                value = json.loads(await anyio.Path(path).read_bytes())
                destination = confined_path(self.root, value["destination"])
                staging = confined_path(self.root, value["staging"])
                backup = confined_path(self.root, value["backup"]) if value.get("backup") else None
                if (
                    value.get("state") in {"prepared", "original_staged"}
                    and not destination.exists()
                    and backup
                    and backup.exists()
                ):
                    await anyio.to_thread.run_sync(os.replace, backup, destination)
                    recovered.append(
                        {"publicationId": value["publicationId"], "state": "restored_backup"}
                    )
                elif value.get("state") == "new_installed" and destination.exists():
                    recovered.append(
                        {
                            "publicationId": value["publicationId"],
                            "state": "installed_requires_manifest_review",
                        }
                    )
                if staging.exists():
                    await anyio.to_thread.run_sync(shutil.rmtree, staging, True)
                await anyio.Path(path).unlink(missing_ok=True)
            except (KeyError, json.JSONDecodeError, OSError) as exc:
                raise OmniScholarError(
                    "recovery_failed",
                    f"Recovery journal {path.name} is invalid",
                    category="filesystem",
                    cause=exc,
                ) from exc
        return recovered
