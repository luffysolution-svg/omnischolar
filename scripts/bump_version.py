"""Synchronize the release version across all published surfaces."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated = text.replace(old, new)
    if updated == text and new not in text:
        raise SystemExit(f"version {old!r} was not found in {path}")
    path.write_text(updated, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new semantic version, for example 0.1.3")
    args = parser.parse_args()
    if not VERSION_RE.fullmatch(args.version):
        parser.error("version must be strict semantic version syntax")

    pyproject = ROOT / "pyproject.toml"
    match = re.search(r'^version = "([^"]+)"$', pyproject.read_text(encoding="utf-8"), re.M)
    if match is None:
        raise SystemExit("project version was not found in pyproject.toml")
    old = match.group(1)

    exact_files = [
        "pyproject.toml",
        "src/omnischolar/version.py",
        "package.json",
        "package-lock.json",
        "plugin.json",
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
        "server.json",
        "mcp.json",
        ".mcp.json",
        "pi-extension/src/index.ts",
        "uv.lock",
    ]
    for relative in exact_files:
        _replace(ROOT / relative, old, args.version)

    for path in [
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        ROOT / "docs/INSTALLATION.md",
        ROOT / "docs/INSTALLATION.en.md",
    ]:
        _replace(path, f"luffysolution-omnischolar=={old}", f"luffysolution-omnischolar=={args.version}")

    # Validate JSON after the mechanical update so a malformed edit cannot be released.
    for relative in [
        "package.json",
        "package-lock.json",
        "plugin.json",
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
        "server.json",
        "mcp.json",
        ".mcp.json",
    ]:
        json.loads((ROOT / relative).read_text(encoding="utf-8"))
    print(f"updated {old} -> {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
