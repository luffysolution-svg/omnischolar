from __future__ import annotations

import tempfile
import unittest
import re
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
    @staticmethod
    def _unescaped_pipe_count(line: str) -> int:
        return len(re.findall(r"(?<!\\)\|", line))

    @staticmethod
    def _figure_table_lines(markdown: str) -> list[str]:
        return [line for line in markdown.splitlines() if line.lstrip().startswith("|")]

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
            review = await analysis.execute(
                {
                    "action": "write",
                    "analysisType": "review",
                    "keys": ["PAPER123", "PAPER124"],
                    "topic": "method review",
                    "content": "# Review\n\nEvidence.",
                    "language": "en",
                    "overwrite": True,
                }
            )

            self.assertTrue(single["path"].startswith("Analysis/Single/"))
            self.assertTrue(single["path"].endswith("/full-read.md"))
            self.assertTrue(compare["path"].startswith("Analysis/Multi/"))
            self.assertTrue(compare["path"].endswith("-compare.md"))
            self.assertTrue(review["path"].startswith("Analysis/Multi/"))
            self.assertTrue(review["path"].endswith("-review.md"))
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

    async def test_real_targeted_rows_preserve_complete_fields_and_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            assets = root / "Literatures" / "Yang-2024-Unveiling the Synergistic Role of Frustrated Lewis Pa-f2b8695f" / "assets"
            assets.mkdir(parents=True)
            for name in ("image-12.jpg", "image-21.jpg", "image-24.jpg", "image-26.jpg"):
                (assets / name).write_bytes(b"image")
            analysis = AnalysisService(service, LiteratureReader(service), OutputConfig())
            source = (
                "| 预览 | 图表名称、原文位置与分析解读 |\n"
                "| --- | --- |\n"
                "| ![[Literatures/Yang-2024-Unveiling the Synergistic Role of Frustrated Lewis Pa-f2b8695f/assets/image-26.jpg|158]] | "
                "1. **图表标题**：1. 图6：能带对齐和 FLP/光热反应机制。 "
                "2. 原文位置：§2.5，Fig.6；Yang…md#L137-L137。 "
                "3. 作者原文表述：FLP 位点促进 H–OH 解离和 H2 生成，非辐射复合带来光热效应。 "
                "4. 图表解读：用户保留的完整机制解释。<br><br>"
                "2. **原文位置**：§2.5<br><br>"
                "3. **作者原文表述**：见论文图注和对应正文段落；MinerU 未抽取可靠逐字表述。<br><br>"
                "4. **图表解读**：用户保留的完整机制解释。 |\n"
            )

            normalized = analysis._normalise_table_image_embeds(
                source,
                "Analysis/Single/Yang/targeted-reading.md",
            )
            normalized_again = analysis._normalise_table_image_embeds(
                normalized,
                "Analysis/Single/Yang/targeted-reading.md",
            )

            self.assertEqual(normalized, normalized_again)
            self.assertIn("![[Literatures/Yang-2024-Unveiling the Synergistic Role of Frustrated Lewis Pa-f2b8695f/assets/image-26.jpg]]", normalized)
            self.assertNotIn("|158]]", normalized)
            self.assertIn("图6：能带对齐和 FLP/光热反应机制", normalized)
            self.assertIn("FLP 位点促进 H–OH 解离和 H2 生成", normalized)
            self.assertIn("用户保留的完整机制解释", normalized)
            self.assertNotIn("MinerU 未抽取可靠逐字表述", normalized)
            self.assertEqual(normalized.count("**图表标题**"), 1)
            self.assertEqual(normalized.count("**原文位置**"), 1)
            self.assertEqual(normalized.count("**作者原文表述**"), 1)
            self.assertEqual(normalized.count("**图表解读**"), 1)
            for line in self._figure_table_lines(normalized):
                self.assertEqual(self._unescaped_pipe_count(line), 3, line)

    async def test_chinese_and_english_titles_and_width_aliases_are_normalised(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            assets = root / "assets"
            assets.mkdir()
            (assets / "image-18.jpg").write_bytes(b"image")
            (assets / "image-21.jpg").write_bytes(b"image")
            analysis = AnalysisService(service, LiteratureReader(service), OutputConfig())
            source = (
                "| 预览 | 图表名称、原文位置与分析解读 |\n"
                "| --- | --- |\n"
                "| ![[assets/image-18.jpg|158]] | 图 6 |\n"
                "| ![[assets/image-21.jpg|260]] | Figure 6. |\n"
            )

            normalized = analysis._normalise_table_image_embeds(
                source,
                "Analysis/Single/Paper/targeted-reading.md",
            )

            self.assertIn("1. **图表标题**：图 6", normalized)
            self.assertIn("1. **图表标题**：Figure 6", normalized)
            self.assertNotIn("|158]]", normalized)
            self.assertNotIn("|260]]", normalized)
            for line in self._figure_table_lines(normalized):
                self.assertEqual(self._unescaped_pipe_count(line), 3, line)

    async def test_multiple_subfigures_get_separate_two_column_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            assets = root / "assets"
            assets.mkdir()
            (assets / "image-a.jpg").write_bytes(b"image")
            (assets / "image-b.jpg").write_bytes(b"image")
            analysis = AnalysisService(service, LiteratureReader(service), OutputConfig())
            source = (
                "| 预览 | 图表名称、原文位置与分析解读 |\n"
                "| --- | --- |\n"
                "| ![[assets/image-a.jpg|158]] ![[assets/image-b.jpg|260]] | Figure 3 | extra column text |\n"
            )

            normalized = analysis._normalise_table_image_embeds(
                source,
                "Analysis/Single/Paper/targeted-reading.md",
            )
            rows = [line for line in self._figure_table_lines(normalized) if "![[assets/" in line]

            self.assertEqual(len(rows), 2)
            self.assertTrue(any("image-a.jpg]]" in line for line in rows))
            self.assertTrue(any("image-b.jpg]]" in line for line in rows))
            self.assertTrue(all("\\| extra column text" in line for line in rows))
            self.assertTrue(all(self._unescaped_pipe_count(line) == 3 for line in rows))

    async def test_input_sources_are_not_duplicated_when_analysis_is_written_again(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            await service.publish(_paper("PAPER123", "A Paper", pdf), "# A Paper", {}, parse_key="a")
            analysis = AnalysisService(service, LiteratureReader(service), OutputConfig())
            content = (
                "# Targeted\n\n"
                "## Zotero 阅读记录\n\n"
                "- MinerU 原文：[[old-paper.md|打开解析文档]]\n"
                "- PDF：[[old-paper.pdf|打开或预览 PDF]]\n\n"
                "## Figures\n\n正文。"
            )

            result = await analysis.execute(
                {
                    "action": "write",
                    "analysisType": "targeted-reading",
                    "key": "PAPER123",
                    "content": content,
                    "language": "zh-CN",
                    "overwrite": True,
                }
            )
            written = (root / result["path"]).read_text(encoding="utf-8")

            self.assertEqual(written.count("## Sources"), 1)
            self.assertNotIn("## Zotero 阅读记录", written)
            self.assertNotIn("old-paper.md", written)
            self.assertEqual(written.count("MinerU 原文"), 1)


if __name__ == "__main__":
    unittest.main()
