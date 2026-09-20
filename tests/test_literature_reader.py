from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omnischolar.services.reader import LiteratureReader
from omnischolar.services.sync import SyncService, stable_hash


def _publication(service: SyncService, root: Path, key: str, title: str, body: str) -> None:
    relative = f"Literatures/{title.replace(' ', '-')}"
    directory = root / relative
    directory.mkdir(parents=True)
    markdown = f"# {title}\n\n{body}\n"
    markdown_path = directory / "paper.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "zotero": {
                    "zoteroKey": key,
                    "title": title,
                    "abstract": f"Abstract for {title}",
                    "doi": f"10.1000/{key.lower()}",
                }
            }
        ),
        encoding="utf-8",
    )
    identifier = f"zotero:{service.namespace}:{key}:PDF12345"
    manifest = (
        json.loads(service.manifest_path.read_text(encoding="utf-8"))
        if service.manifest_path.exists()
        else service._empty_manifest()
    )
    manifest["entries"][identifier] = {
        "publicationId": identifier,
        "relativePath": relative,
        "metadataFingerprint": "fingerprint",
        "parseKey": "parse-key",
        "renderKey": "render-key",
        "baseline": {"paper.md": stable_hash(markdown.encode("utf-8"))},
        "excluded": False,
        "updatedAt": 1,
    }
    service.state_root.mkdir(parents=True, exist_ok=True)
    service.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


class LiteratureReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_read_is_bounded_and_cursored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            body = "## Results\n\n" + ("A paragraph with evidence.\n\n" * 300)
            _publication(service, root, "PAPER123", "Paper One", body)

            result = await LiteratureReader(service).read(
                {"key": "PAPER123", "mode": "full", "maxChars": 800}
            )

        self.assertTrue(result["hasMore"])
        self.assertIsNotNone(result["nextCursor"])
        self.assertLessEqual(len(result["text"]), 800)

    async def test_mode_specific_extraction_and_multi_document_packets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            body = (
                "## Results\n\n"
                "![](assets/image-1.png)\n\nFigure 1: Reaction pathway.\n\n"
                "| condition | yield |\n| --- | --- |\n| A | 90% |\n\n"
                "$$E = mc^2$$\n\n"
                "The catalyst improves selectivity.\n"
            )
            _publication(service, root, "PAPER123", "Paper One", body)
            _publication(service, root, "PAPER124", "Paper Two", body)
            reader = LiteratureReader(service)

            figures = await reader.read({"key": "PAPER123", "mode": "figures"})
            formulas = await reader.read({"key": "PAPER123", "mode": "formulas"})
            paragraphs = await reader.read(
                {"key": "PAPER123", "mode": "paragraphs", "query": "selectivity"}
            )
            comparison = await reader.read(
                {"keys": ["PAPER123", "PAPER124"], "mode": "compare"}
            )
            review = await reader.read(
                {"keys": ["PAPER123", "PAPER124"], "mode": "review", "query": "catalyst selectivity"}
            )

        self.assertEqual(figures["items"][0]["caption"], "Figure 1: Reaction pathway.")
        self.assertEqual(figures["items"][1]["kind"], "table")
        self.assertEqual(formulas["items"][0]["formula"], "$$E = mc^2$$")
        self.assertIn("selectivity", paragraphs["items"][0]["text"])
        self.assertEqual(len(comparison["documents"]), 2)
        self.assertTrue(all(document["evidence"] for document in review["documents"]))


if __name__ == "__main__":
    unittest.main()
