"""Host-neutral execution context for tool execution."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ProgressCallback = Callable[[float, float | None, str | None], Awaitable[None]]


async def _noop_progress(_progress: float, _total: float | None, _message: str | None) -> None:
    return None


@dataclass(slots=True)
class ToolExecutionContext:
    config_source: str
    workspace_roots: tuple[Path, ...] = ()
    progress: ProgressCallback = _noop_progress
    cancellation_event: asyncio.Event = field(default_factory=asyncio.Event)
    metadata: dict[str, Any] = field(default_factory=dict)

    def check_cancelled(self) -> None:
        if self.cancellation_event.is_set():
            raise asyncio.CancelledError
