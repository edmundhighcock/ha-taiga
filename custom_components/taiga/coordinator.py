"""DataUpdateCoordinator for the Taiga integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TaigaAPI, TaigaAuthError, TaigaConnectionError
from .const import CONF_PROJECTS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import TaigaData, TaigaProjectData

_LOGGER = logging.getLogger(__name__)


class TaigaCoordinator(DataUpdateCoordinator[TaigaData]):
    """Coordinator to fetch data from Taiga."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: TaigaAPI,
    ) -> None:
        scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> TaigaData:
        """Fetch data from Taiga for all tracked projects."""
        projects_config: list[dict[str, Any]] = self.config_entry.data[CONF_PROJECTS]
        projects: dict[int, TaigaProjectData] = {}

        try:
            for proj_config in projects_config:
                pid = proj_config["id"]
                projects[pid] = await self._fetch_project(proj_config)
        except TaigaAuthError:
            await self._reauthenticate()
            raise UpdateFailed("Re-authenticated with Taiga, will retry next cycle")
        except TaigaConnectionError as err:
            raise UpdateFailed(f"Cannot connect to Taiga: {err}") from err

        return TaigaData(projects=projects)

    async def _fetch_project(
        self, proj_config: dict[str, Any]
    ) -> TaigaProjectData:
        """Fetch all data for a single project in parallel."""
        pid = proj_config["id"]

        (
            us_statuses,
            task_statuses,
            stories,
            tasks,
            epics,
            project_detail,
        ) = await asyncio.gather(
            self.api.get_userstory_statuses(pid),
            self.api.get_task_statuses(pid),
            self.api.get_user_stories(pid),
            self.api.get_tasks(pid),
            self.api.get_epics(pid),
            self.api.get_project(pid),
        )

        members = {
            m["id"]: m.get("full_name") or m.get("username", "Unknown")
            for m in project_detail.get("members", [])
        }

        return TaigaProjectData(
            project_id=pid,
            project_name=proj_config["name"],
            project_slug=proj_config["slug"],
            userstory_statuses=us_statuses,
            task_statuses=task_statuses,
            user_stories=stories,
            tasks=tasks,
            epics=epics,
            members=members,
        )

    async def _reauthenticate(self) -> None:
        """Try to re-authenticate using stored credentials."""
        from .const import AUTH_METHOD_CREDENTIALS, CONF_AUTH_METHOD

        data = self.config_entry.data
        if data.get(CONF_AUTH_METHOD) == AUTH_METHOD_CREDENTIALS:
            try:
                await self.api.authenticate(
                    data["username"], data["password"]
                )
                _LOGGER.info("Re-authenticated with Taiga successfully")
            except Exception:
                _LOGGER.error("Failed to re-authenticate with Taiga")
