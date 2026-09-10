"""Pi compatibility adapter backed by the shared ToolRegistry."""

from __future__ import annotations

from typing import Any

from omnischolar.core import ToolExecutionContext
from omnischolar.registry import ToolRegistry


class PiAdapter:
    """Maps Pi-shaped descriptors/results without owning business logic."""

    def __init__(self, registry: ToolRegistry, application: Any) -> None:
        self.registry = registry
        self.application = application

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "label": tool.name.replace("_", " ").title(),
                "description": tool.description,
                "parameters": tool.input_schema,
            }
            for tool in self.registry.list()
        ]

    async def execute(
        self, name: str, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        result = await self.registry.execute(name, arguments, context, self.application)
        return {
            "content": [{"type": "text", "text": result.text}],
            "details": result.structured_content,
            "isError": result.is_error,
        }
