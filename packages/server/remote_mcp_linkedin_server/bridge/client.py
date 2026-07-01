"""Server-side abstraction for sending commands to the local bridge."""

from __future__ import annotations

from abc import ABC, abstractmethod

from remote_mcp_linkedin_protocol import (
    NetworkSearchRequest,
    ProfileGetRequest,
    RawNetworkResult,
    RawProfileResult,
)


class BridgeClient(ABC):
    """Small interface used by MCP tools and tests."""

    @abstractmethod
    async def extract_profile(self, request: ProfileGetRequest) -> RawProfileResult:
        """Ask the authenticated local bridge to extract a profile."""

    @abstractmethod
    async def search_network(
        self, request: NetworkSearchRequest
    ) -> RawNetworkResult:
        """Ask the authenticated local bridge to search visible contact network data."""
