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
