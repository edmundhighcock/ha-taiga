"""The Taiga integration."""

from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TaigaAPI
from .const import (
    AUTH_METHOD_CREDENTIALS,
    CONF_AUTH_METHOD,
    CONF_TOKEN,
    DOMAIN,
)
from .coordinator import TaigaCoordinator
from .services import async_setup_services, async_unload_services

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Taiga from a config entry."""
    session = async_get_clientsession(hass)
    api = TaigaAPI(session, entry.data[CONF_URL])

    # Authenticate
    if entry.data.get(CONF_AUTH_METHOD) == AUTH_METHOD_CREDENTIALS:
        await api.authenticate(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    else:
        api.set_token(entry.data[CONF_TOKEN])

    coordinator = TaigaCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register services on first entry
    if len(hass.data[DOMAIN]) == 1:
        await async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove services when last entry unloaded
    if not hass.data.get(DOMAIN):
        await async_unload_services(hass)

    return unload_ok
