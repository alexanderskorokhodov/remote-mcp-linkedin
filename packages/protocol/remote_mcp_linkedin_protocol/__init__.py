"""Shared protocol package for remote-mcp-linkedin."""

from .schemas import (
    ALL_PROFILE_SECTIONS,
    DEFAULT_PROFILE_SECTIONS,
    PROTOCOL_VERSION,
    BridgeAck,
    BridgeCommand,
    BridgeError,
    BridgeHello,
    BridgeResultMessage,
    ErrorCode,
    ProfileGetRequest,
    ProfileSection,
    RawProfileResult,
    SectionExtractionError,
)

__all__ = [
    "ALL_PROFILE_SECTIONS",
    "DEFAULT_PROFILE_SECTIONS",
    "PROTOCOL_VERSION",
    "BridgeAck",
    "BridgeCommand",
    "BridgeError",
    "BridgeHello",
    "BridgeResultMessage",
    "ErrorCode",
    "ProfileGetRequest",
    "ProfileSection",
    "RawProfileResult",
    "SectionExtractionError",
]
