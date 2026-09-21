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


def _replace_package_lock_version(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'("version"\s*:\s*")' + re.escape(old) + r'(")')
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        raise SystemExit(f"root package versions were not found in {path}")
    replacements = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replacements
        if replacements >= 2:
            return match.group(0)
        replacements += 1
        return f"{match.group(1)}{new}{match.group(2)}"

    updated = pattern.sub(replace, text)
    if replacements != 2:
        raise SystemExit(f"expected two root package versions in {path}")
    path.write_text(updated, encoding="utf-8", newline="\n")


def _replace_uv_lock_version(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(\[\[package\]\]\s+name = "luffysolution-omnischolar"\s+version = ")'
        + re.escape(old)
        + r'(")'
    )
    updated, count = pattern.subn(rf"\g<1>{new}\g<2>", text, count=1)
    if count != 1:
        raise SystemExit(f"project version was not found in {path}")
    path.write_text(updated, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new semantic version, for example 0.1.3")
    args = parser.parse_args()
    if not VERSION_RE.fullmatch(args.version):
        parser.error("version must be strict semantic version syntax")

    pyproject = ROOT / "pyproject.toml"
    match = re.search(r'^version = "([^"]+)"$', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
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
        "pi-extension/src/index.ts",
        "uv.lock",
    ]
    for relative in exact_files:
        path = ROOT / relative
        if relative == "package-lock.json":
            _replace_package_lock_version(path, old, args.version)
        elif relative == "uv.lock":
            _replace_uv_lock_version(path, old, args.version)
        else:
            _replace(path, old, args.version)

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
