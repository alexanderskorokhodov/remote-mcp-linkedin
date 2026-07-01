from __future__ import annotations


def test_cli_modules_import() -> None:
    import remote_mcp_linkedin_bridge.main
    import remote_mcp_linkedin_server.main

    assert remote_mcp_linkedin_bridge.main.main
    assert remote_mcp_linkedin_server.main.main

