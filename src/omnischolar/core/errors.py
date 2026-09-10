"""Stable, redaction-safe errors shared by every host adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class OmniScholarError(Exception):
    """A structured domain error safe to map to MCP and host results."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        category: str = "internal",
        retryable: bool = False,
        http_status: int | None = None,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category
        self.retryable = retryable
        self.http_status = http_status
        self.details = dict(details or {})
        self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "category": self.category,
            "retryable": self.retryable,
        }
        if self.http_status is not None:
            value["httpStatus"] = self.http_status
        if self.details:
            value["details"] = self.details
        return value


def normalize_error(error: BaseException) -> OmniScholarError:
    if isinstance(error, OmniScholarError):
        return error
    if isinstance(error, TimeoutError):
        return OmniScholarError(
            "timeout",
            "The operation exceeded its deadline",
            category="network",
            retryable=True,
            cause=error,
        )
    if isinstance(error, (ValueError, TypeError)):
        return OmniScholarError(
            "invalid_request",
            "The request or provider response could not be processed",
            category="validation",
            details={"exceptionType": type(error).__name__},
            cause=error,
        )
    return OmniScholarError(
        "internal_error",
        "The operation failed",
        category="internal",
        cause=error,
    )
