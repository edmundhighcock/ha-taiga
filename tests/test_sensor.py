"""Tests for the Taiga sensor."""

from __future__ import annotations

import pytest

from custom_components.taiga.models import TaigaData, TaigaProjectData
from custom_components.taiga.sensor import _format_story, _format_task


@pytest.fixture
def sample_project_data(userstory_statuses, task_statuses, userstories_list, tasks_list, epics_list):
    """Create a TaigaProjectData from fixtures."""
    return TaigaProjectData(
        project_id=1,
        project_name="Test Project",
        project_slug="test-project",
        userstory_statuses=userstory_statuses,
        task_statuses=task_statuses,
        user_stories=userstories_list,
        tasks=tasks_list,
        epics=epics_list,
        members={19: "John Doe", 10: "Jane Smith"},
    )


def test_format_story(userstories_list, userstory_statuses):
    """Test formatting a user story for the Lovelace card."""
    story = userstories_list[0]
    status_map = {s["id"]: s["name"] for s in userstory_statuses}
    epic_map = {}

    result = _format_story(story, status_map, epic_map, {})

    assert result["id"] == 58190
    assert result["ref"] == 1
    assert result["subject"] == "Test story"
    assert result["version"] == 1
    assert result["tags"] == []
    assert result["assigned_to"] is None


def test_format_task(tasks_list, task_statuses):
    """Test formatting a task for the Lovelace card."""
    task = tasks_list[0]
    status_map = {s["id"]: s["name"] for s in task_statuses}
    members = {19: "John Doe"}

    result = _format_task(task, status_map, members)

    assert result["id"] == 1149
    assert result["ref"] == 31
    assert result["subject"] == "Customer personal data"
    assert result["assigned_to"] == "John Doe"
    assert result["assigned_to_id"] == 19
    assert result["version"] == 8
    assert result["user_story_id"] == 17
    assert "service catalog" in result["tags"]
    assert "customer" in result["tags"]


def test_format_story_with_epic():
    """Test formatting a story that belongs to an epic."""
    story = {
        "id": 1,
        "ref": 5,
        "subject": "Epic story",
        "status": 1,
        "assigned_to": None,
        "tags": [],
        "version": 1,
        "epics": [{"id": 10, "subject": "Big Feature"}],
    }
    status_map = {1: "New"}
    epic_map = {10: "Big Feature"}

    result = _format_story(story, status_map, epic_map, {})

    assert result["epic"] == "Big Feature"
    assert result["epic_id"] == 10


def test_format_story_with_list_tags():
    """Test formatting tags that come as [name, color] pairs."""
    story = {
        "id": 1,
        "ref": 5,
        "subject": "Tagged story",
        "status": 1,
        "assigned_to": None,
        "tags": [["bug", "#ff0000"], ["urgent", "#ff8800"]],
        "version": 1,
    }
    status_map = {1: "New"}

    result = _format_story(story, status_map, {}, {})

    assert result["tags"] == ["bug", "urgent"]
