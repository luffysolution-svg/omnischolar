from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnischolar.hosts.installer import (
    CONTRACTS,
    LATEST_MCP_PROCESS,
    PI_EXTENSION_SOURCE,
    InstallEnvironment,
    manage_host,
    manage_mcp,
    manage_pi_extension,
    manage_skills,
)


class PiInstallerTests(unittest.IsolatedAsyncioTestCase):
    async def test_dry_run_plans_extension_and_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = InstallEnvironment(root / "home", root / "project")
            environment.project.mkdir(parents=True)
            results = await manage_host(
                "pi", "install", scope="project", dry_run=True, environment=environment
            )
        self.assertEqual([result.component for result in results], ["extension", "skills"])
        self.assertTrue(all(result.status == "planned" for result in results))

    async def test_extension_install_uses_pi_and_verifies_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = InstallEnvironment(root / "home", root / "project")
            environment.project.mkdir(parents=True)
            settings = environment.project / ".pi" / "settings.json"

            async def fake_pi(arguments: list[str], *, cwd: Path) -> None:
                self.assertEqual(cwd, environment.project)
                self.assertEqual(
                    arguments,
                    ["install", PI_EXTENSION_SOURCE, "--local", "--approve"],
                )
                settings.parent.mkdir(parents=True)
                settings.write_text(
                    json.dumps({"packages": [PI_EXTENSION_SOURCE]}), encoding="utf-8"
                )

            with patch(
                "omnischolar.hosts.installer._run_pi_command", side_effect=fake_pi
            ):
                result = await manage_pi_extension(
                    "install", scope="project", environment=environment
                )
        self.assertEqual(result.status, "installed")
        self.assertEqual(result.component, "extension")


class WorkBuddyInstallerTests(unittest.IsolatedAsyncioTestCase):
    async def test_workbuddy_template_uses_stdio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = InstallEnvironment(root / "home", root / "project")
            environment.project.mkdir(parents=True)
            result = await manage_mcp(
                "workbuddy",
                "install",
                scope="project",
                dry_run=True,
                environment=environment,
                handshake=False,
            )
        self.assertEqual(result.status, "planned")
        self.assertEqual(Path(result.path or "").name, ".mcp.json")

    def test_latest_mcp_process_is_valid_for_codex_and_stdio_hosts(self) -> None:
        self.assertNotIn("type", LATEST_MCP_PROCESS)
        self.assertEqual(CONTRACTS["codex"].server_value, LATEST_MCP_PROCESS)
        self.assertEqual(CONTRACTS["claude"].server_value.get("type"), "stdio")


class SkillInstallerTests(unittest.TestCase):
    @staticmethod
    def _skill(root: Path, name: str, body: str) -> None:
        directory = root / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Test skill.\n---\n\n{body}\n",
            encoding="utf-8",
        )

    def test_update_removes_retired_managed_skill_after_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = InstallEnvironment(root / "home", root / "project")
            environment.project.mkdir(parents=True)
            first = root / "first"
            second = root / "second"
            self._skill(first, "keep", "first")
            self._skill(first, "retired", "retired")
            self._skill(second, "keep", "second")

            manage_skills(
                "codex", "install", scope="project", environment=environment, source=first
            )
            result = manage_skills(
                "codex", "update", scope="project", environment=environment, source=second
            )

            target = environment.project / ".agents" / "skills"
            self.assertEqual(result.status, "updated")
            self.assertFalse((target / "retired").exists())
            self.assertIn("second", (target / "keep" / "SKILL.md").read_text(encoding="utf-8"))
            self.assertTrue((Path(result.backup or "") / "retired" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
