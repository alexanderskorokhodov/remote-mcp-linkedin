"""Read-only network/contact search command handler for the local bridge."""

from __future__ import annotations

from remote_mcp_linkedin_protocol import BridgeCommand, RawNetworkResult

from remote_mcp_linkedin_bridge.browser.extractor import ProfileExtractor


async def handle_network_search(
    command: BridgeCommand,
    extractor: ProfileExtractor,
) -> RawNetworkResult:
    return await extractor.search_network(command.payload)
