"""Browser extractor factory."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .extractor import (
    PatchrightProfileExtractor,
    ProfileExtractor,
    StubProfileExtractor,
)


@dataclass(frozen=True, slots=True)
class BrowserSessionConfig:
    headless: bool = False
    extractor: str = "stub"
    user_data_dir: Path = Path.home() / ".remote-mcp-linkedin" / "bridge-profile"
    timeout_ms: int = 15000

    @classmethod
    def from_env(cls) -> BrowserSessionConfig:
        return cls(
            headless=os.environ.get("REMOTE_MCP_LINKEDIN_HEADLESS", "false").lower()
            in {"1", "true", "yes"},
            extractor=os.environ.get("REMOTE_MCP_LINKEDIN_EXTRACTOR", "stub"),
            user_data_dir=Path(
                os.environ.get(
                    "REMOTE_MCP_LINKEDIN_BROWSER_USER_DATA_DIR",
                    str(Path.home() / ".remote-mcp-linkedin" / "bridge-profile"),
                )
            ),
            timeout_ms=int(
                os.environ.get("REMOTE_MCP_LINKEDIN_BROWSER_TIMEOUT_MS", "15000")
            ),
        )


def create_profile_extractor(config: BrowserSessionConfig) -> ProfileExtractor:
    if config.extractor == "patchright":
        return PatchrightProfileExtractor(
            headless=config.headless,
            user_data_dir=config.user_data_dir,
            timeout_ms=config.timeout_ms,
        )
    return StubProfileExtractor()
