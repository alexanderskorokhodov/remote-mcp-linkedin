"""Read-only profile command handler for the local bridge."""

from __future__ import annotations

from remote_mcp_linkedin_protocol import BridgeCommand, RawProfileResult

from remote_mcp_linkedin_bridge.browser.extractor import ProfileExtractor


async def handle_profile_get(
    command: BridgeCommand,
    extractor: ProfileExtractor,
) -> RawProfileResult:
    return await extractor.extract_profile(command.payload)

