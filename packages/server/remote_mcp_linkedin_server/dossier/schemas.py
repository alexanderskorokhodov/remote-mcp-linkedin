"""Structured dossier output schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    section: str
    snippet: str


class ProfileDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person: dict[str, Any] = Field(default_factory=dict)
    headline: str | None = None
    location: str | None = None
    about: str | None = None
    experience: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, Any]] = Field(default_factory=list)
    contact_info: dict[str, Any] | None = None
    posts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[EvidenceEntry] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    source_url: str
    extracted_at: datetime

