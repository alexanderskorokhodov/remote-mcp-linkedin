"""Authenticated single-bridge WebSocket session manager."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from remote_mcp_linkedin_protocol import (
    PROTOCOL_VERSION,
    BridgeAck,
    BridgeCommand,
    BridgeHello,
    BridgeResultMessage,
    ErrorCode,
    NetworkSearchRequest,
    ProfileGetRequest,
    RawNetworkResult,
    RawProfileResult,
)
from remote_mcp_linkedin_protocol.schemas import BridgeError
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .client import BridgeClient

logger = logging.getLogger(__name__)


class BridgeUnavailableError(RuntimeError):
    """Raised when no authenticated bridge is connected."""


class BridgeCommandError(RuntimeError):
    """Raised when the bridge returns a protocol error."""

    def __init__(self, error: BridgeError) -> None:
        super().__init__(error.message)
        self.error = error


class BridgeCommandTimeout(RuntimeError):
    """Raised when a bridge command does not finish in time."""


@dataclass(frozen=True, slots=True)
class BridgeServerConfig:
    token: str
    host: str = "127.0.0.1"
    port: int = 8765
    command_timeout_seconds: float = 120.0

    @classmethod
    def from_env(cls) -> BridgeServerConfig:
        token = os.environ.get("REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN", "")
        if not token:
            raise ValueError("REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN is required")
        return cls(
            token=token,
            host=os.environ.get("REMOTE_MCP_LINKEDIN_BRIDGE_HOST", "127.0.0.1"),
            port=int(os.environ.get("REMOTE_MCP_LINKEDIN_BRIDGE_PORT", "8765")),
            command_timeout_seconds=float(
                os.environ.get(
                    "REMOTE_MCP_LINKEDIN_BRIDGE_COMMAND_TIMEOUT_SECONDS",
                    "120",
                )
            ),
        )


class BridgeSession:
    """One authenticated WebSocket bridge connection."""

    def __init__(self, websocket: ServerConnection) -> None:
        self._websocket = websocket
        self._pending: dict[str, asyncio.Future[BridgeResultMessage]] = {}
        self._send_lock = asyncio.Lock()

    async def send_command(
        self,
        command: BridgeCommand,
        *,
        timeout_seconds: float,
    ) -> RawProfileResult | RawNetworkResult:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[BridgeResultMessage] = loop.create_future()
        self._pending[command.command_id] = future

        try:
            async with self._send_lock:
                await self._websocket.send(command.model_dump_json())

            result = await asyncio.wait_for(future, timeout=timeout_seconds)
            if result.status == "error":
                if result.error is None:
                    raise BridgeCommandError(
                        BridgeError(
                            code=ErrorCode.PROTOCOL_ERROR,
                            message="Bridge returned an error without details",
                        )
                    )
                raise BridgeCommandError(result.error)
            if result.payload is None:
                raise BridgeCommandError(
                    BridgeError(
                        code=ErrorCode.PROTOCOL_ERROR,
                        message="Bridge returned success without a payload",
                    )
                )
            return result.payload
        except TimeoutError as exc:
            raise BridgeCommandTimeout(
                f"Bridge command timed out after {timeout_seconds:.1f}s"
            ) from exc
        finally:
            self._pending.pop(command.command_id, None)

    async def run_read_loop(self) -> None:
        try:
            async for raw_message in self._websocket:
                try:
                    result = BridgeResultMessage.model_validate_json(raw_message)
                except Exception:
                    logger.warning("Ignoring invalid bridge result message")
                    continue

                future = self._pending.pop(result.command_id, None)
                if future is None:
                    logger.warning("Ignoring bridge result for unknown command")
                    continue
                if not future.done():
                    future.set_result(result)
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(
                        BridgeUnavailableError("Bridge disconnected")
                    )
            self._pending.clear()

    async def close(self) -> None:
        await self._websocket.close()


class BridgeConnectionManager(BridgeClient):
    """Accepts one authenticated local bridge and routes commands to it."""

    def __init__(self, config: BridgeServerConfig) -> None:
        self.config = config
        self._server: Server | None = None
        self._session: BridgeSession | None = None
        self._session_lock = asyncio.Lock()

    @classmethod
    def from_env(cls) -> BridgeConnectionManager:
        return cls(BridgeServerConfig.from_env())

    @property
    def port(self) -> int:
        return self.config.port

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await serve(
            self._handle_socket,
            self.config.host,
            self.config.port,
        )
        sockets = getattr(self._server, "sockets", None) or []
        if sockets and self.config.port == 0:
            bound_port = int(sockets[0].getsockname()[1])
            self.config = BridgeServerConfig(
                token=self.config.token,
                host=self.config.host,
                port=bound_port,
                command_timeout_seconds=self.config.command_timeout_seconds,
            )
        logger.info(
            "Bridge WebSocket listener started on %s:%s",
            self.config.host,
            self.config.port,
        )

    async def stop(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def extract_profile(self, request: ProfileGetRequest) -> RawProfileResult:
        session = self._session
        if session is None:
            raise BridgeUnavailableError("No authenticated local bridge is connected")

        command = BridgeCommand(
            command_id=str(uuid.uuid4()),
            command="profile.get",
            payload=request,
        )
        logger.info("Dispatching read-only bridge command profile.get")
        result = await session.send_command(
            command,
            timeout_seconds=self.config.command_timeout_seconds,
        )
        if not isinstance(result, RawProfileResult):
            raise BridgeCommandError(
                BridgeError(
                    code=ErrorCode.PROTOCOL_ERROR,
                    message="Bridge returned non-profile payload for profile.get",
                )
            )
        return result

    async def search_network(
        self, request: NetworkSearchRequest
    ) -> RawNetworkResult:
        session = self._session
        if session is None:
            raise BridgeUnavailableError("No authenticated local bridge is connected")

        command = BridgeCommand(
            command_id=str(uuid.uuid4()),
            command="network.search",
            payload=request,
        )
        logger.info("Dispatching read-only bridge command network.search")
        result = await session.send_command(
            command,
            timeout_seconds=self.config.command_timeout_seconds,
        )
        if not isinstance(result, RawNetworkResult):
            raise BridgeCommandError(
                BridgeError(
                    code=ErrorCode.PROTOCOL_ERROR,
                    message="Bridge returned non-network payload for network.search",
                )
            )
        return result

    async def _handle_socket(self, websocket: ServerConnection) -> None:
        path = self._get_path(websocket)
        if path not in {None, "/bridge"}:
            await websocket.close(code=1008, reason="unsupported path")
            return

        try:
            raw_hello = await asyncio.wait_for(websocket.recv(), timeout=10)
            hello = BridgeHello.model_validate_json(raw_hello)
        except Exception:
            await websocket.close(code=1008, reason="invalid bridge hello")
            return

        if hello.protocol_version != PROTOCOL_VERSION:
            await websocket.close(code=1002, reason="unsupported protocol version")
            return
        if not secrets.compare_digest(hello.token, self.config.token):
            await websocket.close(code=1008, reason="authentication failed")
            return

        session = BridgeSession(websocket)
        async with self._session_lock:
            if self._session is not None:
                await self._session.close()
            self._session = session

        await websocket.send(BridgeAck().model_dump_json())
        logger.info("Authenticated local bridge connected")
        try:
            await session.run_read_loop()
        except ConnectionClosed:
            pass
        finally:
            async with self._session_lock:
                if self._session is session:
                    self._session = None
            logger.info("Local bridge disconnected")

    @staticmethod
    def _get_path(websocket: Any) -> str | None:
        request = getattr(websocket, "request", None)
        path = getattr(request, "path", None)
        if path is not None:
            return path
        return getattr(websocket, "path", None)
