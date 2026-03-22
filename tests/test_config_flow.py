"""Tests for the Taiga config flow and options flow."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from custom_components.taiga.config_flow import TaigaOptionsFlow
from custom_components.taiga.const import (
    AUTH_METHOD_CREDENTIALS,
    CONF_AUTH_METHOD,
    CONF_PROJECTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


def _create_options_flow(data: dict, options: dict | None = None) -> TaigaOptionsFlow:
    """Create an OptionsFlow with a mocked config_entry property."""
    mock_entry = MagicMock()
    mock_entry.data = data
    mock_entry.options = options or {}

    flow = TaigaOptionsFlow(mock_entry)
    # Patch the computed property so it returns our mock entry
    type(flow).config_entry = PropertyMock(return_value=mock_entry)
    return flow


ENTRY_DATA = {
    "url": "http://localhost:8099",
    CONF_AUTH_METHOD: AUTH_METHOD_CREDENTIALS,
    "username": "testuser",
    "password": "testpass",
    CONF_PROJECTS: [{"id": 1, "name": "Test Project", "slug": "test-project"}],
}


class TestOptionsFlow:
    """Tests for TaigaOptionsFlow."""

    async def test_options_flow_shows_form(self):
        """Test the options flow shows a form with current scan interval."""
        flow = _create_options_flow(ENTRY_DATA)
        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    async def test_options_flow_default_scan_interval(self):
        """Test default scan interval is used when not set in options."""
        flow = _create_options_flow(ENTRY_DATA)
        result = await flow.async_step_init(user_input=None)

        schema_dict = dict(result["data_schema"].schema)
        for key in schema_dict:
            if hasattr(key, "schema") and key.schema == CONF_SCAN_INTERVAL:
                assert key.default() == DEFAULT_SCAN_INTERVAL
                return
        pytest.fail("CONF_SCAN_INTERVAL not found in schema")

    async def test_options_flow_saves_interval(self):
        """Test options flow saves the scan interval."""
        flow = _create_options_flow(ENTRY_DATA)
        result = await flow.async_step_init(
            user_input={CONF_SCAN_INTERVAL: 60}
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_SCAN_INTERVAL] == 60

    async def test_options_flow_uses_existing_option(self):
        """Test options flow shows current options value."""
        flow = _create_options_flow(ENTRY_DATA, options={CONF_SCAN_INTERVAL: 120})
        result = await flow.async_step_init(user_input=None)

        schema_dict = dict(result["data_schema"].schema)
        for key in schema_dict:
            if hasattr(key, "schema") and key.schema == CONF_SCAN_INTERVAL:
                assert key.default() == 120
                return
        pytest.fail("CONF_SCAN_INTERVAL not found in schema")

    async def test_options_flow_falls_back_to_data(self):
        """Test options flow falls back to data if no options set."""
        data_with_interval = {**ENTRY_DATA, CONF_SCAN_INTERVAL: 45}
        flow = _create_options_flow(data_with_interval)
        result = await flow.async_step_init(user_input=None)

        schema_dict = dict(result["data_schema"].schema)
        for key in schema_dict:
            if hasattr(key, "schema") and key.schema == CONF_SCAN_INTERVAL:
                assert key.default() == 45
                return
        pytest.fail("CONF_SCAN_INTERVAL not found in schema")
