from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodexPluginPackageTests(unittest.TestCase):
    def test_portable_mcp_uses_pinned_pypi_release(self) -> None:
        document = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        server = document["mcpServers"]["omnischolar"]
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "uvx")
        self.assertEqual(
            server["args"],
            [
                "--from",
                "luffysolution-omnischolar==0.1.0",
                "omnischolar",
                "mcp",
            ],
        )

    def test_repo_marketplace_exposes_root_plugin(self) -> None:
        path = ROOT / ".agents" / "plugins" / "marketplace.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["name"], "omnischolar")
        self.assertEqual(len(document["plugins"]), 1)
        plugin = document["plugins"][0]
        self.assertEqual(plugin["name"], "omnischolar")
        self.assertEqual(plugin["source"]["source"], "url")
        self.assertEqual(
            plugin["source"]["url"],
            "https://github.com/luffysolution-svg/omnischolar.git",
        )
        self.assertEqual(plugin["source"]["ref"], "main")

    def test_claude_marketplace_exposes_root_plugin(self) -> None:
        path = ROOT / ".claude-plugin" / "marketplace.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["name"], "omnischolar")
        self.assertEqual(document["owner"]["email"], "LuffySolution@gmail.com")
        self.assertEqual(len(document["plugins"]), 1)
        plugin = document["plugins"][0]
        self.assertEqual(plugin["name"], "omnischolar")
        self.assertEqual(plugin["source"], "./")

    def test_claude_and_portable_mcp_launchers_match(self) -> None:
        portable = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        claude = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(
            claude["mcpServers"]["omnischolar"],
            portable["mcpServers"]["omnischolar"],
        )


if __name__ == "__main__":
    unittest.main()
