"""Read-only LinkedIn profile MCP tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from remote_mcp_linkedin_protocol import ProfileGetRequest

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
    ) -> dict[str, Any]:
        """Return normalized raw visible profile sections via the local bridge."""

        try:
            request = ProfileGetRequest(
                profile_url=profile_url,
                username=username,
                sections=sections,
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
