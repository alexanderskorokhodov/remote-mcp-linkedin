from __future__ import annotations

import asyncio

from remote_mcp_linkedin_protocol import (
    BridgeAck,
    BridgeCommand,
    BridgeHello,
    BridgeResultMessage,
    ProfileGetRequest,
    ProfileSection,
    RawProfileResult,
)
from remote_mcp_linkedin_server.bridge.manager import (
    BridgeConnectionManager,
    BridgeServerConfig,
)
from websockets.asyncio.client import connect


async def test_server_to_bridge_profile_command_routing() -> None:
    manager = BridgeConnectionManager(
        BridgeServerConfig(
            token="test-token",
            host="127.0.0.1",
            port=0,
            command_timeout_seconds=5,
        )
    )
    await manager.start()

    async def mocked_bridge() -> None:
        async with connect(f"ws://127.0.0.1:{manager.port}/bridge") as websocket:
            await websocket.send(
                BridgeHello(token="test-token").model_dump_json()
            )
            ack = BridgeAck.model_validate_json(await websocket.recv())
            assert ack.accepted is True

            command = BridgeCommand.model_validate_json(await websocket.recv())
            assert command.command == "profile.get"
            assert command.payload.username == "jane-doe"

            payload = RawProfileResult(
                profile_url=command.payload.resolved_profile_url,
                username=command.payload.resolved_username,
                requested_sections=command.payload.sections,
                raw_sections={ProfileSection.TOP_CARD: "Jane Doe"},
                extractor="mock",
            )
            await websocket.send(
                BridgeResultMessage(
                    command_id=command.command_id,
                    status="ok",
                    payload=payload,
                ).model_dump_json()
            )

    task = asyncio.create_task(mocked_bridge())
    try:
        for _ in range(100):
            if manager._session is not None:
                break
            await asyncio.sleep(0.01)

        result = await manager.extract_profile(ProfileGetRequest(username="jane-doe"))

        assert result.username == "jane-doe"
        assert result.raw_sections[ProfileSection.TOP_CARD] == "Jane Doe"
        await task
    finally:
        await manager.stop()

