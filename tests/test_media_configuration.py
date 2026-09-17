from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omnischolar.services.media import MediaProviderSettings, MediaService


class MediaConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_enabled_provider_without_key_is_not_reported_as_usable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                None,  # type: ignore[arg-type]
                [
                    MediaProviderSettings(
                        "openai",
                        True,
                        None,
                        models={"gpt-image-1": {"text-to-image"}},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )

            models = await service.models()

        self.assertGreaterEqual(len(models), 1)
        self.assertTrue(all(not model.usable for model in models))
        self.assertTrue(all(model.unavailable_reason == "credential_required" for model in models))


if __name__ == "__main__":
    unittest.main()
