"""Read-only LinkedIn profile MCP tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from remote_mcp_linkedin_protocol import (
    NetworkSearchRequest,
    ProfileGetRequest,
    ProfileSection,
)

from remote_mcp_linkedin_server.bridge.client import BridgeClient
from remote_mcp_linkedin_server.bridge.manager import (
    BridgeCommandError,
    BridgeCommandTimeout,
    BridgeUnavailableError,
)
from remote_mcp_linkedin_server.storage import ResultStore


def register_profile_tools(
    mcp: FastMCP,
    *,
    bridge_client: BridgeClient,
    result_store: ResultStore,
) -> None:
    @mcp.tool(
        title="LinkedIn Profile Get",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"linkedin", "profile", "read-only"},
    )
    async def linkedin_profile_get(
        profile_url: str | None = None,
        username: str | None = None,
        sections: list[str] | None = None,
        max_scrolls: int = 10,
    ) -> dict[str, Any]:
        """Return normalized raw visible profile sections via the local bridge."""

        try:
            request = ProfileGetRequest(
                profile_url=profile_url,
                username=username,
                sections=sections,
                max_scrolls=max_scrolls,
            )
            result = await bridge_client.extract_profile(request)
            payload = result.model_dump(mode="json")
            await result_store.save("profile", payload)
            return payload
        except (
            BridgeUnavailableError,
            BridgeCommandTimeout,
            BridgeCommandError,
        ) as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        title="LinkedIn Profile Posts",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"linkedin", "profile", "posts", "read-only"},
    )
    async def linkedin_profile_posts(
        profile_url: str | None = None,
        username: str | None = None,
        max_scrolls: int = 10,
    ) -> dict[str, Any]:
        """Collect visible posts from a profile's recent activity page."""

        try:
            request = ProfileGetRequest(
                profile_url=profile_url,
                username=username,
                sections=[ProfileSection.POSTS],
                max_scrolls=max_scrolls,
            )
            result = await bridge_client.extract_profile(request)
            payload = result.model_dump(mode="json")
            await result_store.save("profile-posts", payload)
            return payload
        except (
            BridgeUnavailableError,
            BridgeCommandTimeout,
            BridgeCommandError,
        ) as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        title="LinkedIn Contact Network Search",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"linkedin", "network", "contacts", "people", "read-only"},
    )
    async def linkedin_contact_network_search(
        keywords: str | None = None,
        location: str | None = None,
        network: list[str] | None = None,
        current_company: str | None = None,
        max_pages: int = 1,
        max_scrolls: int = 5,
    ) -> dict[str, Any]:
        """Collect visible people-search results, defaulting to 1st-degree contacts."""

        try:
            request = NetworkSearchRequest(
                keywords=keywords,
                location=location,
                network=network,
                current_company=current_company,
                max_pages=max_pages,
                max_scrolls=max_scrolls,
            )
            result = await bridge_client.search_network(request)
            payload = result.model_dump(mode="json")
            await result_store.save("network", payload)
            return payload
        except (
            BridgeUnavailableError,
            BridgeCommandTimeout,
            BridgeCommandError,
        ) as exc:
            raise ToolError(str(exc)) from exc
