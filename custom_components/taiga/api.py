"""Taiga REST API client."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class TaigaAuthError(Exception):
    """Raised when authentication fails."""


class TaigaConnectionError(Exception):
    """Raised when connection to Taiga fails."""


class TaigaApiError(Exception):
    """Raised when an API call fails."""


class TaigaAPI:
    """Async client for the Taiga REST API."""

    def __init__(self, session: aiohttp.ClientSession, url: str) -> None:
        self._session = session
        self._base_url = url.rstrip("/")
        self._token: str | None = None
        self._user_id: int | None = None

    @property
    def user_id(self) -> int | None:
        """Return the authenticated user's ID."""
        return self._user_id

    def set_token(self, token: str) -> None:
        """Set an application token directly."""
        self._token = token

    async def authenticate(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate with username/password and store the auth token.

        Returns the full auth response including user data.
        """
        try:
            resp = await self._session.post(
                f"{self._base_url}/api/v1/auth",
                json={
                    "type": "normal",
                    "username": username,
                    "password": password,
                },
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TaigaConnectionError(
                f"Cannot connect to Taiga at {self._base_url}"
            ) from err

        if resp.status == 400:
            raise TaigaAuthError("Invalid username or password")
        if resp.status != 200:
            raise TaigaApiError(f"Auth failed with status {resp.status}")

        data = await resp.json()
        self._token = data["auth_token"]
        self._user_id = data["id"]
        return data

    async def validate_token(self) -> dict[str, Any]:
        """Validate an application token by fetching the current user.

        Returns user data.
        """
        data = await self._get("/api/v1/users/me")
        self._user_id = data["id"]
        return data

    async def get_projects(self, member: int | None = None) -> list[dict[str, Any]]:
        """Get projects, optionally filtered by member."""
        params: dict[str, Any] = {}
        if member is not None:
            params["member"] = member
        return await self._get("/api/v1/projects", params=params)

    async def get_project(self, project_id: int) -> dict[str, Any]:
        """Get a single project's details."""
        return await self._get(f"/api/v1/projects/{project_id}")

    async def get_userstory_statuses(
        self, project_id: int
    ) -> list[dict[str, Any]]:
        """Get all user story statuses for a project."""
        return await self._get(
            "/api/v1/userstory-statuses", params={"project": project_id}
        )

    async def get_task_statuses(self, project_id: int) -> list[dict[str, Any]]:
        """Get all task statuses for a project."""
        return await self._get(
            "/api/v1/task-statuses", params={"project": project_id}
        )

    async def get_user_stories(
        self, project_id: int, status: int | None = None
    ) -> list[dict[str, Any]]:
        """Get user stories for a project."""
        params: dict[str, Any] = {"project": project_id}
        if status is not None:
            params["status"] = status
        return await self._get("/api/v1/userstories", params=params)

    async def get_tasks(
        self, project_id: int, status: int | None = None
    ) -> list[dict[str, Any]]:
        """Get tasks for a project."""
        params: dict[str, Any] = {"project": project_id}
        if status is not None:
            params["status"] = status
        return await self._get("/api/v1/tasks", params=params)

    async def get_epics(self, project_id: int) -> list[dict[str, Any]]:
        """Get epics for a project."""
        return await self._get("/api/v1/epics", params={"project": project_id})

    async def create_user_story(
        self, project_id: int, subject: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Create a new user story."""
        payload: dict[str, Any] = {"project": project_id, "subject": subject}
        payload.update(kwargs)
        return await self._post("/api/v1/userstories", json=payload)

    async def create_task(
        self, project_id: int, subject: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Create a new task."""
        payload: dict[str, Any] = {"project": project_id, "subject": subject}
        payload.update(kwargs)
        return await self._post("/api/v1/tasks", json=payload)

    async def update_user_story(
        self, story_id: int, version: int, **kwargs: Any
    ) -> dict[str, Any]:
        """Update a user story. Requires the current version for optimistic concurrency."""
        payload: dict[str, Any] = {"version": version}
        payload.update(kwargs)
        return await self._patch(f"/api/v1/userstories/{story_id}", json=payload)

    async def update_task(
        self, task_id: int, version: int, **kwargs: Any
    ) -> dict[str, Any]:
        """Update a task. Requires the current version for optimistic concurrency."""
        payload: dict[str, Any] = {"version": version}
        payload.update(kwargs)
        return await self._patch(f"/api/v1/tasks/{task_id}", json=payload)

    async def get_user_story(self, story_id: int) -> dict[str, Any]:
        """Get a single user story."""
        return await self._get(f"/api/v1/userstories/{story_id}")

    async def get_task(self, task_id: int) -> dict[str, Any]:
        """Get a single task."""
        return await self._get(f"/api/v1/tasks/{task_id}")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, json=json)

    async def _patch(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PATCH", path, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers(),
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TaigaConnectionError(
                f"Cannot connect to Taiga at {self._base_url}"
            ) from err

        if resp.status == 401:
            raise TaigaAuthError("Authentication token is invalid or expired")
        if resp.status >= 400:
            text = await resp.text()
            raise TaigaApiError(
                f"API request {method} {path} failed with status {resp.status}: {text}"
            )

        return await resp.json()
