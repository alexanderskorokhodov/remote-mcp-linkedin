"""Read-only LinkedIn profile dossier MCP tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from remote_mcp_linkedin_protocol import (
    DEFAULT_PROFILE_SECTIONS,
    ProfileGetRequest,
    ProfileSection,
)

from remote_mcp_linkedin_server.bridge.client import BridgeClient
from remote_mcp_linkedin_server.bridge.manager import (
    BridgeCommandError,
    BridgeCommandTimeout,
    BridgeUnavailableError,
)
from remote_mcp_linkedin_server.dossier.builder import DossierBuilder
from remote_mcp_linkedin_server.storage import ResultStore


def register_dossier_tools(
    mcp: FastMCP,
    *,
    bridge_client: BridgeClient,
    result_store: ResultStore,
) -> None:
    builder = DossierBuilder()

    @mcp.tool(
        title="LinkedIn Profile Dossier",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"linkedin", "profile", "dossier", "read-only"},
    )
    async def linkedin_profile_dossier(
        profile_url: str | None = None,
        username: str | None = None,
        include_posts: bool = False,
    ) -> dict[str, Any]:
        """Build a deterministic structured dossier from visible profile sections."""

        try:
            sections = list(DEFAULT_PROFILE_SECTIONS)
            if include_posts and ProfileSection.POSTS not in sections:
                sections.append(ProfileSection.POSTS)
            request = ProfileGetRequest(
                profile_url=profile_url,
                username=username,
                sections=sections,
            )
            raw = await bridge_client.extract_profile(request)
            dossier = builder.build(raw, include_posts=include_posts)
            payload = dossier.model_dump(mode="json")
            await result_store.save("dossier", payload)
            return payload
        except (
            BridgeUnavailableError,
            BridgeCommandTimeout,
            BridgeCommandError,
        ) as exc:
            raise ToolError(str(exc)) from exc
