from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omnischolar.core import OmniScholarError
from omnischolar.services.sync import (
    SyncService,
    metadata_fingerprint,
    paper_stem,
    publication_id,
    stable_hash,
)
from omnischolar.tools.catalogue import (
    _prepare_publication_content,
    _sync_parse_arguments,
)


class PublicationContentTests(unittest.TestCase):
    def test_duplicate_title_is_removed_and_assets_follow_reference_order(self) -> None:
        title = (
            "Unveiling the Synergistic Role of Frustrated Lewis Pairs in "
            "Carbon-Encapsulated Ni/NiOx"
        )
        parsed = (
            "# Unveiling the Synergistic Role ofFrustrated Lewis Pairs in "
            "Carbon-Encapsulated Ni/NiO\n\n"
            "Text.\n\n![](images/b.png)\n\n![](images/a.png)\n"
        )

        markdown, assets = _prepare_publication_content(
            title,
            parsed,
            {
                "images/a.png": b"a",
                "images/b.png": b"b",
                "images/c.jpg": b"c",
            },
        )

        self.assertEqual(markdown.count("\n# "), 0)
        self.assertTrue(markdown.startswith(f"# {title}\n\nText."))
        self.assertIn("![](assets/image-1.png)", markdown)
        self.assertIn("![](assets/image-2.png)", markdown)
        self.assertEqual(list(assets), ["image-1.png", "image-2.png", "image-3.jpg"])
        self.assertEqual(assets["image-1.png"], b"b")
        self.assertEqual(assets["image-2.png"], b"a")

    def test_distinct_leading_heading_is_preserved(self) -> None:
        markdown, assets = _prepare_publication_content(
            "Paper title",
            "# Methods\n\nBody\n\n![](assets/image_hash.jpg)\n",
            {"image_hash.jpg": b"image"},
        )

        self.assertTrue(markdown.startswith("# Paper title\n\n# Methods"))
        self.assertIn("![](assets/image-1.jpg)", markdown)
        self.assertEqual(list(assets), ["image-1.jpg"])

    def test_ambiguous_asset_basenames_are_rejected(self) -> None:
        with self.assertRaisesRegex(OmniScholarError, "ambiguous reference names"):
            _prepare_publication_content(
                "Title",
                "![](one/same.png)",
                {"one/same.png": b"1", "two/same.png": b"2"},
            )

    def test_custom_asset_template_preserves_original_stem_and_extension(self) -> None:
        markdown, assets = _prepare_publication_content(
            "Title",
            "![](images/figure-b.PNG)\n![](images/figure-a.jpg)\n",
            {"images/figure-a.jpg": b"a", "images/figure-b.PNG": b"b"},
            asset_filename_template="figure-{index}-{original}{extension}",
        )

        self.assertIn("![](assets/figure-1-figure-b.png)", markdown)
        self.assertIn("![](assets/figure-2-figure-a.jpg)", markdown)
        self.assertEqual(list(assets), ["figure-1-figure-b.png", "figure-2-figure-a.jpg"])


class PaperStemTests(unittest.TestCase):
    def test_long_stem_is_bounded_and_deterministic(self) -> None:
        paper = {
            "creators": [
                {"creatorType": "author", "lastName": "Yang"},
            ],
            "year": "2024",
            "title": "A very long paper title " * 30,
        }

        first = paper_stem(paper)
        second = paper_stem(paper)

        self.assertEqual(first, second)
        self.assertLessEqual(len(first.encode()), 72)
        self.assertRegex(first, r"-[0-9a-f]{8}$")

    def test_custom_template_and_separator_are_supported(self) -> None:
        paper = {
            "creators": [{"creatorType": "author", "lastName": "Yang"}],
            "year": "2024",
            "title": "A paper title",
        }

        self.assertEqual(
            paper_stem(
                paper,
                template="{year}{separator}{author}{separator}{title}",
                separator="+",
            ),
            "2024+Yang+A paper title",
        )


class SyncActionTests(unittest.TestCase):
    def test_repair_and_restore_reuse_cache_while_forcing_publication(self) -> None:
        for action in ("repair", "restore", "apply"):
            arguments = _sync_parse_arguments({"force": action == "apply"}, action)
            self.assertFalse(arguments["_parseForce"], action)
            self.assertTrue(arguments["_publishForce"], action)

    def test_reparse_forces_parser_and_publication(self) -> None:
        arguments = _sync_parse_arguments({}, "reparse")
        self.assertTrue(arguments["_parseForce"])
        self.assertTrue(arguments["_publishForce"])


class SyncPlanTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_parse_key_is_reported_when_no_candidate_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            paper = {
                "zoteroKey": "PAPER",
                "zoteroVersion": 1,
                "title": "Test paper",
                "creators": [],
                "selectedPdf": {"key": "PDF", "md5": "abc", "mtime": 1},
            }
            identifier = publication_id(paper, service.namespace)
            relative = "Literatures/Test-paper"
            directory = root / relative
            directory.mkdir(parents=True)
            content = b"# Test paper\n"
            (directory / "paper.md").write_bytes(content)
            manifest = service._empty_manifest()
            manifest["entries"][identifier] = {
                "publicationId": identifier,
                "relativePath": relative,
                "metadataFingerprint": metadata_fingerprint(paper),
                "parseKey": "cached-parse-key",
                "renderKey": "render-key",
                "baseline": {"paper.md": stable_hash(content)},
                "excluded": False,
                "updatedAt": 1,
            }
            service.state_root.mkdir(parents=True)
            service.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = await service.plan(paper)

        self.assertEqual(plan.status, "up_to_date")
        self.assertEqual(plan.parse_key, "cached-parse-key")


if __name__ == "__main__":
    unittest.main()
