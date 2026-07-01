"""Read-only profile extraction interface and minimal implementations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from remote_mcp_linkedin_protocol import (
    ProfileGetRequest,
    ProfileSection,
    RawProfileResult,
    SectionExtractionError,
)


class ProfileExtractor(Protocol):
    async def extract_profile(self, request: ProfileGetRequest) -> RawProfileResult:
        """Extract visible profile data from the local browser context."""

    async def close(self) -> None:
        """Release browser resources."""


class StubProfileExtractor:
    """Deterministic extractor used for protocol smoke tests and development."""

    async def extract_profile(self, request: ProfileGetRequest) -> RawProfileResult:
        username = request.resolved_username or "unknown-profile"
        display_name = username.replace("-", " ").replace("_", " ").title()
        requested = list(request.sections)
        raw_sections: dict[ProfileSection, str] = {
            ProfileSection.TOP_CARD: "\n".join(
                [
                    display_name,
                    "Stub profile headline",
                    "Visible location unavailable in stub mode",
                ]
            ),
            ProfileSection.ABOUT: (
                "Stub extraction mode is active. Replace this with the Patchright "
                "extractor to collect visible LinkedIn profile text locally."
            ),
            ProfileSection.EXPERIENCE: "Stub Company - Stub Role",
            ProfileSection.EDUCATION: "Stub University",
            ProfileSection.SKILLS: "Python\nMCP\nBrowser automation",
        }
        if ProfileSection.POSTS in requested:
            raw_sections[ProfileSection.POSTS] = "Stub post text"

        raw_sections = {
            section: text
            for section, text in raw_sections.items()
            if section in requested
        }
        structured_sections = {
            "top_card": {
                "name": display_name,
                "headline": "Stub profile headline",
                "location": "Visible location unavailable in stub mode",
            },
            "about": {
                "summary": raw_sections.get(ProfileSection.ABOUT, ""),
            },
            "experience": [
                {"title": "Stub Role", "company": "Stub Company"},
            ],
            "education": [
                {"school": "Stub University"},
            ],
            "skills": [
                {"name": "Python"},
                {"name": "MCP"},
                {"name": "Browser automation"},
            ],
        }
        if ProfileSection.POSTS in requested:
            structured_sections["posts"] = [{"raw": "Stub post text"}]

        return RawProfileResult(
            profile_url=request.resolved_profile_url,
            username=username,
            requested_sections=requested,
            raw_sections=raw_sections,
            structured_sections=structured_sections,
            warnings=[
                "STUB_BROWSER_EXTRACTION: v0.1 default bridge extractor returns "
                "mock data."
            ],
            extractor="stub",
            extracted_at=datetime.now(UTC),
        )

    async def close(self) -> None:
        return None


class PatchrightProfileExtractor:
    """Experimental read-only Patchright extractor.

    This intentionally performs only page navigation and visible text extraction.
    It does not export cookies, browser profile data, storage state, or CDP access.
    """

    def __init__(
        self,
        *,
        headless: bool,
        user_data_dir: Path,
        timeout_ms: int,
    ) -> None:
        self._headless = headless
        self._user_data_dir = user_data_dir
        self._timeout_ms = timeout_ms
        self._playwright = None
        self._context = None

    async def extract_profile(self, request: ProfileGetRequest) -> RawProfileResult:
        await self._ensure_context()
        if self._context.pages:
            page = self._context.pages[0]
        else:
            page = await self._context.new_page()
        await page.goto(
            request.resolved_profile_url,
            wait_until="domcontentloaded",
            timeout=self._timeout_ms,
        )
        await page.wait_for_timeout(1000)

        text = await self._extract_visible_main_text(page)
        raw_sections = _split_profile_text(text, request.sections)
        top_card = _parse_top_card(raw_sections.get(ProfileSection.TOP_CARD, ""))
        warnings = [
            "EXPERIMENTAL_BROWSER_EXTRACTION: v0.1 Patchright extractor is "
            "minimal and may return partial sections."
        ]
        extraction_errors: list[SectionExtractionError] = []

        if _looks_like_auth_wall(text, page.url):
            warnings.append("LinkedIn login or auth challenge appears to be visible.")

        for section in request.sections:
            if section not in raw_sections:
                extraction_errors.append(
                    SectionExtractionError(
                        section=section,
                        message="Section was not found in visible page text.",
                        retryable=False,
                    )
                )

        return RawProfileResult(
            profile_url=request.resolved_profile_url,
            username=request.resolved_username,
            requested_sections=list(request.sections),
            raw_sections=raw_sections,
            structured_sections={"top_card": top_card} if top_card else {},
            extraction_errors=extraction_errors,
            warnings=warnings,
            extractor="patchright",
            extracted_at=datetime.now(UTC),
        )

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def _ensure_context(self) -> None:
        if self._context is not None:
            return
        try:
            from patchright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Patchright extractor selected but patchright is not installed. "
                "Install remote-mcp-linkedin[browser]."
            ) from exc

        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._user_data_dir),
            headless=self._headless,
            viewport={"width": 1440, "height": 1000},
        )

    async def _extract_visible_main_text(self, page) -> str:
        try:
            return await page.locator("main").inner_text(timeout=self._timeout_ms)
        except Exception:
            return await page.locator("body").inner_text(timeout=self._timeout_ms)


SECTION_HEADERS: dict[ProfileSection, tuple[str, ...]] = {
    ProfileSection.ABOUT: ("about",),
    ProfileSection.EXPERIENCE: ("experience",),
    ProfileSection.EDUCATION: ("education",),
    ProfileSection.SKILLS: ("skills",),
    ProfileSection.CERTIFICATIONS: ("licenses & certifications", "certifications"),
    ProfileSection.PROJECTS: ("projects",),
    ProfileSection.LANGUAGES: ("languages",),
    ProfileSection.CONTACT_INFO: ("contact info", "contact"),
    ProfileSection.POSTS: ("activity", "posts"),
}


def _split_profile_text(
    text: str,
    requested_sections: list[ProfileSection],
) -> dict[ProfileSection, str]:
    lines = _clean_lines(text)
    result: dict[ProfileSection, str] = {}
    if ProfileSection.TOP_CARD in requested_sections and lines:
        result[ProfileSection.TOP_CARD] = "\n".join(lines[:40])

    lower_lines = [line.lower() for line in lines]
    header_positions: dict[ProfileSection, int] = {}
    for section, headers in SECTION_HEADERS.items():
        if section not in requested_sections:
            continue
        for index, line in enumerate(lower_lines):
            if line in headers:
                header_positions[section] = index
                break

    sorted_positions = sorted(header_positions.items(), key=lambda item: item[1])
    for index, (section, start) in enumerate(sorted_positions):
        end = len(lines)
        if index + 1 < len(sorted_positions):
            end = sorted_positions[index + 1][1]
        section_text = "\n".join(lines[start:end]).strip()
        if section_text:
            result[section] = section_text
    return result


def _parse_top_card(text: str) -> dict[str, str]:
    lines = _clean_lines(text)
    top_card: dict[str, str] = {}
    if lines:
        top_card["name"] = lines[0]
    if len(lines) > 1:
        top_card["headline"] = lines[1]
    if len(lines) > 2:
        top_card["location"] = lines[2]
    return top_card


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _looks_like_auth_wall(text: str, current_url: str) -> bool:
    lowered = text.lower()
    return "/login" in current_url or "sign in" in lowered or "join linkedin" in lowered
