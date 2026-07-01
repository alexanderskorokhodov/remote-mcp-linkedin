from __future__ import annotations

import asyncio
from pathlib import Path

from fastmcp import Client
from remote_mcp_linkedin_protocol import (
    BridgeAck,
    BridgeCommand,
    BridgeHello,
    BridgeResultMessage,
    ProfileSection,
    RawProfileResult,
)
from remote_mcp_linkedin_server.bridge.manager import (
    BridgeConnectionManager,
    BridgeServerConfig,
)
from remote_mcp_linkedin_server.mcp_server import create_mcp_server
from remote_mcp_linkedin_server.storage import ResultStore
from websockets.asyncio.client import connect


async def test_mocked_mcp_dossier_flow(tmp_path: Path) -> None:
    manager = BridgeConnectionManager(
        BridgeServerConfig(
            token="test-token",
            host="127.0.0.1",
            port=0,
            command_timeout_seconds=5,
        )
    )
    mcp = create_mcp_server(
        bridge_manager=manager,
        result_store=ResultStore(tmp_path),
    )

    async with Client(mcp) as client:
        bridge_task = asyncio.create_task(_mock_bridge(manager))
        for _ in range(100):
            if manager._session is not None:
                break
            await asyncio.sleep(0.01)

        result = await client.call_tool(
            "linkedin_profile_dossier",
            {"username": "jane-doe", "include_posts": False},
        )

        await bridge_task

    assert not result.is_error
    assert result.data["person"]["name"] == "Jane Doe"
    assert result.data["headline"] == "Principal Engineer"


async def _mock_bridge(manager: BridgeConnectionManager) -> None:
    async with connect(f"ws://127.0.0.1:{manager.port}/bridge") as websocket:
        await websocket.send(BridgeHello(token="test-token").model_dump_json())
        BridgeAck.model_validate_json(await websocket.recv())

        command = BridgeCommand.model_validate_json(await websocket.recv())
        payload = RawProfileResult(
            profile_url=command.payload.resolved_profile_url,
            username=command.payload.resolved_username,
            requested_sections=command.payload.sections,
            raw_sections={
                ProfileSection.TOP_CARD: "Jane Doe\nPrincipal Engineer\nBerlin",
                ProfileSection.ABOUT: "Builds distributed systems.",
            },
            structured_sections={
                "top_card": {
                    "name": "Jane Doe",
                    "headline": "Principal Engineer",
                    "location": "Berlin",
                },
                "about": {"summary": "Builds distributed systems."},
            },
            extractor="mock",
        )
        await websocket.send(
            BridgeResultMessage(
                command_id=command.command_id,
                status="ok",
                payload=payload,
            ).model_dump_json()
        )

