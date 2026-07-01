"""Read-only profile extraction interface and minimal implementations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from remote_mcp_linkedin_protocol import (
    NetworkSearchRequest,
    ProfileGetRequest,
    ProfileSection,
    RawNetworkResult,
    RawProfileResult,
    SectionExtractionError,
)

AUTH_WALL_WARNING = "LinkedIn login or auth challenge appears to be visible."


class ProfileExtractor(Protocol):
    async def extract_profile(self, request: ProfileGetRequest) -> RawProfileResult:
        """Extract visible profile data from the local browser context."""

    async def search_network(self, request: NetworkSearchRequest) -> RawNetworkResult:
        """Extract visible people-search/contact-network data."""

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

    async def search_network(self, request: NetworkSearchRequest) -> RawNetworkResult:
        profiles = [
            {
                "username": "stub-contact",
                "profile_url": "https://www.linkedin.com/in/stub-contact/",
                "degree": request.network[0].value if request.network else "F",
                "raw": "Stub Contact\n1st\nStub profile headline",
            }
        ]
        return RawNetworkResult(
            search_url=request.resolved_search_url,
            keywords=request.keywords,
            location=request.location,
            network=list(request.network),
            current_company=request.current_company,
            profiles=profiles,
            raw_text="Stub Contact\n1st\nStub profile headline",
            page_texts=["Stub Contact\n1st\nStub profile headline"],
            references=[
                {
                    "kind": "person",
                    "url": "/in/stub-contact/",
                    "text": "Stub Contact",
                    "context": "network_search",
                }
            ],
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
        page = await self._active_page()
        profile_sections = [
            section for section in request.sections if section != ProfileSection.POSTS
        ]
        raw_sections: dict[ProfileSection, str] = {}
        warnings = [
            "EXPERIMENTAL_BROWSER_EXTRACTION: v0.1 Patchright extractor is "
            "minimal and may return partial sections."
        ]
        extraction_errors: list[SectionExtractionError] = []
        structured_sections: dict[str, Any] = {}

        if profile_sections:
            await page.goto(
                request.resolved_profile_url,
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            await page.wait_for_timeout(1000)

            text = await self._extract_visible_main_text(page)
            raw_sections.update(_split_profile_text(text, profile_sections))
            top_card = _parse_top_card(raw_sections.get(ProfileSection.TOP_CARD, ""))
            if top_card:
                structured_sections["top_card"] = top_card

            if _looks_like_auth_wall(text, page.url):
                warnings.append(AUTH_WALL_WARNING)

        if ProfileSection.POSTS in request.sections:
            posts_text, posts = await self._extract_profile_posts(page, request)
            if posts_text:
                raw_sections[ProfileSection.POSTS] = posts_text
                structured_sections["posts"] = posts
            else:
                extraction_errors.append(
                    SectionExtractionError(
                        section=ProfileSection.POSTS,
                        message="Profile posts page did not return visible text.",
                        retryable=True,
                    )
                )

            if _looks_like_auth_wall(posts_text, page.url):
                warnings.append(AUTH_WALL_WARNING)

        if not profile_sections and ProfileSection.POSTS not in request.sections:
            await page.goto(
                request.resolved_profile_url,
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            await page.wait_for_timeout(1000)
            text = await self._extract_visible_main_text(page)
            if _looks_like_auth_wall(text, page.url):
                warnings.append(AUTH_WALL_WARNING)

        for section in profile_sections:
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
            structured_sections=structured_sections,
            extraction_errors=extraction_errors,
            warnings=warnings,
            extractor="patchright",
            extracted_at=datetime.now(UTC),
        )

    async def search_network(self, request: NetworkSearchRequest) -> RawNetworkResult:
        page = await self._active_page()
        search_url = request.resolved_search_url
        page_texts: list[str] = []
        profiles: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []
        seen_profiles: set[str] = set()
        warnings = [
            "EXPERIMENTAL_BROWSER_EXTRACTION: v0.1 Patchright network search is "
            "minimal and may return partial visible results."
        ]

        for page_index in range(request.max_pages):
            url = _with_search_page(search_url, page_index + 1)
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            await self._wait_for_main_text(page, min_length=100, timeout_ms=10000)
            await self._scroll_visible_page(page, max_scrolls=request.max_scrolls)

            text = await self._extract_visible_main_text(page)
            if text:
                page_texts.append(text)
            if _looks_like_auth_wall(text, page.url):
                warnings.append(AUTH_WALL_WARNING)
                break

            page_profiles = await self._extract_people_cards(page)
            new_profiles = 0
            for profile in page_profiles:
                key = str(profile.get("profile_url") or profile.get("username") or "")
                if not key or key in seen_profiles:
                    continue
                seen_profiles.add(key)
                profiles.append(profile)
                new_profiles += 1
                username = profile.get("username")
                if username:
                    references.append(
                        {
                            "kind": "person",
                            "url": f"/in/{username}/",
                            "text": profile.get("name") or username,
                            "context": "network_search",
                        }
                    )
            if page_index > 0 and new_profiles == 0:
                break

        return RawNetworkResult(
            search_url=search_url,
            keywords=request.keywords,
            location=request.location,
            network=list(request.network),
            current_company=request.current_company,
            profiles=profiles,
            raw_text="\n---\n".join(page_texts),
            page_texts=page_texts,
            references=references,
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

    async def _active_page(self):
        await self._ensure_context()
        if self._context.pages:
            return self._context.pages[0]
        return await self._context.new_page()

    async def _extract_profile_posts(
        self,
        page,
        request: ProfileGetRequest,
    ) -> tuple[str, list[dict[str, Any]]]:
        posts_url = _profile_posts_url(request.resolved_profile_url)
        await page.goto(
            posts_url,
            wait_until="domcontentloaded",
            timeout=self._timeout_ms,
        )
        await self._wait_for_main_text(page, min_length=100, timeout_ms=10000)
        await self._scroll_visible_page(page, max_scrolls=request.max_scrolls)
        text = await self._extract_visible_main_text(page)
        posts = await self._extract_post_cards(page)
        return text, posts

    async def _wait_for_main_text(
        self,
        page,
        *,
        min_length: int,
        timeout_ms: int,
    ) -> None:
        try:
            await page.wait_for_function(
                """(minLength) => {
                    const main = document.querySelector('main');
                    return !!main && main.innerText.trim().length >= minLength;
                }""",
                arg=min_length,
                timeout=timeout_ms,
            )
        except Exception:
            return None

    async def _scroll_visible_page(self, page, *, max_scrolls: int) -> None:
        stale_count = 0
        previous_height = 0
        for _ in range(max_scrolls):
            height = await page.evaluate(
                """() => Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight
                )"""
            )
            await page.mouse.wheel(0, 2200)
            await page.evaluate(
                """() => {
                    const main = document.querySelector('main');
                    if (main) {
                        for (const el of main.querySelectorAll('*')) {
                            if (el.scrollHeight > el.clientHeight + 50) {
                                el.scrollTop = el.scrollHeight;
                            }
                        }
                    }
                    window.scrollTo(0, document.body.scrollHeight);
                }"""
            )
            await page.wait_for_timeout(1000)
            if height <= previous_height:
                stale_count += 1
                if stale_count >= 3:
                    break
            else:
                stale_count = 0
                previous_height = height

    async def _extract_post_cards(self, page) -> list[dict[str, Any]]:
        return await page.evaluate(
            """() => {
                const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
                const absolute = href => {
                    try { return new URL(href, location.origin).href; }
                    catch { return null; }
                };
                const usernameFromHref = href => {
                    const url = absolute(href);
                    if (!url) return null;
                    const match = new URL(url).pathname.match(/^\\/in\\/([^/?#]+)/);
                    return match ? match[1] : null;
                };
                const postUrlFrom = node => {
                    for (const a of node.querySelectorAll('a[href]')) {
                        const href = a.getAttribute('href') || '';
                        if (
                            href.includes('/feed/update/') ||
                            href.includes('/posts/')
                        ) {
                            const url = absolute(href);
                            if (url) return url.split('?')[0];
                        }
                    }
                    return null;
                };
                const authorFrom = node => {
                    for (const a of node.querySelectorAll('a[href*="/in/"]')) {
                        const username = usernameFromHref(a.getAttribute('href') || '');
                        const name = normalize(a.innerText || a.textContent);
                        if (username) return { username, name: name || username };
                    }
                    return {};
                };
                const candidates = Array.from(document.querySelectorAll([
                    'main article',
                    'main div.feed-shared-update-v2',
                    'main div[data-urn]',
                    'main li'
                ].join(',')));
                const seen = new Set();
                const posts = [];
                for (const node of candidates) {
                    const raw = normalize(node.innerText || node.textContent);
                    if (!raw || raw.length < 20) continue;
                    const postUrl = postUrlFrom(node);
                    if (!postUrl && !/\\b(like|comment|repost|share)\\b/i.test(raw)) {
                        continue;
                    }
                    const key = postUrl || raw.slice(0, 300);
                    if (seen.has(key)) continue;
                    seen.add(key);
                    const author = authorFrom(node);
                    posts.push({
                        url: postUrl,
                        author_name: author.name || null,
                        author_username: author.username || null,
                        raw,
                    });
                    if (posts.length >= 100) break;
                }
                return posts;
            }"""
        )

    async def _extract_people_cards(self, page) -> list[dict[str, Any]]:
        return await page.evaluate(
            """() => {
                const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
                const absolute = href => {
                    try { return new URL(href, location.origin).href; }
                    catch { return null; }
                };
                const profileFromHref = href => {
                    const url = absolute(href);
                    if (!url) return null;
                    const parsed = new URL(url);
                    const match = parsed.pathname.match(/^\\/in\\/([^/?#]+)/);
                    if (!match) return null;
                    return {
                        username: match[1],
                        profile_url: `https://www.linkedin.com/in/${match[1]}/`,
                    };
                };
                const candidateCards = Array.from(document.querySelectorAll([
                    'main li',
                    'main div.entity-result',
                    'main div.reusable-search__result-container',
                    'main div[data-chameleon-result-urn]'
                ].join(',')));
                const cards = candidateCards.length
                    ? candidateCards
                    : Array.from(document.querySelectorAll('main a[href*="/in/"]'))
                        .map(a => a.closest('li, div') || a);
                const seen = new Set();
                const profiles = [];
                for (const card of cards) {
                    const link = card.querySelector
                        ? card.querySelector('a[href*="/in/"]')
                        : null;
                    const profile = profileFromHref(link?.getAttribute('href') || '');
                    if (!profile || seen.has(profile.username)) continue;
                    const raw = normalize(card.innerText || card.textContent);
                    const linkText = normalize(link.innerText || link.textContent);
                    const firstLine = raw.split(/\\s{2,}|\\n/).find(Boolean) || '';
                    const degreeMatch = raw.match(/\\b(1st|2nd|3rd)\\b/i);
                    seen.add(profile.username);
                    profiles.push({
                        ...profile,
                        name: linkText || firstLine || profile.username,
                        degree: degreeMatch ? degreeMatch[1].toLowerCase() : null,
                        raw,
                    });
                    if (profiles.length >= 100) break;
                }
                return profiles;
            }"""
        )

    async def _extract_visible_main_text(self, page) -> str:
        try:
            return await page.locator("main").inner_text(timeout=self._timeout_ms)
        except Exception:
            return await page.locator("body").inner_text(timeout=self._timeout_ms)

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


def _profile_posts_url(profile_url: str) -> str:
    parsed = urlparse(profile_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "in":
        path = f"/in/{parts[1]}/recent-activity/all/"
    else:
        path = parsed.path.rstrip("/") + "/recent-activity/all/"
    return urlunparse(("https", "www.linkedin.com", path, "", "", ""))


def _with_search_page(search_url: str, page_number: int) -> str:
    if page_number <= 1:
        return search_url

    parsed = urlparse(search_url)
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "page"
    ]
    query_items.append(("page", str(page_number)))
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query_items),
            parsed.fragment,
        )
    )
