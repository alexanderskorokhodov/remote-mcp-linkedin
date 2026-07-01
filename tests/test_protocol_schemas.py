from __future__ import annotations

import pytest
from pydantic import ValidationError
from remote_mcp_linkedin_protocol import (
    BridgeCommand,
    BridgeResultMessage,
    NetworkDegree,
    NetworkSearchRequest,
    ProfileGetRequest,
    ProfileSection,
    RawNetworkResult,
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


def test_network_search_request_builds_people_search_url() -> None:
    request = NetworkSearchRequest(
        keywords="senior engineer",
        location="Remote",
        network="F,S",
        current_company="1115",
    )

    assert request.network == [NetworkDegree.FIRST, NetworkDegree.SECOND]
    assert request.resolved_search_url == (
        "https://www.linkedin.com/search/results/people/"
        "?keywords=senior+engineer&location=Remote&network=%5B%22F%22%2C%22S%22%5D"
        "&currentCompany=%5B%221115%22%5D"
    )


def test_network_search_request_rejects_plain_company_names() -> None:
    with pytest.raises(ValidationError):
        NetworkSearchRequest(current_company="OpenAI")


def test_bridge_command_rejects_write_actions() -> None:
    with pytest.raises(ValidationError):
        BridgeCommand.model_validate(
            {
                "command_id": "1",
                "command": "profile.connect",
                "payload": {"username": "jane-doe"},
            }
        )


def test_bridge_command_accepts_network_search() -> None:
    command = BridgeCommand.model_validate(
        {
            "command_id": "1",
            "command": "network.search",
            "payload": {"keywords": "engineer", "network": ["F"]},
        }
    )

    assert isinstance(command.payload, NetworkSearchRequest)
    assert command.payload.network == [NetworkDegree.FIRST]


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


def test_raw_network_result_serializes_enum_network_values() -> None:
    result = RawNetworkResult(
        search_url="https://www.linkedin.com/search/results/people/",
        network=[NetworkDegree.FIRST],
        extractor="test",
    )

    dumped = result.model_dump(mode="json")

    assert dumped["network"] == ["F"]
