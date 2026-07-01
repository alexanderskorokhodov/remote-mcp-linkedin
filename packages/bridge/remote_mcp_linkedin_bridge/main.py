"""CLI entry point for the local remote-mcp-linkedin browser bridge."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from pydantic import ValidationError
from remote_mcp_linkedin_protocol import (
    PROTOCOL_VERSION,
    BridgeAck,
    BridgeCommand,
    BridgeError,
    BridgeHello,
    BridgeResultMessage,
    ErrorCode,
)
from remote_mcp_linkedin_protocol.errors import UnsupportedCommand
from websockets.asyncio.client import connect

from remote_mcp_linkedin_bridge.browser.session import (
    BrowserSessionConfig,
    create_profile_extractor,
)
from remote_mcp_linkedin_bridge.commands.profiles import handle_profile_get

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="remote-mcp-linkedin-bridge")
    parser.add_argument(
        "--server-url",
        default=os.environ.get(
            "REMOTE_MCP_LINKEDIN_SERVER_URL",
            "ws://127.0.0.1:8765/bridge",
        ),
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN", ""),
    )
    parser.add_argument(
        "--extractor",
        choices=("stub", "patchright"),
        default=os.environ.get("REMOTE_MCP_LINKEDIN_EXTRACTOR", "stub"),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=os.environ.get("REMOTE_MCP_LINKEDIN_HEADLESS", "false").lower()
        in {"1", "true", "yes"},
    )
    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=float(os.environ.get("REMOTE_MCP_LINKEDIN_RECONNECT_DELAY", "3")),
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("REMOTE_MCP_LINKEDIN_LOG_LEVEL", "INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


async def run_bridge(
    *,
    server_url: str,
    token: str,
    session_config: BrowserSessionConfig,
    reconnect_delay: float,
) -> None:
    extractor = create_profile_extractor(session_config)
    try:
        while True:
            try:
                async with connect(server_url) as websocket:
                    await websocket.send(
                        BridgeHello(token=token).model_dump_json()
                    )
                    ack = BridgeAck.model_validate_json(await websocket.recv())
                    if ack.protocol_version != PROTOCOL_VERSION or not ack.accepted:
                        raise RuntimeError("Server rejected bridge hello")
                    logger.info("Connected to remote-mcp-linkedin server")

                    async for raw_message in websocket:
                        result = await _handle_message(raw_message, extractor)
                        await websocket.send(result.model_dump_json())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Bridge connection closed: %s", exc.__class__.__name__)
                await asyncio.sleep(reconnect_delay)
    finally:
        await extractor.close()


async def _handle_message(
    raw_message: str | bytes,
    extractor,
) -> BridgeResultMessage:
    command_id = "unknown"
    try:
        command = BridgeCommand.model_validate_json(raw_message)
        command_id = command.command_id
        if command.command != "profile.get":
            raise UnsupportedCommand(command.command)
        payload = await handle_profile_get(command, extractor)
        return BridgeResultMessage(
            command_id=command.command_id,
            status="ok",
            payload=payload,
        )
    except UnsupportedCommand as exc:
        return BridgeResultMessage(
            command_id=command_id,
            status="error",
            error=exc.to_bridge_error(),
        )
    except ValidationError as exc:
        return BridgeResultMessage(
            command_id=command_id,
            status="error",
            error=BridgeError(
                code=ErrorCode.PROTOCOL_ERROR,
                message="Invalid bridge command message",
                details={"error_count": exc.error_count()},
            ),
        )
    except Exception as exc:
        return BridgeResultMessage(
            command_id=command_id,
            status="error",
            error=BridgeError(
                code=ErrorCode.EXTRACTION_FAILED,
                message=str(exc),
                retryable=True,
            ),
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not args.token:
        print(
            "REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN or --token is required",
            file=sys.stderr,
        )
        return 2

    session_config = BrowserSessionConfig.from_env()
    session_config = BrowserSessionConfig(
        headless=args.headless,
        extractor=args.extractor,
        user_data_dir=session_config.user_data_dir,
        timeout_ms=session_config.timeout_ms,
    )
    try:
        asyncio.run(
            run_bridge(
                server_url=args.server_url,
                token=args.token,
                session_config=session_config,
                reconnect_delay=args.reconnect_delay,
            )
        )
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
