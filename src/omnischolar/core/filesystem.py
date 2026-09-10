"""Filesystem confinement, atomic writes, temporary files, and safe ZIP handling."""

from __future__ import annotations

import os
import stat
import tempfile
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import anyio

from .errors import OmniScholarError


@dataclass(frozen=True, slots=True)
class Artifact:
    path: Path
    media_type: str
    size: int
    sha256: str | None = None


def confined_path(root: Path, relative: str | Path, *, must_exist: bool = False) -> Path:
    root_real = root.expanduser().resolve()
    candidate = (root_real / relative).resolve(strict=must_exist)
    try:
        candidate.relative_to(root_real)
    except ValueError as exc:
        raise OmniScholarError(
            "unsafe_path",
            "Path escapes the configured root",
            category="filesystem",
            cause=exc,
        ) from exc
    return candidate


def confined_input(path: Path, roots: tuple[Path, ...]) -> Path:
    candidate = path.expanduser().resolve(strict=True)
    for root in roots:
        try:
            candidate.relative_to(root.expanduser().resolve(strict=True))
            return candidate
        except ValueError:
            continue
    raise OmniScholarError(
        "input_outside_workspace",
        "Input file is outside configured workspace roots",
        category="authorization",
    )


async def read_file_bounded(path: Path, max_bytes: int) -> bytes:
    resolved = path.resolve(strict=True)
    info = await anyio.to_thread.run_sync(resolved.stat)
    if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
        raise OmniScholarError(
            "file_too_large",
            f"Input file exceeds the {max_bytes}-byte limit or is not regular",
            category="limits",
        )
    async with await anyio.open_file(resolved, "rb") as handle:
        data = await handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise OmniScholarError(
            "file_too_large", "Input file grew beyond its limit", category="limits"
        )
    return data


async def atomic_write(root: Path, relative: str | Path, data: bytes) -> Path:
    target = confined_path(root, relative)
    await anyio.to_thread.run_sync(lambda: target.parent.mkdir(parents=True, exist_ok=True))
    parent_real = target.parent.resolve(strict=True)
    root_real = root.expanduser().resolve()
    try:
        parent_real.relative_to(root_real)
    except ValueError as exc:
        raise OmniScholarError(
            "unsafe_path", "Write parent escapes output root", category="filesystem"
        ) from exc
    # Keep the temporary component short: hash-addressed targets can otherwise
    # cross the legacy Windows MAX_PATH boundary solely because of the prefix.
    descriptor, temporary = tempfile.mkstemp(prefix=".omni-", dir=target.parent)
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        async with await anyio.open_file(temporary_path, "wb") as handle:
            await handle.write(data)
            await handle.flush()
        await anyio.to_thread.run_sync(os.replace, temporary_path, target)
        return target
    finally:
        if temporary_path.exists():
            await anyio.to_thread.run_sync(temporary_path.unlink, True)


@asynccontextmanager
async def temporary_path(*, directory: Path | None = None, suffix: str = "") -> AsyncIterator[Path]:
    descriptor, name = tempfile.mkstemp(dir=directory, suffix=suffix)
    os.close(descriptor)
    path = Path(name)
    try:
        yield path
    finally:
        if path.exists():
            await anyio.to_thread.run_sync(path.unlink, True)


def validate_zip(
    archive: Path,
    *,
    max_entries: int = 10_000,
    max_uncompressed_bytes: int = 512 * 1024 * 1024,
) -> list[zipfile.ZipInfo]:
    try:
        with zipfile.ZipFile(archive) as handle:
            entries = handle.infolist()
            if len(entries) > max_entries:
                raise OmniScholarError(
                    "archive_too_large", "Archive has too many entries", category="limits"
                )
            expanded = 0
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                path = Path(name)
                if path.is_absolute() or ".." in path.parts:
                    raise OmniScholarError(
                        "unsafe_archive", "Archive contains an unsafe path", category="filesystem"
                    )
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise OmniScholarError(
                        "unsafe_archive", "Archive contains a symbolic link", category="filesystem"
                    )
                expanded += entry.file_size
                if expanded > max_uncompressed_bytes:
                    raise OmniScholarError(
                        "archive_too_large", "Archive expands beyond its limit", category="limits"
                    )
            return entries
    except zipfile.BadZipFile as exc:
        raise OmniScholarError(
            "invalid_archive", "Provider archive is not a valid ZIP", category="provider", cause=exc
        ) from exc
