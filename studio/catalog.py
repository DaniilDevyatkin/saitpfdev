"""Каталог записей витрины.

Источник правды — docs/inventory.json, который собирает scripts/inventory.py
из настоящих репозиториев. Каталог только обогащает эти данные ссылками и
статусами, поэтому цифры на витрине не расходятся с кодом.

Одна запись витрины = один проект или один самостоятельный раздел приложения:
четыре раздела «Карточек товаров» живут в одном репозитории, но это разные
заказы, поэтому у них отдельные записи и свои адреса внутри стенда.
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
    repo: str
    origin: str
    commit: str
    last_commit: str
    files: int
    loc: int
    mb: float
    live: str = ""
    stand: str = ""
    stand_path: str = "/"
    parent: str = ""
    highlights: list[str] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    online: bool = True  # вычисляется при запросе: отвечает ли компонент

    @property
    def github(self) -> str:
        return f"https://github.com/{config.GITHUB_ORG}/{self.repo}"

    @property
    def stack(self) -> list[str]:
        return [name for name, _ in sorted(self.languages.items(), key=lambda kv: -kv[1])][:3]

    @property
    def is_stand(self) -> bool:
        return bool(self.stand)

    @property
    def stand_port(self) -> int | None:
        entry = config.STAND_PROJECTS.get(self.stand)
        return entry[0] if entry else None


def load() -> list[Project]:
    path: Path = config.DOCS_DIR / "inventory.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    known = set(Project.__dataclass_fields__)
    projects: list[Project] = []
    for item in raw.get("projects", []):
        clean = {k: v for k, v in item.items() if k in known}
        projects.append(Project(**clean))
    return projects


def by_slug(slug: str) -> Project | None:
    for project in load():
        if project.slug == slug:
            return project
    return None


def totals(projects: list[Project]) -> dict[str, int | float]:
    """Итоги по уникальным репозиториям, а не по записям витрины."""
    unique: dict[str, Project] = {}
    for project in projects:
        unique.setdefault(project.repo, project)
    return {
        "projects": len(projects),
        "repos": len(unique),
        "loc": sum(p.loc for p in unique.values()),
        "files": sum(p.files for p in unique.values()),
        "mb": round(sum(p.mb for p in unique.values()), 1),
    }
