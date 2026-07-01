"""Server-side abstraction for sending commands to the local bridge."""

from __future__ import annotations

from abc import ABC, abstractmethod

from remote_mcp_linkedin_protocol import ProfileGetRequest, RawProfileResult


class BridgeClient(ABC):
    """Small interface used by MCP tools and tests."""

    @abstractmethod
    async def extract_profile(self, request: ProfileGetRequest) -> RawProfileResult:
        """Ask the authenticated local bridge to extract a profile."""

