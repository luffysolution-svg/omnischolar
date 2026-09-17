from __future__ import annotations

import base64
import unittest

from omnischolar.services.artifacts import _extract


class MediaArtifactTests(unittest.TestCase):
    def test_extracts_gemini_interactions_image_blocks(self) -> None:
        encoded = base64.b64encode(b"fake-image-bytes").decode()
        candidates, _ = _extract(
            {"steps": [{"type": "model_output", "content": [{"type": "image", "data": encoded}]}]},
            1024,
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].content, b"fake-image-bytes")

    def test_extracts_vertex_prediction_bytes(self) -> None:
        encoded = base64.b64encode(b"fake-image-bytes").decode()
        candidates, _ = _extract(
            {"predictions": [{"bytesBase64Encoded": encoded, "mimeType": "image/png"}]},
            1024,
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].content, b"fake-image-bytes")

    def test_extracts_atlas_outputs(self) -> None:
        encoded = base64.b64encode(b"fake-image-bytes").decode()
        candidates, _ = _extract(
            {"data": {"status": "completed", "outputs": [f"data:image/png;base64,{encoded}"]}},
            1024,
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].content, b"fake-image-bytes")


if __name__ == "__main__":
    unittest.main()
