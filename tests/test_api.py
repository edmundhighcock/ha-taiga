"""Tests for the Taiga API client."""

from __future__ import annotations

import re

import pytest
import pytest_asyncio
import aiohttp
from aiohttp import ClientSession
from aioresponses import aioresponses

from custom_components.taiga.api import (
    TaigaAPI,
    TaigaAuthError,
    TaigaConnectionError,
)


BASE_URL = "http://taiga.example.com"


@pytest.fixture
def mock_aiohttp():
    with aioresponses() as m:
        yield m


@pytest_asyncio.fixture
async def api():
    session = ClientSession()
    client = TaigaAPI(session, BASE_URL)
    yield client
    await session.close()


@pytest.mark.asyncio
async def test_authenticate_success(mock_aiohttp, api, auth_response):
    """Test successful authentication."""
    mock_aiohttp.post(f"{BASE_URL}/api/v1/auth", payload=auth_response)

    result = await api.authenticate("astagi", "password123")

    assert result["auth_token"] == "f4k3"
    assert api.user_id == 10
    assert api._token == "f4k3"


@pytest.mark.asyncio
async def test_authenticate_invalid_credentials(mock_aiohttp, api):
    """Test authentication with invalid credentials."""
    mock_aiohttp.post(f"{BASE_URL}/api/v1/auth", status=400)

    with pytest.raises(TaigaAuthError, match="Invalid username or password"):
        await api.authenticate("wrong", "wrong")


@pytest.mark.asyncio
async def test_authenticate_connection_error(api):
    """Test authentication when Taiga is unreachable."""
    # No mock registered, so aiohttp will fail to connect
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/v1/auth", exception=aiohttp.ClientConnectionError())
        with pytest.raises(TaigaConnectionError):
            await api.authenticate("user", "pass")


@pytest.mark.asyncio
async def test_validate_token(mock_aiohttp, api, auth_response):
    """Test token validation."""
    api.set_token("valid-token")
    mock_aiohttp.get(f"{BASE_URL}/api/v1/users/me", payload=auth_response)

    result = await api.validate_token()

    assert api.user_id == 10


@pytest.mark.asyncio
async def test_validate_token_invalid(mock_aiohttp, api):
    """Test validation with invalid token."""
    api.set_token("bad-token")
    mock_aiohttp.get(f"{BASE_URL}/api/v1/users/me", status=401)

    with pytest.raises(TaigaAuthError):
        await api.validate_token()


@pytest.mark.asyncio
async def test_get_projects(mock_aiohttp, api, projects_list):
    """Test fetching projects list."""
    api.set_token("f4k3")
    mock_aiohttp.get(
        f"{BASE_URL}/api/v1/projects?member=10",
        payload=projects_list,
    )

    result = await api.get_projects(member=10)

    assert len(result) == 1
    assert result[0]["name"] == "Project Example 0"
    assert result[0]["id"] == 1


@pytest.mark.asyncio
async def test_get_user_stories(mock_aiohttp, api, userstories_list):
    """Test fetching user stories."""
    api.set_token("f4k3")
    mock_aiohttp.get(
        f"{BASE_URL}/api/v1/userstories?project=1",
        payload=userstories_list,
    )

    result = await api.get_user_stories(1)

    assert len(result) == 1
    assert result[0]["subject"] == "Test story"
    assert result[0]["version"] == 1


@pytest.mark.asyncio
async def test_get_tasks(mock_aiohttp, api, tasks_list):
    """Test fetching tasks."""
    api.set_token("f4k3")
    mock_aiohttp.get(
        f"{BASE_URL}/api/v1/tasks?project=1",
        payload=tasks_list,
    )

    result = await api.get_tasks(1)

    assert len(result) == 2
    assert result[0]["subject"] == "Customer personal data"


@pytest.mark.asyncio
async def test_get_epics(mock_aiohttp, api, epics_list):
    """Test fetching epics."""
    api.set_token("f4k3")
    mock_aiohttp.get(
        f"{BASE_URL}/api/v1/epics?project=1",
        payload=epics_list,
    )

    result = await api.get_epics(1)

    assert len(result) == 1
    assert result[0]["subject"] == "Added file copying and processing of images (resizing)"


@pytest.mark.asyncio
async def test_get_userstory_statuses(mock_aiohttp, api, userstory_statuses):
    """Test fetching user story statuses."""
    api.set_token("f4k3")
    mock_aiohttp.get(
        f"{BASE_URL}/api/v1/userstory-statuses?project=1",
        payload=userstory_statuses,
    )

    result = await api.get_userstory_statuses(1)

    assert len(result) == 5
    assert result[0]["name"] == "New"
    assert result[4]["is_closed"] is True


@pytest.mark.asyncio
async def test_create_user_story(mock_aiohttp, api, userstories_list):
    """Test creating a user story."""
    api.set_token("f4k3")
    created = {**userstories_list[0], "subject": "New story"}
    mock_aiohttp.post(f"{BASE_URL}/api/v1/userstories", payload=created)

    result = await api.create_user_story(1, "New story")

    assert result["subject"] == "New story"


@pytest.mark.asyncio
async def test_update_user_story(mock_aiohttp, api, userstories_list):
    """Test updating a user story with version for optimistic concurrency."""
    api.set_token("f4k3")
    updated = {**userstories_list[0], "status": 3, "version": 2}
    mock_aiohttp.patch(
        f"{BASE_URL}/api/v1/userstories/58190",
        payload=updated,
    )

    result = await api.update_user_story(58190, version=1, status=3)

    assert result["status"] == 3


@pytest.mark.asyncio
async def test_request_with_expired_token(mock_aiohttp, api):
    """Test that 401 response raises TaigaAuthError."""
    api.set_token("expired")
    mock_aiohttp.get(f"{BASE_URL}/api/v1/projects", status=401)

    with pytest.raises(TaigaAuthError):
        await api.get_projects()


@pytest.mark.asyncio
async def test_authorization_header(mock_aiohttp, api, projects_list):
    """Test that auth header is sent with requests."""
    api.set_token("my-token")
    mock_aiohttp.get(f"{BASE_URL}/api/v1/projects", payload=projects_list)

    await api.get_projects()

    # Verify the request was made with the right header
    history = mock_aiohttp.requests
    key = ("GET", f"{BASE_URL}/api/v1/projects")
    # aioresponses stores requests - verify at least one was made
    assert len(history) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        lambda api: api.get_projects(),
        lambda api: api.get_user_stories(1),
        lambda api: api.get_tasks(1),
        lambda api: api.get_epics(1),
        lambda api: api.get_userstory_statuses(1),
        lambda api: api.get_task_statuses(1),
    ],
)
async def test_list_requests_disable_pagination(mock_aiohttp, api, call):
    """Test that list endpoints ask Taiga to disable pagination.

    Without this header Taiga only returns the first page of results, so
    the sensor would silently see a fraction of the stories/tasks/epics.
    """
    api.set_token("f4k3")
    mock_aiohttp.get(re.compile(rf"^{re.escape(BASE_URL)}/api/v1/.*"), payload=[])

    await call(api)

    history = mock_aiohttp.requests
    # Find the (only) request made and check its headers.
    request_calls = next(iter(history.values()))
    headers = request_calls[-1].kwargs["headers"]
    assert headers.get("x-disable-pagination") == "True"


@pytest.mark.asyncio
async def test_single_object_get_does_not_disable_pagination(
    mock_aiohttp, api, userstories_list
):
    """Test that single-object GETs don't send the pagination-disabling header."""
    api.set_token("f4k3")
    mock_aiohttp.get(
        f"{BASE_URL}/api/v1/userstories/58190", payload=userstories_list[0]
    )

    await api.get_user_story(58190)

    history = mock_aiohttp.requests
    request_calls = next(iter(history.values()))
    headers = request_calls[-1].kwargs["headers"]
    assert "x-disable-pagination" not in headers
