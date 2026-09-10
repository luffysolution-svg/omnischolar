from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnischolar.hosts.installer import (
    PI_EXTENSION_SOURCE,
    InstallEnvironment,
    manage_host,
    manage_mcp,
    manage_pi_extension,
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


if __name__ == "__main__":
    unittest.main()
