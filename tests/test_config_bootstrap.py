from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omnischolar.config import ensure_user_config, load_config, user_config_file


class ConfigBootstrapTests(unittest.TestCase):
    def test_default_path_uses_one_level_app_directory(self) -> None:
        from platformdirs import user_config_path

        self.assertEqual(
            user_config_file(),
            user_config_path("omnischolar", appauthor=False) / "omnischolar.config.json",
        )

    def test_creates_one_user_config_with_all_tool_groups_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            user_directory = Path(temporary) / "config" / "omnischolar"
            path = ensure_user_config(
                cwd=Path(temporary) / "project",
                user_directory=user_directory,
            )

            self.assertEqual(path, user_directory / "omnischolar.config.json")
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(all(document["tools"]["groups"].values()))
            self.assertEqual(load_config(user_directory=user_directory).source.kind, "user")

    def test_does_not_replace_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            project_config = project / "omnischolar.config.json"
            project_config.write_text('{"schemaVersion": 1}\n', encoding="utf-8")
            user_directory = root / "user"

            path = ensure_user_config(cwd=project, user_directory=user_directory)

            self.assertEqual(path, project_config)
            self.assertFalse((user_directory / "omnischolar.config.json").exists())


if __name__ == "__main__":
    unittest.main()
