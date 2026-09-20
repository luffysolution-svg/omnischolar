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

    async def test_analysis_removes_input_frontmatter_and_normalises_table_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            assets = root / "assets"
            assets.mkdir()
            (assets / "image-1.png").write_bytes(b"image-1")
            (assets / "image-2.png").write_bytes(b"image-2")
            await service.publish(_paper("PAPER123", "A Paper", pdf), "# A Paper\n\nEvidence", {}, parse_key="a")
            reader = LiteratureReader(service)
            analysis = AnalysisService(service, reader, OutputConfig())

            result = await analysis.execute(
                {
                    "action": "write",
                    "analysisType": "targeted-reading",
                    "key": "PAPER123",
                    "content": (
                        "---\n"
                        "analysisType: targeted-reading\n"
                        "scope: figures\n"
                        "---\n\n"
                        "---\n"
                        "generatedAgain: true\n"
                        "---\n\n"
                        "# Targeted\n\n"
                        "| 预览 | 图表名称、原文位置与分析解读 |\n"
                        "| --- | --- |\n"
                        "| ![[assets/image-1.png]] ![[assets/image-2.png]] | Figure 1 | extra |\n"
                    ),
                    "language": "zh-CN",
                    "overwrite": True,
                }
            )

            text = (root / result["path"]).read_text(encoding="utf-8")
            self.assertEqual(text.count("analysisType:"), 1)
            self.assertNotIn("scope: figures", text)
            self.assertNotIn("generatedAgain: true", text)
            self.assertIn("![[assets/image-1.png]]", text)
            self.assertIn("![[assets/image-2.png]]", text)
            self.assertEqual(text.count("![[assets/"), 2)
            self.assertIn("1. **图表标题**：Figure 1", text)
            self.assertIn("2. **原文位置**：见对应图注/正文", text)
            self.assertIn("3. **作者原文表述**：见论文图注和对应正文段落", text)
            self.assertIn("4. **图表解读**：", text)
            self.assertNotIn("<img ", text)
            self.assertNotIn("|220]]", text)


if __name__ == "__main__":
    unittest.main()
