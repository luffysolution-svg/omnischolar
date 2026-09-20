from __future__ import annotations

import unittest
from typing import Any

from omnischolar.core import OmniScholarError
from omnischolar.services.zotero import ZoteroService


class FakeZoteroTransport:
    async def json(self, method: str, url: str, *, params: dict[str, Any] | None = None, **_kwargs: Any) -> Any:
        del method
        if url.endswith("/items/PARENT01"):
            return {
                "key": "PARENT01",
                "version": 1,
                "data": {"itemType": "journalArticle", "title": "A paper", "creators": []},
            }
        if url.endswith("/items/PARENT01/children"):
            return [
                {
                    "key": "ATTACH01",
                    "version": 2,
                    "data": {
                        "itemType": "attachment",
                        "contentType": "application/pdf",
                        "filename": "paper.pdf",
                    },
                },
                {
                    "key": "ANNO0002",
                    "version": 4,
                    "data": {"itemType": "annotation", "parentItem": "OTHER01"},
                },
            ]
        if (
            url.endswith("/items")
            and params
            and params.get("parentItem") == "ATTACH01"
            and params.get("itemType") == "annotation"
        ):
            return [
                {
                    "key": "ANNO0001",
                    "version": 3,
                    "data": {
                        "itemType": "annotation",
                        "parentItem": "ATTACH01",
                        "annotationType": "highlight",
                        "annotationColor": "#ffd400",
                        "annotationText": "Selected evidence",
                        "annotationComment": "Important",
                        "annotationPageLabel": "2",
                        "tags": [{"tag": "result"}],
                    },
                }
            ]
        if url.endswith("/items/ATTACH01/fulltext"):
            raise OmniScholarError("not_found", "missing", http_status=404)
        raise AssertionError(f"Unexpected Zotero JSON request: {url} {params}")

    async def text(self, method: str, url: str, **_kwargs: Any) -> str:
        del method
        if url.endswith("/items/ATTACH01/file/view/url"):
            return "file:///C:/missing-paper.pdf"
        raise AssertionError(f"Unexpected Zotero text request: {url}")


class ZoteroAnnotationTests(unittest.IsolatedAsyncioTestCase):
    async def test_annotations_are_loaded_by_parent_item_query(self) -> None:
        service = ZoteroService(FakeZoteroTransport())

        paper = await service.item("PARENT01", aggregate=True)

        self.assertEqual(len(paper["annotations"]), 1)
        self.assertEqual(paper["annotations"][0]["data"]["annotationColor"], "#ffd400")
        self.assertEqual(paper["annotations"][0]["data"]["annotationPageLabel"], "2")


if __name__ == "__main__":
    unittest.main()
