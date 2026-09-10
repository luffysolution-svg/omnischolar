"""Host-neutral execution context and explicit authorization gates."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import OmniScholarError

ProgressCallback = Callable[[float, float | None, str | None], Awaitable[None]]


async def _noop_progress(_progress: float, _total: float | None, _message: str | None) -> None:
    return None


@dataclass(slots=True)
class ToolExecutionContext:
    config_source: str
    workspace_roots: tuple[Path, ...] = ()
    allow_external_upload: bool = False
    allow_paid: bool = False
    progress: ProgressCallback = _noop_progress
    cancellation_event: asyncio.Event = field(default_factory=asyncio.Event)
    metadata: dict[str, Any] = field(default_factory=dict)

    def check_cancelled(self) -> None:
        if self.cancellation_event.is_set():
            raise asyncio.CancelledError

    def require_external_upload(self, service: str) -> None:
        if not self.allow_external_upload:
            raise OmniScholarError(
                "upload_authorization_required",
                f"External upload authorization is required for {service}",
                category="authorization",
            )

    def require_paid(self, service: str) -> None:
        if not self.allow_paid:
            raise OmniScholarError(
                "paid_authorization_required",
                f"Paid operation authorization is required for {service}",
                category="authorization",
            )
