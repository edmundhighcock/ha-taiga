"""Tests for the Taiga DataUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taiga.api import TaigaAPI, TaigaAuthError, TaigaConnectionError
from custom_components.taiga.const import CONF_AUTH_METHOD, CONF_PROJECTS, CONF_SCAN_INTERVAL, AUTH_METHOD_CREDENTIALS, DOMAIN
from custom_components.taiga.coordinator import TaigaCoordinator
from custom_components.taiga.models import TaigaData


PROJECT_CONFIG = [
    {"id": 1, "name": "Test Project", "slug": "test-project"},
]


def _make_entry(hass):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        CONF_PROJECTS: PROJECT_CONFIG,
        CONF_SCAN_INTERVAL: 30,
        CONF_AUTH_METHOD: AUTH_METHOD_CREDENTIALS,
        "username": "admin",
        "password": "pass",
    }
    entry.entry_id = "test_entry"
    return entry


@pytest.fixture
def mock_api(
    userstory_statuses, task_statuses, userstories_list, tasks_list, epics_list, project_details
):
    """Create a mock TaigaAPI with fixture data."""
    api = AsyncMock(spec=TaigaAPI)
    api.get_userstory_statuses.return_value = userstory_statuses
    api.get_task_statuses.return_value = task_statuses
    api.get_user_stories.return_value = userstories_list
    api.get_tasks.return_value = tasks_list
    api.get_epics.return_value = epics_list
    api.get_project.return_value = project_details
    return api


@pytest.mark.asyncio
async def test_coordinator_fetches_data(hass, mock_api, enable_custom_integrations):
    """Test that coordinator fetches and structures project data."""
    entry = _make_entry(hass)
    coordinator = TaigaCoordinator(hass, entry, mock_api)

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert 1 in coordinator.data.projects

    project = coordinator.data.projects[1]
    assert project.project_name == "Test Project"
    assert project.project_slug == "test-project"
    assert len(project.userstory_statuses) == 5
    assert len(project.task_statuses) == 4
    assert len(project.user_stories) == 1
    assert len(project.tasks) == 2
    assert len(project.epics) == 1


@pytest.mark.asyncio
async def test_coordinator_parallel_fetches(hass, mock_api, enable_custom_integrations):
    """Test that coordinator calls all API endpoints for a project."""
    entry = _make_entry(hass)
    coordinator = TaigaCoordinator(hass, entry, mock_api)

    await coordinator.async_refresh()

    mock_api.get_userstory_statuses.assert_called_once_with(1)
    mock_api.get_task_statuses.assert_called_once_with(1)
    mock_api.get_user_stories.assert_called_once_with(1)
    mock_api.get_tasks.assert_called_once_with(1)
    mock_api.get_epics.assert_called_once_with(1)
    mock_api.get_project.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_coordinator_auth_error_retries(hass, mock_api, enable_custom_integrations):
    """Test that coordinator re-authenticates on auth error."""
    mock_api.get_userstory_statuses.side_effect = TaigaAuthError("expired")
    entry = _make_entry(hass)
    coordinator = TaigaCoordinator(hass, entry, mock_api)

    await coordinator.async_refresh()

    # Coordinator should have tried to re-auth
    mock_api.authenticate.assert_called_once_with("admin", "pass")
    # Data should be None since update failed
    assert coordinator.data is None


@pytest.mark.asyncio
async def test_coordinator_connection_error(hass, mock_api, enable_custom_integrations):
    """Test that coordinator handles connection errors."""
    mock_api.get_userstory_statuses.side_effect = TaigaConnectionError("offline")
    entry = _make_entry(hass)
    coordinator = TaigaCoordinator(hass, entry, mock_api)

    await coordinator.async_refresh()

    # Data should be None since update failed
    assert coordinator.data is None


@pytest.mark.asyncio
async def test_coordinator_extracts_members(hass, mock_api, enable_custom_integrations):
    """Test that coordinator extracts member names from project details."""
    entry = _make_entry(hass)
    coordinator = TaigaCoordinator(hass, entry, mock_api)

    await coordinator.async_refresh()

    project = coordinator.data.projects[1]
    # project_details_success.json has member id=10 "Alicia Diaz"
    assert 10 in project.members
    assert project.members[10] == "Alicia Diaz"
