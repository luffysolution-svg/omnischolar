from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omnischolar.services.reader import LiteratureReader
from omnischolar.services.retrieval import LiteratureRetriever
from omnischolar.services.reading_context import ReadingContextStore
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


class LiteratureRetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_focused_search_is_bounded_and_reuses_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            _publication(
                service,
                root,
                "PAPER123",
                "Catalyst Study",
                "## Results\n\nThe catalyst improves selectivity and yield.\n\n"
                + ("Unrelated background text. " * 200),
            )
            _publication(
                service,
                root,
                "PAPER124",
                "Control Study",
                "## Methods\n\nThe control has no catalyst evidence.\n",
            )
            reader = LiteratureReader(service)
            retriever = LiteratureRetriever(reader)

            first = await retriever.search(
                {"query": "catalyst selectivity", "topK": 5, "maxChars": 500}
            )
            second = await retriever.search(
                {"query": "yield", "keys": ["PAPER123"], "topK": 3, "maxChars": 500}
            )
            empty = await retriever.search(
                {"query": "zzzz-no-such-scientific-term", "keys": ["PAPER123"], "topK": 3}
            )

        self.assertEqual(first["strategy"], "hybrid-bm25-tfidf")
        self.assertEqual(first["cacheHit"], False)
        self.assertEqual(second["cacheHit"], True)
        self.assertEqual(first["results"][0]["zoteroKey"], "PAPER123")
        self.assertLessEqual(len(first["results"][0]["excerpt"]), 500)
        self.assertIn("locator", first["results"][0])
        self.assertEqual(empty["results"], [])

    async def test_locator_and_context_cache_remain_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SyncService(root, namespace="test-vault")
            _publication(
                service,
                root,
                "PAPER123",
                "Catalyst Study",
                "## Results\n\n"
                + ("The catalyst improves selectivity and yield across repeated measurements. " * 12)
                + "\n\n"
                + ("The catalyst remains stable after cycling and retains its active sites. " * 12)
                + "\n",
            )
            context = ReadingContextStore(root, max_chars=900)
            reader = LiteratureReader(service, context_store=context)
            located = await reader.locate(
                {"key": "PAPER123", "query": "catalyst", "maxItems": 10}
            )
            await context.execute(
                {
                    "action": "add",
                    "contextId": "ctx-test",
                    "items": located["items"],
                }
            )
            cached = await context.execute(
                {"action": "get", "contextId": "ctx-test", "maxChars": 500}
            )

        self.assertEqual(len(located["items"]), 2)
        self.assertTrue(all(item["locator"].startswith("paper.md#L") for item in located["items"]))
        self.assertTrue(cached["truncated"])
        self.assertLessEqual(cached["returnedChars"], 500)


if __name__ == "__main__":
    unittest.main()
