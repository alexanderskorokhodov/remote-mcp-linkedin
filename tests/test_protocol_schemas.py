from __future__ import annotations

import pytest
from pydantic import ValidationError
from remote_mcp_linkedin_protocol import (
    BridgeCommand,
    BridgeResultMessage,
    ProfileGetRequest,
    ProfileSection,
    RawProfileResult,
)


def test_profile_get_request_requires_target() -> None:
    with pytest.raises(ValidationError):
        ProfileGetRequest()


def test_profile_get_request_normalizes_sections() -> None:
    request = ProfileGetRequest(
        username="jane-doe",
        sections="about,experience,about",
    )

    assert request.resolved_profile_url == "https://www.linkedin.com/in/jane-doe/"
    assert request.sections == [ProfileSection.ABOUT, ProfileSection.EXPERIENCE]


def test_bridge_command_rejects_write_actions() -> None:
    with pytest.raises(ValidationError):
        BridgeCommand.model_validate(
            {
                "command_id": "1",
                "command": "profile.connect",
                "payload": {"username": "jane-doe"},
            }
        )


def test_result_message_requires_payload_for_success() -> None:
    with pytest.raises(ValidationError):
        BridgeResultMessage(command_id="1", status="ok")


def test_raw_profile_result_serializes_enum_section_keys() -> None:
    result = RawProfileResult(
        profile_url="https://www.linkedin.com/in/jane-doe/",
        username="jane-doe",
        requested_sections=[ProfileSection.TOP_CARD],
        raw_sections={ProfileSection.TOP_CARD: "Jane Doe"},
        extractor="test",
    )

    dumped = result.model_dump(mode="json")

    assert dumped["raw_sections"]["top_card"] == "Jane Doe"

