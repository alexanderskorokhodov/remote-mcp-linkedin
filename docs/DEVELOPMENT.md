# Development

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Optional browser dependencies:

```bash
python -m pip install -e ".[browser]"
```

## Test

```bash
pytest
ruff check .
```

## Local Smoke Flow

Terminal 1:

```bash
export REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN="dev-token"
remote-mcp-linkedin-server --transport streamable-http --enable-http
```

Terminal 2:

```bash
export REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN="dev-token"
remote-mcp-linkedin-bridge --extractor stub
```

The smoke path uses mock data by default. Use
`REMOTE_MCP_LINKEDIN_EXTRACTOR=patchright` only when testing real local browser
behavior.

