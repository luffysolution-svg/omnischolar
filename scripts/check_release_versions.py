"""Fail if published package and plugin versions are inconsistent."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    source_version = re.search(
        r'__version__\s*=\s*"([^"]+)"',
        (ROOT / "src/omnischolar/version.py").read_text(encoding="utf-8"),
    )
    if source_version is None or source_version.group(1) != version:
        raise SystemExit("src/omnischolar/version.py does not match pyproject.toml")

    for relative in [
        "package.json",
        "package-lock.json",
        "plugin.json",
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
    ]:
        if json.loads((ROOT / relative).read_text(encoding="utf-8")).get("version") != version:
            raise SystemExit(f"{relative} does not match {version}")

    server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    if server["version"] != version or server["packages"][0]["version"] != version:
        raise SystemExit("server.json does not match the release version")

    for relative in ["mcp.json", ".mcp.json"]:
        document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        args = document["mcpServers"]["omnischolar"]["args"]
        expected = "luffysolution-omnischolar@latest"
        if expected not in args:
            raise SystemExit(f"{relative} launches a different PyPI version")

    bridge = (ROOT / "pi-extension/src/index.ts").read_text(encoding="utf-8")
    if f'version: "{version}"' not in bridge or "luffysolution-omnischolar@latest" not in bridge:
        raise SystemExit("Pi bridge does not match the release version")
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
