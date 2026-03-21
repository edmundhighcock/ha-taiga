"""Fixtures for Taiga integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def auth_response() -> dict[str, Any]:
    """Return a mock auth response."""
    return load_fixture("auth_user_success.json")


@pytest.fixture
def projects_list() -> list[dict[str, Any]]:
    """Return a mock projects list."""
    return load_fixture("projects_list_success.json")


@pytest.fixture
def project_details() -> dict[str, Any]:
    """Return mock project details."""
    return load_fixture("project_details_success.json")


@pytest.fixture
def userstories_list() -> list[dict[str, Any]]:
    """Return a mock user stories list."""
    return load_fixture("userstories_list_success.json")


@pytest.fixture
def tasks_list() -> list[dict[str, Any]]:
    """Return a mock tasks list."""
    return load_fixture("tasks_list_success.json")


@pytest.fixture
def epics_list() -> list[dict[str, Any]]:
    """Return a mock epics list."""
    return load_fixture("epics_list_success.json")


@pytest.fixture
def userstory_statuses() -> list[dict[str, Any]]:
    """Return mock user story statuses."""
    return load_fixture("userstory_statuses.json")


@pytest.fixture
def task_statuses() -> list[dict[str, Any]]:
    """Return mock task statuses."""
    return load_fixture("task_statuses.json")
