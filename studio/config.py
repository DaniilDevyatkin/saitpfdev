"""Настройки платформы: пути, порты, окружение.

Все пути считаются от корня монорепозитория, поэтому платформа запускается
из любого каталога и не зависит от текущей рабочей директории.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPOS_DIR = BASE_DIR / "repos"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

# Куда платформа пишет свою SQLite-базу сервиса согласования.
APPROVAL_DB = DATA_DIR / "approval.db"

# Порт платформы и порты внешних стендов, которые она показывает.
PORTAL_PORT = int(os.environ.get("PORTAL_PORT", "8110"))
KARTOCHKI_PORT = int(os.environ.get("KARTOCHKI_PORT", "8200"))
IGRUSHKI_WEB_PORT = int(os.environ.get("IGRUSHKI_WEB_PORT", "3100"))
IGRUSHKI_API_PORT = int(os.environ.get("IGRUSHKI_API_PORT", "3301"))

# Статические лендинги: slug -> каталог с index.html.
STATIC_PROJECTS = {
    "mayhem": REPOS_DIR / "BelberryTestovoe",
    "drop001": REPOS_DIR / "TestovoeBug",
    "usmanova": REPOS_DIR / "TestovoeUsmanova",
}

# Стенды приложений: slug -> (порт, путь проверки здоровья).
STAND_PROJECTS = {
    "kartochki": (KARTOCHKI_PORT, "/api/tasks"),
    "igrushki": (IGRUSHKI_WEB_PORT, "/"),
}

GITHUB_ORG = "DaniilDevyatkin"

def database_url() -> str:
    """URL для сервиса согласования. По умолчанию — файл в data/."""
    return os.environ.get(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'approval.db'}"
    )
