from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omnischolar.config import OutputConfig
from omnischolar.services.analysis import AnalysisService
from omnischolar.services.reader import LiteratureReader
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


class ZoteroReadingRecordTests(unittest.TestCase):
    def test_notes_and_annotations_are_separate_and_styled(self) -> None:
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


class LiteratureAnalysisTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_copies_pdf_and_writes_reading_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "input.pdf"
            pdf.write_bytes(b"%PDF-test")
            service = SyncService(root, namespace="test-vault")
            paper = _paper("PAPER123", "A Paper", pdf)

            result = await service.publish(
                paper,
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

    async def test_single_and_multi_analysis_use_configured_two_branch_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            pdf_a = root / "a.pdf"
            pdf_b = root / "b.pdf"
            pdf_a.write_bytes(b"%PDF-a")
            pdf_b.write_bytes(b"%PDF-b")
            await service.publish(_paper("PAPER123", "Paper A", pdf_a), "# Paper A\n\nEvidence A", {}, parse_key="a")
            await service.publish(_paper("PAPER124", "Paper B", pdf_b), "# Paper B\n\nEvidence B", {}, parse_key="b")
            reader = LiteratureReader(service)
            config = OutputConfig()
            analysis = AnalysisService(service, reader, config)

            single = await analysis.execute(
                {
                    "action": "write",
                    "analysisType": "full-read",
                    "key": "PAPER123",
                    "content": "# SCI Full Read\n\n## One-sentence summary\n\nA.",
                    "language": "en",
                    "overwrite": True,
                }
            )
            compare = await analysis.execute(
                {
                    "action": "write",
                    "analysisType": "compare",
                    "keys": ["PAPER123", "PAPER124"],
                    "topic": "method comparison",
                    "content": "# Comparison\n\n| Dimension | Paper A | Paper B |\n| --- | --- | --- |\n| Method | A | B |",
                    "language": "en",
                    "overwrite": True,
                }
            )

            self.assertTrue(single["path"].startswith("Analysis/Single/"))
            self.assertTrue(single["path"].endswith("/full-read.md"))
            self.assertTrue(compare["path"].startswith("Analysis/Multi/"))
            self.assertTrue(compare["path"].endswith("-compare.md"))
            single_text = (root / single["path"]).read_text(encoding="utf-8")
            compare_text = (root / compare["path"]).read_text(encoding="utf-8")
            self.assertIn("sourceFingerprint:", single_text)
            self.assertIn("MinerU 原文", single_text)
            self.assertIn("[[", single_text)
            self.assertIn("| Dimension |", compare_text)


if __name__ == "__main__":
    unittest.main()
