# remote-mcp-linkedin

Read-only MCP server for turning visible LinkedIn profile data into structured dossiers.
It uses a local browser bridge, so the browser session stays on the user's machine.

## What it does

- Opens visible LinkedIn profile pages through a local browser bridge
- Extracts basic public / visible profile data
- Builds a structured dossier for AI agents
- Exposes the result through MCP tools

## MCP tools

- `linkedin_profile_get` - returns normalized visible profile data
- `linkedin_profile_dossier` - returns a structured profile dossier with evidence, gaps, warnings, and confidence

## Safety

- Read-only by design
- No messages, likes, comments, connection requests, or job actions
- No cookies or browser session data are exported
- The browser runs locally

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
export REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN="replace-with-a-long-random-token"
remote-mcp-linkedin-server
remote-mcp-linkedin-bridge
```

## Status

Small prototype.

Working:

- MCP server
- local bridge
- profile data tool
- dossier tool
- JSON result storage

Not ready:

- robust LinkedIn parser
- production extraction
- advanced profile analysis

## License

MIT

