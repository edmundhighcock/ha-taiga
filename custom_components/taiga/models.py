"""Data models for the Taiga integration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaigaProjectData:
    """Data for a single tracked project."""

    project_id: int
    project_name: str
    project_slug: str
    userstory_statuses: list[dict] = field(default_factory=list)
    task_statuses: list[dict] = field(default_factory=list)
    user_stories: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    epics: list[dict] = field(default_factory=list)
    members: dict[int, str] = field(default_factory=dict)


@dataclass
class TaigaData:
    """Combined data for all tracked projects."""

    projects: dict[int, TaigaProjectData] = field(default_factory=dict)
