"""Deterministic dossier builder for visible LinkedIn profile data."""

from __future__ import annotations

from typing import Any

from remote_mcp_linkedin_protocol import ProfileSection, RawProfileResult

from .schemas import EvidenceEntry, ProfileDossier


class DossierBuilder:
    """Builds a structured dossier without LLM reasoning or hallucination."""

    def build(
        self,
        raw: RawProfileResult,
        *,
        include_posts: bool = False,
    ) -> ProfileDossier:
        structured = raw.structured_sections
        evidence: list[EvidenceEntry] = []
        gaps: list[str] = []
        warnings = list(raw.warnings)

        for extraction_error in raw.extraction_errors:
            warnings.append(
                f"{extraction_error.section.value}: {extraction_error.message}"
            )

        top_card = _as_dict(structured.get("top_card"))
        person = _as_dict(structured.get("person")) or {}
        if top_card.get("name") and not person.get("name"):
            person["name"] = top_card["name"]

        headline = _first_text(top_card.get("headline"), structured.get("headline"))
        location = _first_text(top_card.get("location"), structured.get("location"))

        about = _section_summary(
            structured.get("about"),
            raw.raw_sections.get(ProfileSection.ABOUT),
        )

        _add_scalar(
            person.get("name"),
            field="person.name",
            section=ProfileSection.TOP_CARD,
            raw=raw,
            evidence=evidence,
            gaps=gaps,
        )
        _add_scalar(
            headline,
            field="headline",
            section=ProfileSection.TOP_CARD,
            raw=raw,
            evidence=evidence,
            gaps=gaps,
        )
        _add_scalar(
            location,
            field="location",
            section=ProfileSection.TOP_CARD,
            raw=raw,
            evidence=evidence,
            gaps=gaps,
        )
        _add_scalar(
            about,
            field="about",
            section=ProfileSection.ABOUT,
            raw=raw,
            evidence=evidence,
            gaps=gaps,
        )

        experience = _section_items(
            structured.get("experience"),
            raw.raw_sections.get(ProfileSection.EXPERIENCE),
        )
        education = _section_items(
            structured.get("education"),
            raw.raw_sections.get(ProfileSection.EDUCATION),
        )
        skills = _section_items(
            structured.get("skills"),
            raw.raw_sections.get(ProfileSection.SKILLS),
        )
        certifications = _section_items(
            structured.get("certifications"),
            raw.raw_sections.get(ProfileSection.CERTIFICATIONS),
        )
        projects = _section_items(
            structured.get("projects"),
            raw.raw_sections.get(ProfileSection.PROJECTS),
        )
        languages = _section_items(
            structured.get("languages"),
            raw.raw_sections.get(ProfileSection.LANGUAGES),
        )
        contact_info = _optional_dict(
            structured.get("contact_info"),
            raw.raw_sections.get(ProfileSection.CONTACT_INFO),
        )

        section_values: dict[str, tuple[ProfileSection, Any]] = {
            "experience": (ProfileSection.EXPERIENCE, experience),
            "education": (ProfileSection.EDUCATION, education),
            "skills": (ProfileSection.SKILLS, skills),
            "certifications": (ProfileSection.CERTIFICATIONS, certifications),
            "projects": (ProfileSection.PROJECTS, projects),
            "languages": (ProfileSection.LANGUAGES, languages),
            "contact_info": (ProfileSection.CONTACT_INFO, contact_info),
        }
        for field, (section, value) in section_values.items():
            if value:
                evidence.append(
                    EvidenceEntry(
                        field=field,
                        section=section.value,
                        snippet=_snippet(raw.raw_sections.get(section, "")),
                    )
                )
            else:
                gaps.append(field)

        posts: list[dict[str, Any]] = []
        if include_posts:
            posts = _section_items(
                structured.get("posts"),
                raw.raw_sections.get(ProfileSection.POSTS),
            )
            if posts:
                evidence.append(
                    EvidenceEntry(
                        field="posts",
                        section=ProfileSection.POSTS.value,
                        snippet=_snippet(
                            raw.raw_sections.get(ProfileSection.POSTS, "")
                        ),
                    )
                )
            else:
                gaps.append("posts")

        confidence = {
            "person": _confidence(person),
            "headline": _confidence(headline),
            "location": _confidence(location),
            "about": _confidence(about),
            "experience": _confidence(experience),
            "education": _confidence(education),
            "skills": _confidence(skills),
            "certifications": _confidence(certifications),
            "projects": _confidence(projects),
            "languages": _confidence(languages),
            "contact_info": _confidence(contact_info),
        }
        if include_posts:
            confidence["posts"] = _confidence(posts)

        return ProfileDossier(
            person=person,
            headline=headline,
            location=location,
            about=about,
            experience=experience,
            education=education,
            skills=skills,
            certifications=certifications,
            projects=projects,
            languages=languages,
            contact_info=contact_info,
            posts=posts,
            evidence=evidence,
            gaps=_dedupe(gaps),
            warnings=_dedupe(warnings),
            confidence=confidence,
            source_url=raw.profile_url,
            extracted_at=raw.extracted_at,
        )


def _add_scalar(
    value: Any,
    *,
    field: str,
    section: ProfileSection,
    raw: RawProfileResult,
    evidence: list[EvidenceEntry],
    gaps: list[str],
) -> None:
    if value:
        evidence.append(
            EvidenceEntry(
                field=field,
                section=section.value,
                snippet=_snippet(raw.raw_sections.get(section, "")),
            )
        )
    else:
        gaps.append(field)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _section_summary(structured: Any, raw_text: str | None) -> str | None:
    if isinstance(structured, dict):
        summary = _first_text(structured.get("summary"), structured.get("text"))
        if summary:
            return summary
    if isinstance(structured, str) and structured.strip():
        return structured.strip()
    if raw_text and raw_text.strip():
        return raw_text.strip()
    return None


def _section_items(structured: Any, raw_text: str | None) -> list[dict[str, Any]]:
    if isinstance(structured, list):
        return [
            item if isinstance(item, dict) else {"value": item}
            for item in structured
        ]
    if isinstance(structured, dict):
        return [structured]
    if isinstance(structured, str) and structured.strip():
        return [{"raw": structured.strip()}]
    if raw_text and raw_text.strip():
        return [{"raw": raw_text.strip()}]
    return []


def _optional_dict(structured: Any, raw_text: str | None) -> dict[str, Any] | None:
    if isinstance(structured, dict) and structured:
        return structured
    if isinstance(structured, str) and structured.strip():
        return {"raw": structured.strip()}
    if raw_text and raw_text.strip():
        return {"raw": raw_text.strip()}
    return None


def _snippet(value: str, *, limit: int = 240) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


def _confidence(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        return 0.8 if value.strip() else 0.0
    if isinstance(value, dict):
        return 0.8 if value else 0.0
    if isinstance(value, list):
        return 0.75 if value else 0.0
    return 0.5


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
