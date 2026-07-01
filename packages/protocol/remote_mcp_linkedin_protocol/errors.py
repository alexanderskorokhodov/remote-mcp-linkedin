"""Shared protocol-level exceptions and error helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import BridgeError, ErrorCode


@dataclass(slots=True)
class ProtocolException(Exception):
    """Base exception that can be rendered as a bridge protocol error."""

    code: ErrorCode
    message: str
    retryable: bool = False

    def to_bridge_error(self) -> BridgeError:
        return BridgeError(
            code=self.code,
            message=self.message,
            retryable=self.retryable,
        )


class UnsupportedCommand(ProtocolException):
    def __init__(self, command: str) -> None:
        super().__init__(
            code=ErrorCode.UNSUPPORTED_COMMAND,
            message=f"Unsupported bridge command: {command}",
            retryable=False,
        )


class ExtractionFailed(ProtocolException):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(
            code=ErrorCode.EXTRACTION_FAILED,
            message=message,
            retryable=retryable,
        )

