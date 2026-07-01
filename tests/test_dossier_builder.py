from __future__ import annotations

from datetime import UTC, datetime

from remote_mcp_linkedin_protocol import (
    ProfileSection,
    RawProfileResult,
    SectionExtractionError,
)
from remote_mcp_linkedin_server.dossier.builder import DossierBuilder


def test_dossier_builder_uses_structured_data_and_gaps() -> None:
    raw = RawProfileResult(
        profile_url="https://www.linkedin.com/in/jane-doe/",
        username="jane-doe",
        requested_sections=[
            ProfileSection.TOP_CARD,
            ProfileSection.ABOUT,
            ProfileSection.EXPERIENCE,
        ],
        raw_sections={
            ProfileSection.TOP_CARD: "Jane Doe\nPrincipal Engineer\nBerlin",
            ProfileSection.ABOUT: "Builds distributed systems.",
            ProfileSection.EXPERIENCE: "Principal Engineer at ExampleCo",
        },
        structured_sections={
            "top_card": {
                "name": "Jane Doe",
                "headline": "Principal Engineer",
                "location": "Berlin",
            },
            "about": {"summary": "Builds distributed systems."},
            "experience": [
                {"title": "Principal Engineer", "company": "ExampleCo"},
            ],
        },
        extraction_errors=[
            SectionExtractionError(
                section=ProfileSection.SKILLS,
                message="Skills section not visible",
            )
        ],
        extractor="test",
        extracted_at=datetime(2026, 7, 1, tzinfo=UTC),
    )

    dossier = DossierBuilder().build(raw)

    assert dossier.person["name"] == "Jane Doe"
    assert dossier.headline == "Principal Engineer"
    assert dossier.experience == [
        {"title": "Principal Engineer", "company": "ExampleCo"}
    ]
    assert "skills: Skills section not visible" in dossier.warnings
    assert "education" in dossier.gaps
    assert any(item.field == "headline" for item in dossier.evidence)


def test_dossier_builder_includes_posts_only_when_requested() -> None:
    raw = RawProfileResult(
        profile_url="https://www.linkedin.com/in/jane-doe/",
        username="jane-doe",
        requested_sections=[ProfileSection.TOP_CARD, ProfileSection.POSTS],
        raw_sections={
            ProfileSection.TOP_CARD: "Jane Doe",
            ProfileSection.POSTS: "Visible post",
        },
        structured_sections={
            "top_card": {"name": "Jane Doe"},
            "posts": [{"raw": "Visible post"}],
        },
        extractor="test",
    )

    without_posts = DossierBuilder().build(raw, include_posts=False)
    with_posts = DossierBuilder().build(raw, include_posts=True)

    assert without_posts.posts == []
    assert with_posts.posts == [{"raw": "Visible post"}]

