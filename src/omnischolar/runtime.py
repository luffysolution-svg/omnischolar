"""Runtime that binds loaded config, application services, and one ToolRegistry."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from omnischolar.config import LoadedConfig, load_config
from omnischolar.registry import ToolRegistry
from omnischolar.services.application import OmniScholarApplication
from omnischolar.tools import create_tool_definitions


class OmniScholarRuntime:
    def __init__(self, loaded: LoadedConfig) -> None:
        self.loaded = loaded
        self.application = OmniScholarApplication(loaded)
        self.registry: ToolRegistry | None = None

    async def __aenter__(self) -> Self:
        await self.application.__aenter__()
        config = self.loaded.config
        groups = config.tools.groups.model_dump()
        self.registry = ToolRegistry(
            enabled_groups=groups,
            disabled_tools=config.tools.disabled,
            max_output_bytes=config.runtime.max_output_bytes,
            max_output_lines=config.runtime.max_output_lines,
            known_secrets=self.application.known_secrets,
        )
        self.registry.register_all(create_tool_definitions())
        self.application.registry = self.registry
        return self

    async def __aexit__(self, *args: object) -> None:
        self.registry = None
        await self.application.__aexit__(*args)

    def require_registry(self) -> ToolRegistry:
        if self.registry is None:
            raise RuntimeError("OmniScholarRuntime is not running")
        return self.registry


async def create_runtime(config_path: str | Path | None = None) -> OmniScholarRuntime:
    runtime = OmniScholarRuntime(load_config(config_path))
    return await runtime.__aenter__()
