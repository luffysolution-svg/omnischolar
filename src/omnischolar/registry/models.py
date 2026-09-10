"""ToolRegistry data models."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from omnischolar.core import ToolExecutionContext

ToolGroup = Literal[
    "runtime",
    "literature",
    "ai4scholar",
    "zotero",
    "parsing",
    "citation",
    "materials",
    "chemistry",
    "media",
]
SideEffects = Literal["none", "filesystem", "external-upload", "paid"]
CostClass = Literal["free", "metered", "paid", "unknown"]


class ServiceContainer(Protocol): ...


ToolExecutor = Callable[[dict[str, Any], ToolExecutionContext, Any], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ToolAnnotations:
    read_only_hint: bool
    open_world_hint: bool
    destructive_hint: bool
    justification: str
    requires_user_interaction: bool = False

    def mcp(self) -> dict[str, Any]:
        return {
            "readOnlyHint": self.read_only_hint,
            "openWorldHint": self.open_world_hint,
            "destructiveHint": self.destructive_hint,
        }


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    execute: ToolExecutor = field(repr=False, compare=False)
    output_schema: dict[str, Any] | None = None
    group: ToolGroup = "literature"
    capabilities: tuple[str, ...] = ()
    side_effects: SideEffects = "none"
    requires_network: bool = False
    requires_credentials: tuple[str, ...] = ()
    cost_class: CostClass = "free"
    annotations: ToolAnnotations = ToolAnnotations(True, False, False, "Read-only operation")


@dataclass(slots=True)
class ToolExecutionResult:
    is_error: bool
    structured_content: dict[str, Any]
    text: str
