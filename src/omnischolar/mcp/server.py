"""Local stdio MCP server backed by the ToolRegistry."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import mcp.server.stdio
from mcp import types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.shared.exceptions import McpError

from omnischolar.core import ToolExecutionContext
from omnischolar.registry import ToolDefinition, ToolExecutionResult
from omnischolar.runtime import OmniScholarRuntime
from omnischolar.version import __version__


def tool_to_mcp(definition: ToolDefinition) -> types.Tool:
    meta = (
        {"anthropic/requiresUserInteraction": True}
        if definition.annotations.requires_user_interaction
        else None
    )
    return types.Tool(
        name=definition.name,
        description=definition.description,
        inputSchema=definition.input_schema,
        outputSchema=definition.output_schema,
        annotations=types.ToolAnnotations(
            readOnlyHint=definition.annotations.read_only_hint,
            destructiveHint=definition.annotations.destructive_hint,
            idempotentHint=definition.annotations.read_only_hint,
            openWorldHint=definition.annotations.open_world_hint,
        ),
        _meta=meta,
    )


def result_to_mcp(result: ToolExecutionResult) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=result.text)],
        structuredContent=result.structured_content,
        isError=result.is_error,
    )


def create_server(runtime: OmniScholarRuntime) -> Server[Any, Any]:
    registry = runtime.require_registry()
    application = runtime.application
    server: Server[Any, Any] = Server(
        "omnischolar",
        version=__version__,
        instructions="Use OmniScholar Skills to choose research tools. Paid calls and uploads require confirmation in the tool arguments.",
    )

    @server.list_tools()  # type: ignore[untyped-decorator, no-untyped-call]
    async def list_tools() -> list[types.Tool]:
        return [tool_to_mcp(definition) for definition in registry.list()]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        try:
            definition = registry.get(name)
        except KeyError as exc:
            raise McpError(
                types.ErrorData(code=types.INVALID_PARAMS, message=f"Unknown tool: {name}")
            ) from exc
        del definition
        request = server.request_context
        token = request.meta.progressToken if request.meta else None

        async def progress(value: float, total: float | None, message: str | None) -> None:
            if token is not None:
                await request.session.send_progress_notification(
                    token,
                    value,
                    total,
                    message,
                    related_request_id=str(request.request_id),
                )

        config = runtime.loaded.config
        context = ToolExecutionContext(
            config_source=runtime.loaded.source.kind,
            workspace_roots=tuple(config.runtime.workspace_roots),
            progress=progress,
            metadata={"protocol": "mcp", "requestId": str(request.request_id)},
        )
        result = await registry.execute(name, arguments or {}, context, application)
        return result_to_mcp(result)

    return server


async def run_stdio(config_path: str | Path | None = None) -> None:
    from omnischolar.config import load_config

    async with OmniScholarRuntime(load_config(config_path)) as runtime:
        server = create_server(runtime)
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="omnischolar",
                    server_version=__version__,
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                    instructions="OmniScholar research tools over local stdio MCP",
                ),
            )


def main() -> None:
    asyncio.run(run_stdio())
