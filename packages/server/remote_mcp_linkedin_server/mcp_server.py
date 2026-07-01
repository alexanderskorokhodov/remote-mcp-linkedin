"""FastMCP server assembly for remote-mcp-linkedin."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from remote_mcp_linkedin_server import __version__
from remote_mcp_linkedin_server.bridge.manager import BridgeConnectionManager
from remote_mcp_linkedin_server.storage import ResultStore
from remote_mcp_linkedin_server.tools.dossiers import register_dossier_tools
from remote_mcp_linkedin_server.tools.profiles import register_profile_tools

logger = logging.getLogger(__name__)


def create_mcp_server(
    *,
    bridge_manager: BridgeConnectionManager | None = None,
    result_store: ResultStore | None = None,
) -> FastMCP:
    manager = bridge_manager or BridgeConnectionManager.from_env()
    store = result_store or ResultStore()

    @asynccontextmanager
    async def server_lifespan(app: FastMCP) -> AsyncIterator[dict[str, Any]]:
        del app
        await manager.start()
        try:
            yield {"bridge_manager": manager}
        finally:
            await manager.stop()

    mcp = FastMCP(
        "remote-mcp-linkedin",
        version=__version__,
        lifespan=server_lifespan,
        mask_error_details=True,
    )
    register_profile_tools(mcp, bridge_client=manager, result_store=store)
    register_dossier_tools(mcp, bridge_client=manager, result_store=store)
    return mcp

