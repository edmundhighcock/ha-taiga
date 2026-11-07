"""Tests for the Taiga services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.taiga.api import TaigaApiError
from custom_components.taiga.const import DOMAIN
from custom_components.taiga.coordinator import TaigaCoordinator
from custom_components.taiga.models import TaigaData, TaigaProjectData
from custom_components.taiga.services import (
    _get_coordinator,
    _resolve_status_id,
    async_setup_services,
)


@pytest.fixture
def mock_coordinator(userstory_statuses, task_statuses):
    """Create a mock coordinator with project data."""
    coordinator = MagicMock(spec=TaigaCoordinator)
    coordinator.api = AsyncMock()
    coordinator.data = TaigaData(
        projects={
            1: TaigaProjectData(
                project_id=1,
                project_name="Test",
                project_slug="test",
                userstory_statuses=userstory_statuses,
                task_statuses=task_statuses,
            )
        }
    )
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def test_get_coordinator_single(hass, mock_coordinator):
    """Test getting coordinator when only one exists."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    result = _get_coordinator(hass)
    assert result is mock_coordinator


def test_get_coordinator_by_project_id(hass, mock_coordinator):
    """Test getting coordinator by project ID."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    result = _get_coordinator(hass, project_id=1)
    assert result is mock_coordinator


def test_get_coordinator_no_integrations(hass):
    """Test error when no integrations configured."""
    hass.data = {}
    with pytest.raises(HomeAssistantError, match="No Taiga integration"):
        _get_coordinator(hass)


def test_get_coordinator_project_not_found(hass, mock_coordinator):
    """Test error when project not tracked."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    with pytest.raises(HomeAssistantError, match="project 999"):
        _get_coordinator(hass, project_id=999)


def test_resolve_status_id(mock_coordinator):
    """Test resolving status name to ID."""
    status_id = _resolve_status_id(mock_coordinator, 1, "user_story", "In progress")
    assert status_id == 3


def test_resolve_status_id_case_insensitive(mock_coordinator):
    """Test that status resolution is case-insensitive."""
    status_id = _resolve_status_id(mock_coordinator, 1, "user_story", "in progress")
    assert status_id == 3


def test_resolve_status_id_not_found(mock_coordinator):
    """Test error when status name not found."""
    with pytest.raises(HomeAssistantError, match="not found.*Available"):
        _resolve_status_id(mock_coordinator, 1, "user_story", "Nonexistent")


def test_resolve_task_status(mock_coordinator):
    """Test resolving task status name to ID."""
    status_id = _resolve_status_id(mock_coordinator, 1, "task", "Closed")
    assert status_id == 4


def test_resolve_status_no_data(mock_coordinator):
    """Test error when coordinator has no data."""
    mock_coordinator.data = None
    with pytest.raises(HomeAssistantError, match="not yet loaded"):
        _resolve_status_id(mock_coordinator, 1, "user_story", "New")


def test_resolve_status_project_not_found(mock_coordinator):
    """Test error when project not in coordinator data."""
    with pytest.raises(HomeAssistantError, match="Project 999"):
        _resolve_status_id(mock_coordinator, 999, "user_story", "New")


@pytest.mark.asyncio
async def test_create_user_story_links_epic_correctly(hass, mock_coordinator):
    """Test that creating a story with an epic_id links it via link_user_story_to_epic.

    Regression test: the handler used to POST {"user_story": id} directly to
    /api/v1/epics/{epic_id}/related_userstories, which Taiga rejects with
    400 {"epic": ["This field is required."]}.
    """
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    mock_coordinator.api.create_user_story.return_value = {"id": 42}
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "create_user_story",
        {"project_id": 1, "subject": "A story", "epic_id": 7},
        blocking=True,
    )

    mock_coordinator.api.link_user_story_to_epic.assert_awaited_once_with(7, 42)
    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_user_story_epic_link_failure_still_refreshes(
    hass, mock_coordinator
):
    """Test that a failure linking the (already created) story to the epic
    does not prevent the coordinator from refreshing."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    mock_coordinator.api.create_user_story.return_value = {"id": 42}
    mock_coordinator.api.link_user_story_to_epic.side_effect = Exception("boom")
    await async_setup_services(hass)

    with pytest.raises(Exception, match="boom"):
        await hass.services.async_call(
            DOMAIN,
            "create_user_story",
            {"project_id": 1, "subject": "A story", "epic_id": 7},
            blocking=True,
        )

    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_user_story_tags_as_string(hass, mock_coordinator):
    """Test that a comma-separated tags string is split into a list."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    mock_coordinator.api.create_user_story.return_value = {"id": 42}
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "create_user_story",
        {"project_id": 1, "subject": "A story", "tags": "one, two"},
        blocking=True,
    )

    mock_coordinator.api.create_user_story.assert_awaited_once_with(
        1, "A story", tags=["one", "two"]
    )


@pytest.mark.asyncio
async def test_create_user_story_tags_as_list(hass, mock_coordinator):
    """Test that a list of tags (e.g. from a script call) is accepted as-is,
    instead of crashing with AttributeError on list.split()."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    mock_coordinator.api.create_user_story.return_value = {"id": 42}
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "create_user_story",
        {"project_id": 1, "subject": "A story", "tags": ["one", "two"]},
        blocking=True,
    )

    mock_coordinator.api.create_user_story.assert_awaited_once_with(
        1, "A story", tags=["one", "two"]
    )


@pytest.mark.asyncio
async def test_update_user_story_passes_fields(hass, mock_coordinator):
    """Test that update_user_story passes the given optional fields through."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "update_user_story",
        {
            "project_id": 1,
            "user_story_id": 58190,
            "subject": "New subject",
            "description": "New description",
            "tags": "one, two",
        },
        blocking=True,
    )

    mock_coordinator.api.update_item.assert_awaited_once_with(
        "user_story",
        58190,
        subject="New subject",
        description="New description",
        tags=["one", "two"],
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_story_tags_as_list(hass, mock_coordinator):
    """Test that update_user_story accepts tags as a list, not just a string."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "update_user_story",
        {"project_id": 1, "user_story_id": 58190, "tags": ["one", "two"]},
        blocking=True,
    )

    mock_coordinator.api.update_item.assert_awaited_once_with(
        "user_story", 58190, tags=["one", "two"]
    )


@pytest.mark.asyncio
async def test_update_user_story_requires_a_field(hass, mock_coordinator):
    """Test that update_user_story rejects calls with no optional field set."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    with pytest.raises(HomeAssistantError, match="At least one"):
        await hass.services.async_call(
            DOMAIN,
            "update_user_story",
            {"project_id": 1, "user_story_id": 58190},
            blocking=True,
        )

    mock_coordinator.api.update_item.assert_not_awaited()
    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_story_wraps_api_error(hass, mock_coordinator):
    """Test that a Taiga API failure is surfaced as a HomeAssistantError."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    mock_coordinator.api.update_item.side_effect = TaigaApiError(
        "API request PATCH /api/v1/userstories/58190 failed with status 400: boom"
    )
    await async_setup_services(hass)

    with pytest.raises(HomeAssistantError, match="Failed to update user story"):
        await hass.services.async_call(
            DOMAIN,
            "update_user_story",
            {"project_id": 1, "user_story_id": 58190, "subject": "New subject"},
            blocking=True,
        )

    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_passes_fields(hass, mock_coordinator):
    """Test that update_task passes the given optional fields through."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "update_task",
        {
            "project_id": 1,
            "task_id": 1149,
            "subject": "New subject",
            "description": "New description",
        },
        blocking=True,
    )

    mock_coordinator.api.update_item.assert_awaited_once_with(
        "task", 1149, subject="New subject", description="New description"
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_task_requires_a_field(hass, mock_coordinator):
    """Test that update_task rejects calls with neither subject nor description."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    with pytest.raises(HomeAssistantError, match="At least one"):
        await hass.services.async_call(
            DOMAIN,
            "update_task",
            {"project_id": 1, "task_id": 1149},
            blocking=True,
        )

    mock_coordinator.api.update_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_wraps_api_error(hass, mock_coordinator):
    """Test that a Taiga API failure updating a task becomes a HomeAssistantError."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    mock_coordinator.api.update_item.side_effect = TaigaApiError("boom")
    await async_setup_services(hass)

    with pytest.raises(HomeAssistantError, match="Failed to update task"):
        await hass.services.async_call(
            DOMAIN,
            "update_task",
            {"project_id": 1, "task_id": 1149, "subject": "New subject"},
            blocking=True,
        )

    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_comment_passes_fields(hass, mock_coordinator):
    """Test that add_comment forwards item_type, item_id, and comment text."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "add_comment",
        {
            "project_id": 1,
            "item_type": "task",
            "item_id": 1149,
            "comment": "Looks good",
        },
        blocking=True,
    )

    mock_coordinator.api.add_comment.assert_awaited_once_with(
        "task", 1149, "Looks good"
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_comment_rejects_invalid_item_type(hass, mock_coordinator):
    """Test that add_comment rejects an item_type outside the known set."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    with pytest.raises(HomeAssistantError, match="Invalid item_type"):
        await hass.services.async_call(
            DOMAIN,
            "add_comment",
            {
                "project_id": 1,
                "item_type": "sprint",
                "item_id": 1,
                "comment": "Looks good",
            },
            blocking=True,
        )

    mock_coordinator.api.add_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_comment_rejects_empty_comment(hass, mock_coordinator):
    """Test that add_comment rejects blank/whitespace-only comment text."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    await async_setup_services(hass)

    with pytest.raises(HomeAssistantError, match="must not be empty"):
        await hass.services.async_call(
            DOMAIN,
            "add_comment",
            {"project_id": 1, "item_type": "task", "item_id": 1, "comment": "   "},
            blocking=True,
        )

    mock_coordinator.api.add_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_comment_wraps_api_error(hass, mock_coordinator):
    """Test that a Taiga API failure adding a comment becomes a HomeAssistantError."""
    hass.data = {DOMAIN: {"entry1": mock_coordinator}}
    mock_coordinator.api.add_comment.side_effect = TaigaApiError("boom")
    await async_setup_services(hass)

    with pytest.raises(HomeAssistantError, match="Failed to add comment"):
        await hass.services.async_call(
            DOMAIN,
            "add_comment",
            {
                "project_id": 1,
                "item_type": "epic",
                "item_id": 1,
                "comment": "Looks good",
            },
            blocking=True,
        )

    mock_coordinator.async_request_refresh.assert_not_awaited()
