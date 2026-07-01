"""Versioned WebSocket and extraction schemas for remote-mcp-linkedin."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROTOCOL_VERSION = "0.1"


class ProfileSection(StrEnum):
    TOP_CARD = "top_card"
    ABOUT = "about"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    PROJECTS = "projects"
    LANGUAGES = "languages"
    CONTACT_INFO = "contact_info"
    POSTS = "posts"


DEFAULT_PROFILE_SECTIONS: tuple[ProfileSection, ...] = (
    ProfileSection.TOP_CARD,
    ProfileSection.ABOUT,
    ProfileSection.EXPERIENCE,
    ProfileSection.EDUCATION,
    ProfileSection.SKILLS,
    ProfileSection.CERTIFICATIONS,
    ProfileSection.PROJECTS,
    ProfileSection.LANGUAGES,
    ProfileSection.CONTACT_INFO,
)

ALL_PROFILE_SECTIONS: tuple[ProfileSection, ...] = (
    *DEFAULT_PROFILE_SECTIONS,
    ProfileSection.POSTS,
)


class ErrorCode(StrEnum):
    AUTH_FAILED = "auth_failed"
    BRIDGE_UNAVAILABLE = "bridge_unavailable"
    COMMAND_TIMEOUT = "command_timeout"
    EXTRACTION_FAILED = "extraction_failed"
    INVALID_REQUEST = "invalid_request"
    PROTOCOL_ERROR = "protocol_error"
    UNSUPPORTED_COMMAND = "unsupported_command"


class BridgeError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class SectionExtractionError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: ProfileSection
    message: str
    retryable: bool = False


class ProfileGetRequest(BaseModel):
    """Read-only request for visible LinkedIn profile data."""

    model_config = ConfigDict(extra="forbid")

    profile_url: str | None = None
    username: str | None = None
    sections: list[ProfileSection] = Field(
        default_factory=lambda: list(DEFAULT_PROFILE_SECTIONS)
    )

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("profile_url must be an http(s) URL")
        if not parsed.netloc.endswith("linkedin.com"):
            raise ValueError("profile_url must point to linkedin.com")
        if "/in/" not in parsed.path:
            raise ValueError("profile_url must point to a LinkedIn /in/ profile")
        return value

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().strip("/")
        if not value:
            return None
        if any(ch.isspace() for ch in value) or "/" in value or "?" in value:
            raise ValueError("username must be a LinkedIn public profile slug")
        return value

    @field_validator("sections", mode="before")
    @classmethod
    def normalize_sections(cls, value: Any) -> list[ProfileSection]:
        if value is None or value == "":
            return list(DEFAULT_PROFILE_SECTIONS)
        if isinstance(value, str):
            raw_sections = [item.strip() for item in value.split(",")]
        else:
            raw_sections = list(value)

        sections: list[ProfileSection] = []
        for raw in raw_sections:
            if isinstance(raw, ProfileSection):
                section = raw
            else:
                section = ProfileSection(str(raw).strip().lower())
            if section not in sections:
                sections.append(section)
        return sections or list(DEFAULT_PROFILE_SECTIONS)

    @model_validator(mode="after")
    def require_target(self) -> ProfileGetRequest:
        if not self.profile_url and not self.username:
            raise ValueError("Provide profile_url or username")
        return self

    @property
    def resolved_profile_url(self) -> str:
        if self.profile_url:
            return self.profile_url.rstrip("/")
        return f"https://www.linkedin.com/in/{self.username}/"

    @property
    def resolved_username(self) -> str | None:
        if self.username:
            return self.username
        if not self.profile_url:
            return None
        parsed = urlparse(self.profile_url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "in":
            return parts[1]
        return None


class RawProfileResult(BaseModel):
    """Normalized raw profile extraction returned by the local bridge."""

    model_config = ConfigDict(extra="forbid")

    profile_url: str
    username: str | None = None
    requested_sections: list[ProfileSection]
    raw_sections: dict[ProfileSection, str] = Field(default_factory=dict)
    structured_sections: dict[str, Any] = Field(default_factory=dict)
    extraction_errors: list[SectionExtractionError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    visible_only: bool = True
    extractor: str = "unknown"
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )


class BridgeHello(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bridge.hello"] = "bridge.hello"
    protocol_version: Literal["0.1"] = PROTOCOL_VERSION
    bridge_id: str = "default"
    token: str = Field(repr=False)


class BridgeAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["server.ack"] = "server.ack"
    protocol_version: Literal["0.1"] = PROTOCOL_VERSION
    accepted: bool = True
    message: str = "bridge authenticated"


class BridgeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["command"] = "command"
    protocol_version: Literal["0.1"] = PROTOCOL_VERSION
    command_id: str
    command: Literal["profile.get"]
    payload: ProfileGetRequest


class BridgeResultMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["result"] = "result"
    protocol_version: Literal["0.1"] = PROTOCOL_VERSION
    command_id: str
    status: Literal["ok", "error"]
    payload: RawProfileResult | None = None
    error: BridgeError | None = None

    @model_validator(mode="after")
    def require_matching_payload(self) -> BridgeResultMessage:
        if self.status == "ok" and self.payload is None:
            raise ValueError("ok result requires payload")
        if self.status == "error" and self.error is None:
            raise ValueError("error result requires error")
        return self

