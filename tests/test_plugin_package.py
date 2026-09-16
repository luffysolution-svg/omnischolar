from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

from omnischolar.version import __version__

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = __version__


class CodexPluginPackageTests(unittest.TestCase):
    def test_release_versions_are_synchronized(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(pyproject["project"]["version"], EXPECTED_VERSION)
        self.assertEqual(__version__, EXPECTED_VERSION)
        for relative in (
            "package.json",
            "plugin.json",
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
            ".cursor-plugin/plugin.json",
        ):
            document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(document["version"], EXPECTED_VERSION, relative)
        server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
        self.assertEqual(server["version"], EXPECTED_VERSION)
        self.assertEqual(server["packages"][0]["version"], EXPECTED_VERSION)

    def test_example_uses_workspace_scoped_dashscope_endpoints(self) -> None:
        document = json.loads(
            (ROOT / "omnischolar.config.example.json").read_text(encoding="utf-8")
        )
        providers = document["media"]["providers"]
        self.assertEqual(
            providers["dashscope"]["baseUrl"],
            "https://your-workspace.cn-beijing.maas.aliyuncs.com/api/v1",
        )
        self.assertEqual(
            providers["qwen-cloud"]["baseUrl"],
            "https://your-workspace.ap-southeast-1.maas.aliyuncs.com/api/v1",
        )
        self.assertEqual(providers["dashscope"]["options"]["workspace"], "your-workspace")
        self.assertEqual(providers["qwen-cloud"]["options"]["workspace"], "your-workspace")

    def test_portable_mcp_uses_pinned_pypi_release(self) -> None:
        document = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        server = document["mcpServers"]["omnischolar"]
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "uvx")
        self.assertEqual(
            server["args"],
            [
                "--from",
                f"luffysolution-omnischolar=={EXPECTED_VERSION}",
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

    def test_pi_bridge_uses_pinned_pypi_release(self) -> None:
        source = (ROOT / "pi-extension/src/index.ts").read_text(encoding="utf-8")
        self.assertIn(f'version: "{EXPECTED_VERSION}"', source)
        self.assertIn(f"luffysolution-omnischolar=={EXPECTED_VERSION}", source)

    def test_default_tool_groups_are_all_enabled(self) -> None:
        document = json.loads(
            (ROOT / "omnischolar.config.example.json").read_text(encoding="utf-8")
        )
        self.assertTrue(all(document["tools"]["groups"].values()))


if __name__ == "__main__":
    unittest.main()
