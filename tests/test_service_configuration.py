from __future__ import annotations

import unittest
from types import SimpleNamespace

from omnischolar.config import ConfigSource, LoadedConfig, OmniScholarConfig
from omnischolar.services.application import OmniScholarApplication


class ServiceConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_discovers_remote_image_catalogs(self) -> None:
        class Media:
            discover: bool | None = None

            async def models(self, _provider=None, *, discover=False):
                self.discover = discover
                return []

        media = Media()
        app = OmniScholarApplication(
            LoadedConfig(OmniScholarConfig(), ConfigSource("defaults", None))
        )
        app.services = SimpleNamespace(
            literature=SimpleNamespace(statuses=lambda: []),
            media=media,
            mineru=None,
            materials=None,
            chemistry=SimpleNamespace(sources=lambda: {}),
        )

        await app.status()

        self.assertTrue(media.discover)


if __name__ == "__main__":
    unittest.main()
