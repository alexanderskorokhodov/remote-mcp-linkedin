"""Minimal local result storage for extracted profile data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ResultStore:
    """Persists extracted JSON results without browser session state."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(
            os.environ.get(
                "REMOTE_MCP_LINKEDIN_RESULTS_DIR",
                ".remote-mcp-linkedin/results",
            )
        )

    async def save(self, kind: str, payload: dict[str, Any]) -> Path:
        return await asyncio.to_thread(self._save_sync, kind, payload)

    def _save_sync(self, kind: str, payload: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        source = str(payload.get("profile_url") or payload.get("source_url") or kind)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
        path = self.root / f"{now}-{kind}-{digest}.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return path

