"""Sensor platform for the Taiga integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PROJECTS, DOMAIN
from .coordinator import TaigaCoordinator
from .models import TaigaProjectData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Taiga sensors from a config entry."""
    coordinator: TaigaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TaigaProjectSensor(coordinator, proj_config)
        for proj_config in entry.data[CONF_PROJECTS]
    ]
    async_add_entities(entities)


class TaigaProjectSensor(CoordinatorEntity[TaigaCoordinator], SensorEntity):
    """Sensor representing a Taiga project."""

    _attr_icon = "mdi:view-dashboard"
    _attr_native_unit_of_measurement = "items"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TaigaCoordinator,
        project_config: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._project_id = project_config["id"]
        self._attr_unique_id = f"taiga_{project_config['id']}"
        self._attr_name = f"Taiga {project_config['name']}"

    @property
    def _project_data(self) -> TaigaProjectData | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.projects.get(self._project_id)

    @property
    def native_value(self) -> int | None:
        """Return total count of open items."""
        data = self._project_data
        if data is None:
            return None

        closed_us_ids = {
            s["id"] for s in data.userstory_statuses if s.get("is_closed")
        }
        closed_task_ids = {
            s["id"] for s in data.task_statuses if s.get("is_closed")
        }

        open_stories = sum(
            1 for s in data.user_stories if s.get("status") not in closed_us_ids
        )
        open_tasks = sum(
            1 for t in data.tasks if t.get("status") not in closed_task_ids
        )
        return open_stories + open_tasks

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed project data as attributes."""
        data = self._project_data
        if data is None:
            return {}

        status_name_map_us = {s["id"]: s["name"] for s in data.userstory_statuses}
        status_name_map_task = {s["id"]: s["name"] for s in data.task_statuses}
        epic_map = {e["id"]: e.get("subject", "") for e in data.epics}

        # Count stories by status
        us_counts: dict[str, int] = {}
        for s in data.userstory_statuses:
            us_counts[s["name"]] = 0
        for story in data.user_stories:
            name = status_name_map_us.get(story.get("status"), "Unknown")
            us_counts[name] = us_counts.get(name, 0) + 1

        # Count tasks by status
        task_counts: dict[str, int] = {}
        for s in data.task_statuses:
            task_counts[s["name"]] = 0
        for task in data.tasks:
            name = status_name_map_task.get(task.get("status"), "Unknown")
            task_counts[name] = task_counts.get(name, 0) + 1

        # Build item lists for the Lovelace card
        story_list = [
            _format_story(story, status_name_map_us, epic_map, data.members)
            for story in data.user_stories
        ]
        task_list = [
            _format_task(task, status_name_map_task, data.members)
            for task in data.tasks
        ]

        return {
            "project_name": data.project_name,
            "project_id": data.project_id,
            "user_story_counts": us_counts,
            "task_counts": task_counts,
            "user_stories": story_list,
            "tasks": task_list,
            "epics": [
                {"id": e["id"], "subject": e.get("subject", "")}
                for e in data.epics
            ],
            "statuses": {
                "user_story": [
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "is_closed": s.get("is_closed", False),
                        "color": s.get("color", "#999999"),
                        "order": s.get("order", 0),
                    }
                    for s in data.userstory_statuses
                ],
                "task": [
                    {
                        "id": s["id"],
                        "name": s["name"],
                        "is_closed": s.get("is_closed", False),
                        "color": s.get("color", "#999999"),
                        "order": s.get("order", 0),
                    }
                    for s in data.task_statuses
                ],
            },
        }


def _format_story(
    story: dict[str, Any],
    status_map: dict[int, str],
    epic_map: dict[int, str],
    members: dict[int, str],
) -> dict[str, Any]:
    """Format a user story for the Lovelace card."""
    epic_id = None
    epic_name = None
    if story.get("epics"):
        first_epic = story["epics"][0]
        epic_id = first_epic.get("id")
        epic_name = epic_map.get(epic_id, first_epic.get("subject", ""))

    assigned_to_id = story.get("assigned_to")
    return {
        "id": story["id"],
        "ref": story.get("ref"),
        "subject": story.get("subject", ""),
        "status": status_map.get(story.get("status"), "Unknown"),
        "status_id": story.get("status"),
        "assigned_to": members.get(assigned_to_id, "") if assigned_to_id else None,
        "assigned_to_id": assigned_to_id,
        "epic": epic_name,
        "epic_id": epic_id,
        "tags": [t[0] if isinstance(t, list) else t for t in story.get("tags", [])],
        "version": story.get("version"),
    }


def _format_task(
    task: dict[str, Any],
    status_map: dict[int, str],
    members: dict[int, str],
) -> dict[str, Any]:
    """Format a task for the Lovelace card."""
    assigned_to_id = task.get("assigned_to")
    return {
        "id": task["id"],
        "ref": task.get("ref"),
        "subject": task.get("subject", ""),
        "status": status_map.get(task.get("status"), "Unknown"),
        "status_id": task.get("status"),
        "assigned_to": members.get(assigned_to_id, "") if assigned_to_id else None,
        "assigned_to_id": assigned_to_id,
        "user_story_id": task.get("user_story"),
        "tags": [t[0] if isinstance(t, list) else t for t in task.get("tags", [])],
        "version": task.get("version"),
    }
