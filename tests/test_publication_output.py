from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from omnischolar.config import OmniScholarConfig
from omnischolar.core import OmniScholarError, ToolExecutionContext
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
    parse_tool,
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
            asset_filename_template="figure{separator}{index}{separator}{original}{extension}",
            asset_filename_separator="+",
        )

        self.assertIn("![](assets/figure+1+figure-b.png)", markdown)
        self.assertIn("![](assets/figure+2+figure-a.jpg)", markdown)
        self.assertEqual(list(assets), ["figure+1+figure-b.png", "figure+2+figure-a.jpg"])


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

    def test_folder_template_is_separate_from_file_template(self) -> None:
        paper = {
            "creators": [{"creatorType": "author", "lastName": "Yang"}],
            "year": "2024",
            "title": "A paper title",
        }
        service = SyncService(
            Path("."),
            literature_directory="Papers",
            folder_name_template="{author}{separator}{year}",
            filename_template="{title}",
            filename_separator="_",
        )

        self.assertEqual(service._publication_relative_path(paper), "Papers/Yang_2024")


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

    async def test_republish_removes_obsolete_managed_assets_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            paper = {
                "zoteroKey": "PAPER123",
                "zoteroVersion": 1,
                "title": "Test paper",
                "creators": [],
                "selectedPdf": {"key": "PDF00001", "localPath": str(pdf)},
            }
            service = SyncService(root, namespace="test-vault")
            first = await service.publish(
                paper,
                "# Test paper\n\n![](assets/image-1.png)\n",
                {"image-1.png": b"old"},
                parse_key="parse-1",
            )
            directory = Path(first["directory"])
            (directory / "personal-note.md").write_text("keep", encoding="utf-8")

            await service.publish(
                paper,
                "# Test paper\n\n![](assets/image-2.png)\n",
                {"image-2.png": b"new"},
                parse_key="parse-2",
            )

            self.assertFalse((directory / "assets" / "image-1.png").exists())
            self.assertEqual((directory / "assets" / "image-2.png").read_bytes(), b"new")
            self.assertEqual((directory / "personal-note.md").read_text(encoding="utf-8"), "keep")

    async def test_distinct_publications_with_same_stem_do_not_share_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            base = {
                "zoteroVersion": 1,
                "title": "Same title",
                "date": "2026",
                "creators": [{"creatorType": "author", "lastName": "Smith"}],
            }
            service = SyncService(root, namespace="test-vault")
            first = await service.publish(
                {
                    **base,
                    "zoteroKey": "PAPER001",
                    "selectedPdf": {"key": "PDF00001", "localPath": str(pdf)},
                },
                "# First\n",
                {},
                parse_key="parse-1",
            )
            second = await service.publish(
                {
                    **base,
                    "zoteroKey": "PAPER002",
                    "selectedPdf": {"key": "PDF00002", "localPath": str(pdf)},
                },
                "# Second\n",
                {},
                parse_key="parse-2",
            )

            self.assertNotEqual(first["directory"], second["directory"])
            self.assertTrue(Path(first["markdownPath"]).read_text().startswith("# First"))
            self.assertTrue(Path(second["markdownPath"]).read_text().startswith("# Second"))


class MultiPdfSelectionTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _app(paper: dict[str, object]) -> tuple[object, object, object]:
        class Zotero:
            async def item(self, *_args, **_kwargs):
                return paper

        class Sync:
            def __init__(self) -> None:
                self.published: list[str] = []

            async def publish(self, selected_paper, *_args, **_kwargs):
                key = selected_paper["selectedPdf"]["key"]
                self.published.append(key)
                return {"attachmentKey": key}

        class MinerU:
            def __init__(self) -> None:
                self.parsed: list[str] = []

            async def parse_pdf(self, path, *_args, **_kwargs):
                self.parsed.append(path.name)
                return SimpleNamespace(
                    markdown="# Parsed\n",
                    assets={},
                    parse_key=f"parse-{path.stem}",
                    parser_version="test",
                    summary=lambda: {"source": path.name},
                )

        mineru = MinerU()
        sync = Sync()
        services = SimpleNamespace(zotero=Zotero(), sync=sync, mineru=mineru)
        app = SimpleNamespace(
            loaded=SimpleNamespace(config=OmniScholarConfig()),
            require_services=lambda: services,
        )
        return app, mineru, sync

    async def test_multiple_pdfs_require_confirmation_before_parse(self) -> None:
        paper = {
            "title": "Paper",
            "attachments": [
                {
                    "key": "PDF00001",
                    "contentType": "application/pdf",
                    "filename": "main.pdf",
                    "localPath": "main.pdf",
                },
                {
                    "key": "PDF00002",
                    "contentType": "application/pdf",
                    "filename": "supplement.pdf",
                    "localPath": "supplement.pdf",
                },
            ],
            "selectedPdf": {"key": "PDF00001", "localPath": "main.pdf"},
        }
        app, mineru, sync = self._app(paper)

        with self.assertRaises(OmniScholarError) as raised:
            await parse_tool(
                {"key": "PAPER123"}, ToolExecutionContext(config_source="test"), app
            )

        self.assertEqual(raised.exception.code, "attachment_selection_required")
        self.assertEqual(len(raised.exception.details["attachments"]), 2)
        self.assertEqual(mineru.parsed, [])
        self.assertEqual(sync.published, [])

    async def test_explicit_attachment_is_parsed_after_confirmation(self) -> None:
        paper = {
            "title": "Paper",
            "attachments": [
                {
                    "key": "PDF00002",
                    "contentType": "application/pdf",
                    "filename": "supplement.pdf",
                    "localPath": "supplement.pdf",
                    "selected": True,
                }
            ],
            "selectedPdf": {
                "key": "PDF00002",
                "contentType": "application/pdf",
                "filename": "supplement.pdf",
                "localPath": "supplement.pdf",
            },
        }
        app, mineru, sync = self._app(paper)

        result = await parse_tool(
            {"key": "PAPER123", "attachmentKey": "PDF00002"},
            ToolExecutionContext(config_source="test"),
            app,
        )

        self.assertEqual(result["source"], "supplement.pdf")
        self.assertEqual(mineru.parsed, ["supplement.pdf"])
        self.assertEqual(sync.published, ["PDF00002"])


if __name__ == "__main__":
    unittest.main()
