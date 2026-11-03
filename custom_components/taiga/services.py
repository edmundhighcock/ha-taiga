"""Service handlers for the Taiga integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import TaigaCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_coordinator(
    hass: HomeAssistant, project_id: int | None = None
) -> TaigaCoordinator:
    """Get the coordinator, optionally matching a project ID."""
    coordinators: dict[str, TaigaCoordinator] = hass.data.get(DOMAIN, {})

    if not coordinators:
        raise HomeAssistantError("No Taiga integration configured")

    if project_id is not None:
        for coordinator in coordinators.values():
            if coordinator.data and project_id in coordinator.data.projects:
                return coordinator
        raise HomeAssistantError(
            f"No Taiga integration tracking project {project_id}"
        )

    if len(coordinators) == 1:
        return next(iter(coordinators.values()))

    raise HomeAssistantError(
        "Multiple Taiga integrations configured, please specify project_id"
    )


def _resolve_status_id(
    coordinator: TaigaCoordinator,
    project_id: int,
    item_type: str,
    status_name: str,
) -> int:
    """Resolve a status name to its ID."""
    if coordinator.data is None:
        raise HomeAssistantError("Taiga data not yet loaded")

    project = coordinator.data.projects.get(project_id)
    if project is None:
        raise HomeAssistantError(f"Project {project_id} not found")

    if item_type == "user_story":
        statuses = project.userstory_statuses
    else:
        statuses = project.task_statuses

    for s in statuses:
        if s["name"].lower() == status_name.lower():
            return s["id"]

    available = ", ".join(s["name"] for s in statuses)
    raise HomeAssistantError(
        f"Status '{status_name}' not found. Available: {available}"
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Taiga services."""

    async def handle_change_status(call: ServiceCall) -> None:
        """Handle change_status service call."""
        item_type: str = call.data["item_type"]
        item_id: int = int(call.data["item_id"])
        status_name: str = call.data["status_name"]
        project_id: int | None = call.data.get("project_id")
        if project_id is not None:
            project_id = int(project_id)

        coordinator = _get_coordinator(hass, project_id)
        api = coordinator.api

        # Get current item to read its version and project
        if item_type == "user_story":
            item = await api.get_user_story(item_id)
        else:
            item = await api.get_task(item_id)

        pid = project_id or item["project"]
        status_id = _resolve_status_id(coordinator, pid, item_type, status_name)

        # Update with optimistic concurrency
        if item_type == "user_story":
            await api.update_user_story(item_id, version=item["version"], status=status_id)
        else:
            await api.update_task(item_id, version=item["version"], status=status_id)

        await coordinator.async_request_refresh()

    async def handle_create_user_story(call: ServiceCall) -> None:
        """Handle create_user_story service call."""
        project_id = int(call.data["project_id"])
        subject: str = call.data["subject"]
        coordinator = _get_coordinator(hass, project_id)

        kwargs: dict[str, Any] = {}

        if description := call.data.get("description"):
            kwargs["description"] = description

        if status_name := call.data.get("status_name"):
            kwargs["status"] = _resolve_status_id(
                coordinator, project_id, "user_story", status_name
            )

        if tags := call.data.get("tags"):
            kwargs["tags"] = [t.strip() for t in tags.split(",")]

        result = await coordinator.api.create_user_story(project_id, subject, **kwargs)

        # If epic_id specified, link the story to the epic. The story already
        # exists at this point, so a failure linking it to the epic must not
        # prevent the coordinator from refreshing.
        try:
            if epic_id := call.data.get("epic_id"):
                epic_id = int(epic_id)
                await coordinator.api.link_user_story_to_epic(epic_id, result["id"])
        finally:
            await coordinator.async_request_refresh()

    async def handle_create_task(call: ServiceCall) -> None:
        """Handle create_task service call."""
        project_id = int(call.data["project_id"])
        subject: str = call.data["subject"]
        coordinator = _get_coordinator(hass, project_id)

        kwargs: dict[str, Any] = {}

        if user_story_id := call.data.get("user_story_id"):
            kwargs["user_story"] = int(user_story_id)

        if status_name := call.data.get("status_name"):
            kwargs["status"] = _resolve_status_id(
                coordinator, project_id, "task", status_name
            )

        await coordinator.api.create_task(project_id, subject, **kwargs)
        await coordinator.async_request_refresh()

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "change_status", handle_change_status)
    hass.services.async_register(DOMAIN, "create_user_story", handle_create_user_story)
    hass.services.async_register(DOMAIN, "create_task", handle_create_task)
    hass.services.async_register(DOMAIN, "refresh", handle_refresh)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Taiga services."""
    hass.services.async_remove(DOMAIN, "change_status")
    hass.services.async_remove(DOMAIN, "create_user_story")
    hass.services.async_remove(DOMAIN, "create_task")
    hass.services.async_remove(DOMAIN, "refresh")
