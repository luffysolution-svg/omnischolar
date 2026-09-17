from __future__ import annotations

import json
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

    async def test_atlas_exposes_verified_official_fallback_models(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            empty = MediaService(
                None,  # type: ignore[arg-type]
                [MediaProviderSettings("atlas", True, "key", "https://atlas.example/v1")],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            fallback_models = await empty.models("atlas")
            fallback_ids = {model.id for model in fallback_models if model.usable}
            self.assertIn("google/nano-banana-2/text-to-image", fallback_ids)
            self.assertIn("openai/gpt-image-2/edit", fallback_ids)
            self.assertIn("openai/gpt-image-2.5/sunburst/text-to-image", fallback_ids)

            pinned = MediaService(
                None,  # type: ignore[arg-type]
                [
                    MediaProviderSettings(
                        "atlas",
                        True,
                        "key",
                        "https://atlas.example/v1",
                        {"atlas-image": {"text-to-image"}},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            models = await pinned.models("atlas")

        self.assertEqual(models[0].id, "atlas-image")
        self.assertTrue(models[0].usable)

    async def test_atlas_uses_native_async_generation_and_polling(self) -> None:
        class AtlasTransport:
            def __init__(self) -> None:
                self.calls = []

            async def json(self, method, url, **kwargs):
                self.calls.append((method, url, kwargs))
                if method == "POST":
                    return {"data": {"id": "pred_123", "status": "processing"}}
                return {
                    "data": {
                        "id": "pred_123",
                        "status": "completed",
                        "outputs": ["https://static.example/image.png"],
                    }
                }

        transport = AtlasTransport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [
                    MediaProviderSettings(
                        "atlas",
                        True,
                        "key",
                        "https://api.atlascloud.ai/api/v1",
                        options={"pollIntervalSeconds": 0.01},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            result = await service._call_provider(
                service.providers["atlas"],
                "google/nano-banana-2/text-to-image",
                "text-to-image",
                "draw a diagram",
                [],
                {"n": 2, "resolution": "2k"},
            )

        self.assertEqual(result["data"]["status"], "completed")
        self.assertEqual(transport.calls[0][0], "POST")
        self.assertTrue(transport.calls[0][1].endswith("/model/generateImage"))
        self.assertEqual(transport.calls[0][2]["body"]["num_images"], 2)

    async def test_fal_exposes_current_official_image_slugs_without_catalog_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                None,  # type: ignore[arg-type]
                [MediaProviderSettings("fal", True, "key", "https://queue.fal.run")],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            models = await service.models("fal", discover=True)

        model_ids = {model.id for model in models if model.usable}
        self.assertIn("fal-ai/nano-banana-2", model_ids)
        self.assertIn("openai/gpt-image-2", model_ids)
        self.assertIn("openai/gpt-image-2.5/flare/edit", model_ids)

    def test_qwen_platform_region_and_native_protocol_are_resolved(self) -> None:
        generic = MediaProviderSettings(
            "dashscope", True, "key", "https://dashscope.aliyuncs.com/compatible-mode/v1", {}, {}
        )
        workspace = MediaProviderSettings(
            "dashscope", True, "key", None, {}, {"workspace": "abc123", "region": "cn-beijing"}
        )

        self.assertEqual(
            MediaService._dashscope_base(generic), "https://dashscope.aliyuncs.com/api/v1"
        )
        self.assertEqual(
            MediaService._dashscope_base(workspace),
            "https://abc123.cn-beijing.maas.aliyuncs.com/api/v1",
        )

    def test_qwen_cloud_uses_public_platform_endpoint_without_workspace(self) -> None:
        provider = MediaProviderSettings(
            "qwen-cloud",
            True,
            "key",
            "https://your-workspace.ap-southeast-1.maas.aliyuncs.com/api/v1",
            options={"protocol": "native", "workspace": "your-workspace"},
        )

        self.assertIsNone(MediaService._provider_contract_error(provider))
        self.assertEqual(
            MediaService._dashscope_base(provider),
            "https://dashscope.aliyuncs.com/api/v1",
        )

    async def test_qwen_common_resolution_and_aspect_ratio_map_to_native_size(self) -> None:
        class Transport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {}

        transport = Transport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [MediaProviderSettings("qwen-cloud", True, "key")],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            await service._call_provider(
                service.providers["qwen-cloud"],
                "qwen-image-3.0-pro",
                "text-to-image",
                "draw",
                [],
                {"resolution": "1024x1024", "n": 1, "seed": 7},
            )

        self.assertEqual(transport.call[2]["body"]["parameters"]["size"], "1024*1024")
        self.assertEqual(transport.call[2]["body"]["parameters"]["n"], 1)
        self.assertEqual(transport.call[2]["body"]["parameters"]["seed"], 7)

    def test_vertex_project_is_inferred_from_service_account_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credentials = Path(temporary) / "service-account.json"
            credentials.write_text(json.dumps({"project_id": "inferred-project"}), encoding="utf-8")
            provider = MediaProviderSettings(
                "vertex", True, None, credentials_file=credentials, options={"project": "your-project"}
            )

            self.assertEqual(MediaService._vertex_project(provider), "inferred-project")

    async def test_model_descriptors_expose_official_parameter_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                None,  # type: ignore[arg-type]
                [MediaProviderSettings("qwen-cloud", True, "key")],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            models = await service.models("qwen-cloud")

        self.assertIn("size", models[0].supported_parameters)
        self.assertIn("n", models[0].supported_parameters)
        self.assertNotIn("background", models[0].supported_parameters)

    async def test_xai_image_catalog_is_discovered(self) -> None:
        class CatalogTransport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {"data": [{"id": "grok-imagine-image-2.0", "created": 10}]}

        transport = CatalogTransport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [MediaProviderSettings("xai", True, "key", "https://api.x.ai/v1")],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            models = await service.models("xai", discover=True)

        self.assertEqual(models[0].id, "grok-imagine-image-2.0")
        self.assertTrue(models[0].usable)
        self.assertIn("image-to-image", models[0].capabilities)
        self.assertTrue(transport.call[1].endswith("/image-generation-models"))

    async def test_xai_edit_uses_current_json_image_shape(self) -> None:
        class Transport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {}

        transport = Transport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [MediaProviderSettings("xai", True, "key", "https://api.x.ai/v1", {"grok": {"edit"}})],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            await service._call_provider(
                service.providers["xai"],
                "grok",
                "edit",
                "edit this",
                [("input.png", b"\x89PNG\r\n\x1a\n", "image/png")],
                {},
            )

        body = transport.call[2]["body"]
        self.assertIn("image", body)
        self.assertNotIn("images", body)
        self.assertEqual(body["image"]["type"], "image_url")

    async def test_google_interactions_maps_image_options(self) -> None:
        class Transport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {}

        transport = Transport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [
                    MediaProviderSettings(
                        "google",
                        True,
                        "key",
                        "https://generativelanguage.googleapis.com/v1beta",
                        {"gemini-3.1-flash-image": {"text-to-image"}},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            await service._call_provider(
                service.providers["google"],
                "gemini-3.1-flash-image",
                "text-to-image",
                "draw",
                [],
                {"aspect_ratio": "16:9", "resolution": "2K"},
            )

        self.assertTrue(transport.call[1].endswith("/interactions"))
        body = transport.call[2]["body"]
        self.assertEqual(body["response_format"], {"type": "image", "aspect_ratio": "16:9", "image_size": "2K"})

    async def test_openai_generation_uses_current_image_parameters(self) -> None:
        class Transport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {}

        transport = Transport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [
                    MediaProviderSettings(
                        "openai",
                        True,
                        "key",
                        "https://api.openai.com/v1",
                        {"gpt-image-2": {"text-to-image"}},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            await service._call_provider(
                service.providers["openai"],
                "gpt-image-2",
                "text-to-image",
                "draw",
                [],
                {"size": "1536x1024", "background": "transparent", "output_format": "png", "n": 2},
            )

        body = transport.call[2]["body"]
        self.assertEqual(body["size"], "1536x1024")
        self.assertEqual(body["output_format"], "png")
        self.assertEqual(body["n"], 2)
        self.assertNotIn("response_format", body)

    async def test_qwen_compatible_mode_uses_shared_generation_endpoint(self) -> None:
        class Transport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {}

        transport = Transport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [
                    MediaProviderSettings(
                        "qwen-cloud",
                        True,
                        "key",
                        "https://workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
                        {"qwen-image-3.0-pro": {"text-to-image", "image-to-image"}},
                        {"protocol": "openai-compatible"},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            await service._call_provider(
                service.providers["qwen-cloud"],
                "qwen-image-3.0-pro",
                "text-to-image",
                "draw",
                [],
                {"size": "1024x1024", "n": 2},
            )

        self.assertTrue(transport.call[1].endswith("/images/generations"))
        self.assertEqual(transport.call[2]["body"]["size"], "1024x1024")
        self.assertEqual(transport.call[2]["body"]["n"], 2)

    def test_vertex_model_predict_endpoint_keeps_colon_suffix_relative(self) -> None:
        endpoint = MediaService._relative_endpoint(
            "https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/publishers/google/models",
            "imagen-4.0-generate-001:predict",
        )
        self.assertTrue(endpoint.endswith("/imagen-4.0-generate-001:predict"))

    async def test_vertex_defaults_to_global_location(self) -> None:
        class Transport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {}

        transport = Transport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [
                    MediaProviderSettings(
                        "vertex",
                        True,
                        "oauth-token",
                        None,
                        {"imagen-4.0-generate-001": {"text-to-image"}},
                        {"project": "project-id"},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            await service._call_provider(
                service.providers["vertex"],
                "imagen-4.0-generate-001",
                "text-to-image",
                "draw",
                [],
                {"n": 1},
            )

        self.assertIn("/locations/global/", transport.call[1])

    async def test_vertex_gemini_image_uses_generate_content(self) -> None:
        class Transport:
            async def json(self, method, url, **kwargs):
                self.call = (method, url, kwargs)
                return {}

        transport = Transport()
        with tempfile.TemporaryDirectory() as temporary:
            service = MediaService(
                transport,
                [
                    MediaProviderSettings(
                        "vertex",
                        True,
                        "oauth-token",
                        None,
                        {"gemini-3.1-flash-image": {"text-to-image"}},
                        {"project": "project-id", "location": "global"},
                    )
                ],
                output_root=Path(temporary),
                workspace_roots=(),
            )
            await service._call_provider(
                service.providers["vertex"],
                "gemini-3.1-flash-image",
                "text-to-image",
                "draw",
                [],
                {"n": 1, "aspect_ratio": "16:9", "output_format": "png"},
            )

        self.assertTrue(transport.call[1].endswith(":generateContent"))
        body = transport.call[2]["body"]
        self.assertEqual(body["generationConfig"]["responseModalities"], ["TEXT", "IMAGE"])
        self.assertEqual(body["generationConfig"]["candidateCount"], 1)
        self.assertEqual(body["generationConfig"]["imageConfig"]["aspectRatio"], "16:9")
        self.assertEqual(
            body["generationConfig"]["imageConfig"]["imageOutputOptions"]["mimeType"],
            "image/png",
        )


if __name__ == "__main__":
    unittest.main()
