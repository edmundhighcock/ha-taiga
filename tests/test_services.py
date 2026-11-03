"""Tests for the Taiga services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

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
