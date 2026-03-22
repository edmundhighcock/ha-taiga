"""Config flow for the Taiga integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .api import TaigaAPI, TaigaAuthError, TaigaConnectionError
from .const import (
    AUTH_METHOD_CREDENTIALS,
    AUTH_METHOD_TOKEN,
    CONF_AUTH_METHOD,
    CONF_PROJECTS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class TaigaOptionsFlow(OptionsFlow):
    """Handle options for Taiga."""

    def __init__(self, config_entry) -> None:
        self._projects: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step for scan interval."""
        if user_input is not None:
            return await self._save_options(user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): vol.All(int, vol.Range(min=5, max=3600)),
                }
            ),
        )

    async def _save_options(self, user_input: dict[str, Any]) -> FlowResult:
        """Save updated options."""
        return self.async_create_entry(title="", data=user_input)


class TaigaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Taiga."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry) -> TaigaOptionsFlow:
        """Get the options flow handler."""
        return TaigaOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._url: str = DEFAULT_URL
        self._auth_method: str = AUTH_METHOD_CREDENTIALS
        self._username: str = ""
        self._password: str = ""
        self._token: str = ""
        self._user_id: int | None = None
        self._projects: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: URL and auth method."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._url = user_input[CONF_URL]
            self._auth_method = user_input[CONF_AUTH_METHOD]

            if self._auth_method == AUTH_METHOD_CREDENTIALS:
                return await self.async_step_credentials()
            return await self.async_step_token()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=DEFAULT_URL): str,
                    vol.Required(
                        CONF_AUTH_METHOD, default=AUTH_METHOD_CREDENTIALS
                    ): vol.In(
                        {
                            AUTH_METHOD_CREDENTIALS: "Username & Password",
                            AUTH_METHOD_TOKEN: "Application Token",
                        }
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle username/password authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            api = TaigaAPI(
                aiohttp.ClientSession(), self._url
            )
            try:
                await api.authenticate(self._username, self._password)
                self._user_id = api.user_id
                self._projects = await api.get_projects(member=self._user_id)
            except TaigaAuthError:
                errors["base"] = "invalid_auth"
            except TaigaConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            finally:
                await api._session.close()

            if not errors:
                return await self.async_step_projects()

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle application token authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._token = user_input[CONF_TOKEN]

            api = TaigaAPI(
                aiohttp.ClientSession(), self._url
            )
            api.set_token(self._token)
            try:
                await api.validate_token()
                self._user_id = api.user_id
                self._projects = await api.get_projects(member=self._user_id)
            except TaigaAuthError:
                errors["base"] = "invalid_auth"
            except TaigaConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during token validation")
                errors["base"] = "unknown"
            finally:
                await api._session.close()

            if not errors:
                return await self.async_step_projects()

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_projects(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle project selection."""
        if user_input is not None:
            selected_ids = user_input[CONF_PROJECTS]
            selected_projects = [
                {"id": p["id"], "name": p["name"], "slug": p["slug"]}
                for p in self._projects
                if str(p["id"]) in selected_ids
            ]

            if not selected_projects:
                return self.async_show_form(
                    step_id="projects",
                    data_schema=self._projects_schema(),
                    errors={"base": "no_projects_selected"},
                )

            data: dict[str, Any] = {
                CONF_URL: self._url,
                CONF_AUTH_METHOD: self._auth_method,
                CONF_PROJECTS: selected_projects,
            }
            if self._auth_method == AUTH_METHOD_CREDENTIALS:
                data[CONF_USERNAME] = self._username
                data[CONF_PASSWORD] = self._password
            else:
                data[CONF_TOKEN] = self._token

            title = ", ".join(p["name"] for p in selected_projects)
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="projects",
            data_schema=self._projects_schema(),
        )

    def _projects_schema(self) -> vol.Schema:
        project_options = {
            str(p["id"]): p["name"] for p in self._projects
        }
        return vol.Schema(
            {
                vol.Required(CONF_PROJECTS): vol.All(
                    [vol.In(project_options)],
                    vol.Length(min=1),
                ),
            }
        )
