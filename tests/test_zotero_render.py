from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omnischolar.services.sync import SyncService
from omnischolar.services.zotero_render import render_zotero_reading_record


def _paper(key: str, title: str, pdf: Path) -> dict[str, object]:
    return {
        "zoteroKey": key,
        "zoteroVersion": 1,
        "title": title,
        "date": "2024",
        "creators": [{"creatorType": "author", "lastName": "Smith"}],
        "doi": f"10.1000/{key.lower()}",
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
