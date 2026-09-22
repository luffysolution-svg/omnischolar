from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "obsidian-literature-base"
    / "scripts"
    / "build_literature_base.py"
)


def _publication(
    root: Path,
    *,
    tags: list[str],
    key: str = "PAPER123",
    title: str = "A Paper",
    year: str = "2024",
    folder: str = "Smith-2024-A Paper",
) -> Path:
    directory = root / "Papers" / folder
    (directory / "assets").mkdir(parents=True)
    (directory / "source").mkdir()
    (directory / "assets" / f"{key}-image-1.png").write_bytes(b"one")
    (directory / "assets" / f"{key}-image-2.png").write_bytes(b"two")
    (directory / f"{folder}.md").write_text(
        f"""---
recordType: mineru-publication
title: {title}
tags:
  - topic-Solid-state
---
# {title}

![](assets/{key}-image-2.png)
![](assets/{key}-image-1.png)
""",
        encoding="utf-8",
    )
    (directory / "source" / "zotero-reading-record.md").write_text(
        f"---\nrecordType: zotero-reading-record\ntitle: {title}\n---\n",
        encoding="utf-8",
    )
    sidecar = {
        "schemaVersion": 1,
        "publication": {"id": f"zotero:test:{key}:PDF{key}", "namespace": "test"},
        "zotero": {
            "zoteroKey": key,
            "title": title,
            "date": f"{year}-05-01",
            "itemType": "journalArticle",
            "creators": [
                {"creatorType": "author", "firstName": "Ada", "lastName": "Smith"}
            ],
            "doi": f"10.1000/{key.casefold()}",
            "url": "https://example.test/paper",
            "publicationTitle": "Journal of Tests",
            "abstract": "A structured abstract.",
            "tags": [{"tag": tag} for tag in tags],
        },
        "parse": {"key": "parse-1", "parserVersion": "1"},
    }
    (directory / "metadata.json").write_text(
        json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
    )
    return directory


class ObsidianLiteratureBaseTests(unittest.TestCase):
    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )

    def test_prefixed_zotero_topic_and_all_images_are_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = _publication(root, tags=["topic/Solid-state batteries", "review"])
            result = self._run(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["papers"], 1)
            self.assertEqual(summary["topicSources"]["zotero-tag"], 1)

            index = (directory / "literature-index.md").read_text(encoding="utf-8")
            frontmatter = yaml.safe_load(index.split("---", 2)[1])
            self.assertEqual(frontmatter["topics"], ["Solid-state batteries"])
            self.assertEqual(frontmatter["topicSource"], "zotero-tag")
            self.assertEqual(frontmatter["generatedBy"], "obsidian-literature-base")
            self.assertEqual(frontmatter["year"], 2024)
            self.assertEqual(frontmatter["firstAuthor"], "Ada Smith")
            self.assertEqual(frontmatter["imageCount"], 2)
            self.assertEqual(frontmatter["cover"], "[[assets/PAPER123-image-2.png]]")
            self.assertIn("> [!example]- 全部图片（2）", index)
            self.assertIn("![[assets/PAPER123-image-1.png|240]]", index)
            self.assertFalse((directory / "research-state.md").exists())

            base_text = (root / "Literature.base").read_text(encoding="utf-8")
            base = yaml.safe_load(base_text)
            self.assertEqual(
                [view["name"] for view in base["views"]],
                ["文献总表", "原始产物", "按年份", "按作者", "按期刊", "按主题", "按标签"],
            )
            topics_view = next(view for view in base["views"] if view["name"] == "按主题")
            self.assertEqual(topics_view["image"], "note.cover")

    def test_ai_topics_are_used_only_when_prefixed_topics_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = _publication(root, tags=["review"])
            mapping = root / "topics.json"
            mapping.write_text(
                json.dumps({"PAPER123": ["界面化学", "固态电池"]}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = self._run(root, "--ai-topics", str(mapping))

            self.assertEqual(result.returncode, 0, result.stderr)
            index = (directory / "literature-index.md").read_text(encoding="utf-8")
            frontmatter = yaml.safe_load(index.split("---", 2)[1])
            self.assertEqual(frontmatter["topics"], ["界面化学", "固态电池"])
            self.assertEqual(frontmatter["topicSource"], "ai")

    def test_unowned_base_is_not_overwritten_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _publication(root, tags=["topic/Test"])
            (root / "Literature.base").write_text("views: []\n", encoding="utf-8")

            result = self._run(root)

            self.assertEqual(result.returncode, 2)
            self.assertIn("Refusing to overwrite an unowned file", result.stderr)
            self.assertEqual((root / "Literature.base").read_text(encoding="utf-8"), "views: []\n")
            self.assertFalse((root / "Papers" / "Smith-2024-A Paper" / "literature-index.md").exists())

    def test_wiki_hub_shared_topic_pages_and_manual_content_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = _publication(root, tags=["topic/Shared", "topic/Unique"])
            second = _publication(
                root,
                tags=["topic/Shared"],
                key="PAPER456",
                title="Another Paper",
                year="2023",
                folder="Jones-2023-Another Paper",
            )

            result = self._run(root, "--wiki")

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(summary["wiki"]["enabled"])
            self.assertEqual(summary["wiki"]["topicPages"], 1)
            hub = (root / "文献知识库.md").read_text(encoding="utf-8")
            self.assertIn("![[Literature.base#按主题]]", hub)
            self.assertIn("[[Literature Wiki/Topics/Shared.md|Shared]]", hub)

            topic_path = root / "Literature Wiki" / "Topics" / "Shared.md"
            topic = topic_path.read_text(encoding="utf-8")
            self.assertIn("[[Papers/Smith-2024-A Paper/literature-index.md|A Paper]]", topic)
            self.assertIn(
                "[[Papers/Jones-2023-Another Paper/literature-index.md|Another Paper]]",
                topic,
            )
            self.assertFalse((topic_path.parent / "Unique.md").exists())
            first_index = (first / "literature-index.md").read_text(encoding="utf-8")
            second_index = (second / "literature-index.md").read_text(encoding="utf-8")
            self.assertIn("[[Literature Wiki/Topics/Shared.md|Shared]]", first_index)
            self.assertIn("[[Literature Wiki/Topics/Shared.md|Shared]]", second_index)

            topic_path.write_text(
                topic.replace("aliases: []", "aliases:\n- Shared Alias")
                .replace("reviewStatus: draft", "reviewStatus: human-reviewed")
                .replace("_每条判断应链接支持它的文献。_", "- 人工共识，保留此行。"),
                encoding="utf-8",
            )
            stale = topic_path.parent / "Old Topic.md"
            stale.write_text(
                "---\nrecordType: literature-topic\ngeneratedBy: obsidian-literature-base\n---\n",
                encoding="utf-8",
            )

            refreshed = self._run(root, "--wiki")

            self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
            refreshed_summary = json.loads(refreshed.stdout)
            self.assertIn(
                "Literature Wiki/Topics/Old Topic.md",
                refreshed_summary["wiki"]["staleTopicPages"],
            )
            self.assertTrue(stale.is_file())
            refreshed_topic = topic_path.read_text(encoding="utf-8")
            self.assertIn("- 人工共识，保留此行。", refreshed_topic)
            refreshed_properties = yaml.safe_load(refreshed_topic.split("---", 2)[1])
            self.assertEqual(refreshed_properties["aliases"], ["Shared Alias"])
            self.assertEqual(refreshed_properties["reviewStatus"], "human-reviewed")


if __name__ == "__main__":
    unittest.main()
