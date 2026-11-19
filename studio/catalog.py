"""Каталог проектов платформы.

Источник правды — docs/inventory.json, который собирает scripts/inventory.py
из настоящих репозиториев. Каталог только обогащает эти данные ссылками,
статусами и группировкой, поэтому цифры на витрине не расходятся с кодом.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config


@dataclass
class Project:
    slug: str
    num: str
    name: str
    kind: str
    brief: str
    role: str
    accent: str
    live: str
    highlights: list[str]
    repo: str
    origin: str
    commit: str
    last_commit: str
    files: int
    loc: int
    mb: float
    languages: dict[str, int] = field(default_factory=dict)
    tests: int = 0
    stand: bool = False  # показать в iframe как живой стенд, а не как путь
    online: bool = True  # вычисляется при запросе: отвечает ли компонент

    @property
    def github(self) -> str:
        return f"https://github.com/{config.GITHUB_ORG}/{self.repo}"

    @property
    def stack(self) -> list[str]:
        return [name for name, _ in sorted(self.languages.items(), key=lambda kv: -kv[1])][:3]


def load() -> list[Project]:
    path: Path = config.DOCS_DIR / "inventory.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    projects: list[Project] = []
    for item in raw.get("projects", []):
        item = dict(item)
        item["stand"] = item["slug"] in config.STAND_PROJECTS
        projects.append(Project(**item))
    return projects


def by_slug(slug: str) -> Project | None:
    for project in load():
        if project.slug == slug:
            return project
    return None


def totals(projects: list[Project]) -> dict[str, int | float]:
    return {
        "projects": len(projects),
        "loc": sum(p.loc for p in projects),
        "files": sum(p.files for p in projects),
        "mb": round(sum(p.mb for p in projects), 1),
        "tests": sum(p.tests for p in projects),
    }
