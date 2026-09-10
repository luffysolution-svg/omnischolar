"""The single definition, validation, execution, error, and output boundary."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from omnischolar.core import (
    ToolExecutionContext,
    jsonable,
    normalize_error,
    redact,
    truncate_output,
)

from .models import ToolDefinition, ToolExecutionResult


class ToolRegistry:
    def __init__(
        self,
        *,
        enabled_groups: dict[str, bool] | None = None,
        disabled_tools: set[str] | None = None,
        max_output_bytes: int = 50 * 1024,
        max_output_lines: int = 2_000,
        known_secrets: tuple[str, ...] = (),
    ) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self.enabled_groups = enabled_groups or {}
        self.disabled_tools = disabled_tools or set()
        self.max_output_bytes = max_output_bytes
        self.max_output_lines = max_output_lines
        self.known_secrets = known_secrets

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Duplicate tool name: {definition.name}")
        Draft202012Validator.check_schema(definition.input_schema)
        if definition.output_schema:
            Draft202012Validator.check_schema(definition.output_schema)
        self._tools[definition.name] = definition

    def register_all(self, definitions: list[ToolDefinition]) -> None:
        for definition in definitions:
            self.register(definition)

    def is_enabled(self, definition: ToolDefinition) -> bool:
        return (
            self.enabled_groups.get(definition.group, True)
            and definition.name not in self.disabled_tools
        )

    def list(self, *, enabled_only: bool = True) -> list[ToolDefinition]:
        tools = list(self._tools.values())
        if enabled_only:
            tools = [tool for tool in tools if self.is_enabled(tool)]
        return sorted(tools, key=lambda tool: tool.name)

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name]

    async def execute(
        self, name: str, arguments: dict[str, Any], context: ToolExecutionContext, services: Any
    ) -> ToolExecutionResult:
        definition = self.get(name)
        if not self.is_enabled(definition):
            payload = {
                "ok": False,
                "error": {
                    "code": "tool_disabled",
                    "message": f"Tool {name} is disabled",
                    "category": "authorization",
                    "retryable": False,
                },
            }
            return self._result(payload, True)
        errors = sorted(
            Draft202012Validator(definition.input_schema).iter_errors(arguments),
            key=lambda item: list(item.path),
        )
        if errors:
            issues = [
                {"path": ".".join(str(item) for item in error.path), "message": error.message}
                for error in errors
            ]
            return self._result(
                {
                    "ok": False,
                    "error": {
                        "code": "invalid_arguments",
                        "message": "Tool arguments failed schema validation",
                        "category": "validation",
                        "retryable": False,
                        "details": {"issues": issues},
                    },
                },
                True,
            )
        try:
            context.check_cancelled()
            value = await definition.execute(arguments, context, services)
            payload = {"ok": True, "data": redact(value, self.known_secrets)}
            return self._result(payload, False)
        except BaseException as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(error, __import__("asyncio").CancelledError):
                raise
            normalized = normalize_error(error)
            payload = {"ok": False, "error": redact(normalized.to_dict(), self.known_secrets)}
            return self._result(payload, True)

    def _result(self, payload: dict[str, Any], is_error: bool) -> ToolExecutionResult:
        normalized = jsonable(payload)
        assert isinstance(normalized, dict)
        limited = truncate_output(
            normalized, max_bytes=self.max_output_bytes, max_lines=self.max_output_lines
        )
        if limited["truncated"]:
            structured = {"ok": not is_error, "output": limited}
        else:
            structured = normalized
        text = json.dumps(structured, ensure_ascii=False, indent=2, sort_keys=True)
        return ToolExecutionResult(is_error, structured, text)
