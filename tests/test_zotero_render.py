from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from omnischolar.services.sync import SyncService
from omnischolar.services.zotero_render import render_zotero_reading_record


def _paper(key: str, title: str, pdf: Path) -> dict[str, object]:
    return {
        "zoteroKey": key,
        "zoteroVersion": 1,
        "title": title,
        "date": "2024",
        "itemType": "journalArticle",
        "creators": [
            {"creatorType": "author", "firstName": "Ada", "lastName": "Smith"}
        ],
        "doi": f"10.1000/{key.lower()}",
        "url": "https://example.test/paper",
        "publicationTitle": "Journal of Tests",
        "abstract": "A structured abstract.",
        "tags": [
            {"tag": "solid state"},
            {"tag": "battery:interface"},
            {"tag": "#层级/标签"},
            {"tag": "2026"},
        ],
        "collections": ["COLLECTION1"],
        "notes": [{"key": "NOTE1234", "version": 1, "note": "Researcher note", "tags": [{"tag": "idea"}]}],
        "annotations": [
            {
                "key": "ANNO1234",
                "data": {
                    "annotationType": "highlight",
                    "annotationColor": "#ffd400",
                    "annotationPageLabel": "3",
                    "annotationText": "Important result",
                    "annotationComment": "Check the control group.",
                    "tags": [{"tag": "important"}],
                },
            }
        ],
        "selectedPdf": {"key": f"PDF{key[-4:]}", "localPath": str(pdf), "md5": "abc", "mtime": 1},
    }


class ZoteroReadingRecordTests(unittest.IsolatedAsyncioTestCase):
    async def test_notes_and_annotations_are_separate_and_styled(self) -> None:
        result = render_zotero_reading_record(
            _paper("PAPER123", "A Paper", Path("paper.pdf")),
            pdf_filename="paper.pdf",
        )

        self.assertIn("## Zotero 笔记", result)
        self.assertIn("## PDF 批注", result)
        self.assertIn("![[paper.pdf]]", result)
        self.assertIn("zotero-yellow", result)
        self.assertIn("Page 3", result)
        self.assertIn("#important", result)
        self.assertIn("Check the control group", result)

        frontmatter = yaml.safe_load(result.split("---", 2)[1])
        self.assertEqual(frontmatter["recordType"], "zotero-reading-record")
        self.assertEqual(frontmatter["title"], "A Paper")
        self.assertEqual(frontmatter["itemType"], "journalArticle")
        self.assertEqual(frontmatter["creators"], ["Ada Smith"])
        self.assertEqual(frontmatter["zoteroKey"], "PAPER123")
        self.assertEqual(frontmatter["DOI"], "10.1000/paper123")
        self.assertEqual(frontmatter["URL"], "https://example.test/paper")
        self.assertEqual(frontmatter["publicationTitle"], "Journal of Tests")
        self.assertEqual(
            frontmatter["tags"],
            ["solid-state", "battery-interface", "层级/标签", "tag-2026"],
        )
        self.assertEqual(frontmatter["abstract"], "A structured abstract.")
        self.assertEqual(frontmatter["collections"], ["COLLECTION1"])
        self.assertEqual(
            frontmatter["zoteroLink"], "zotero://select/library/items/PAPER123"
        )
        self.assertEqual(frontmatter["sourceKinds"], ["zotero-note", "pdf-annotation"])

    async def test_publish_copies_pdf_and_writes_reading_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "input.pdf"
            pdf.write_bytes(b"%PDF-test")
            service = SyncService(root, namespace="test-vault")

            result = await service.publish(
                _paper("PAPER123", "A Paper", pdf),
                "# A Paper\n\n## Results\n\nEvidence.",
                {},
                parse_key="parse-1",
            )

            directory = Path(result["directory"])
            self.assertEqual((directory / "source" / "paper.pdf").read_bytes(), b"%PDF-test")
            record = directory / "source" / "zotero-reading-record.md"
            self.assertTrue(record.is_file())
            self.assertIn("## Zotero 笔记", record.read_text(encoding="utf-8"))
            self.assertIn("## PDF 批注", record.read_text(encoding="utf-8"))
if __name__ == "__main__":
    unittest.main()
