"""CLI entry point for the remote-mcp-linkedin MCP server."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from remote_mcp_linkedin_server.bridge.manager import (
    BridgeConnectionManager,
    BridgeServerConfig,
)
from remote_mcp_linkedin_server.mcp_server import create_mcp_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="remote-mcp-linkedin-server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport. Defaults to stdio.",
    )
    parser.add_argument("--mcp-host", default="127.0.0.1")
    parser.add_argument("--mcp-port", type=int, default=8000)
    parser.add_argument("--mcp-path", default="/mcp")
    parser.add_argument(
        "--enable-http",
        action="store_true",
        help="Required to expose streamable-http. Stdio is the safe default.",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("REMOTE_MCP_LINKEDIN_LOG_LEVEL", "INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    token = os.environ.get("REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN", "")
    if not token:
        print(
            "REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN is required for bridge auth",
            file=sys.stderr,
        )
        return 2

    if args.transport == "streamable-http" and not args.enable_http:
        print(
            "Refusing to expose an unauthenticated MCP HTTP endpoint by default. "
            "Pass --enable-http only on a trusted network.",
            file=sys.stderr,
        )
        return 2

    manager = BridgeConnectionManager(
        BridgeServerConfig(
            token=token,
            host=os.environ.get("REMOTE_MCP_LINKEDIN_BRIDGE_HOST", "127.0.0.1"),
            port=int(os.environ.get("REMOTE_MCP_LINKEDIN_BRIDGE_PORT", "8765")),
        )
    )
    mcp = create_mcp_server(bridge_manager=manager)

    try:
        if args.transport == "streamable-http":
            mcp.run(
                transport="streamable-http",
                host=args.mcp_host,
                port=args.mcp_port,
                path=args.mcp_path,
            )
        else:
            mcp.run(transport="stdio")
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
