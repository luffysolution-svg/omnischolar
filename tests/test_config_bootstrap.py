from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omnischolar.config import (
    OmniScholarConfig,
    ensure_user_config,
    load_config,
    resolve_credential,
    user_config_file,
)


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
            self.assertIn("apiKey", document["mineru"])
            self.assertIn("apiKey", document["ai4scholar"])
            self.assertIn("apiKey", document["data"]["materialsProject"])
            self.assertIn("apiKey", document["research"]["providers"]["semantic-scholar"])
            self.assertIn("vertex", document["media"]["providers"])
            self.assertIn("apiKey", document["media"]["providers"]["vertex"])
            self.assertIn("project", document["media"]["providers"]["vertex"])
            self.assertIn("location", document["media"]["providers"]["vertex"])
            self.assertEqual(document["output"]["literatureDirectory"], "Literatures")
            self.assertEqual(document["output"]["filenameSeparator"], "-")
            self.assertIn("{title}", document["output"]["folderNameTemplate"])
            self.assertIn("{title}", document["output"]["filenameTemplate"])
            self.assertIn("{extension}", document["output"]["assetFilenameTemplate"])
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

    def test_inline_api_key_takes_precedence_over_environment(self) -> None:
        credential = resolve_credential(
            "mineru",
            api_key="inline-key",
            api_key_env="MINERU_TEST_KEY",
            environ={"MINERU_TEST_KEY": "environment-key"},
        )

        self.assertTrue(credential.configured)
        self.assertEqual(credential.source, "config.apiKey")
        self.assertEqual(credential.reveal(), "inline-key")

    def test_underscore_is_a_valid_shared_separator(self) -> None:
        config = OmniScholarConfig.model_validate(
            {
                "output": {
                    "filenameSeparator": "_",
                    "folderNameTemplate": "{author}{separator}{year}",
                    "filenameTemplate": "{title}",
                    "assetFilenameTemplate": "figure{separator}{index}{extension}",
                }
            }
        )

        self.assertEqual(config.output.filename_separator, "_")


if __name__ == "__main__":
    unittest.main()
