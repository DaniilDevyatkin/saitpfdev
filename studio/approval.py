"""Мост к сервису согласования из проекта TestovoeDevyatkin.

Проект не переписан: его FastAPI-приложение подключается подпрефиксом
`/svc/approval`, а база переезжает в общий каталог `data/`. Единственное,
что делает мост, — создаёт схему до первого запроса, потому что вложенные
приложения в Starlette не запускают собственный lifespan.
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI

from . import config

MOUNTED = False


def mount(parent: FastAPI) -> bool:
    global MOUNTED
    source = config.REPOS_DIR / "TestovoeDevyatkin"
    if not source.exists():
        return False

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Настройки сервиса читаются из окружения в момент импорта — выставляем до него.
    os.environ.setdefault("DATABASE_URL", config.database_url())

    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

    from app.database import Base, engine  # type: ignore
    from app.main import app as approval_app  # type: ignore

    Base.metadata.create_all(bind=engine)
    parent.mount("/svc/approval", approval_app)
    MOUNTED = True
    return True
