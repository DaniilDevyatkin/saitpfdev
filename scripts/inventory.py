#!/usr/bin/env python3
"""Инвентаризация проектов-источников.

Проходит по клонам в ../repos, считает файлы/строки/размер, определяет стек
и записывает итог в docs/inventory.json. Портал читает этот файл как источник
правды о проектах, поэтому цифры на витрине всегда совпадают с содержимым
репозиториев, а не набиты руками.
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = ROOT / "repos"
OUT = ROOT / "docs" / "inventory.json"

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".next", "dist", "build",
    ".venv", "venv", ".cache", ".pytest_cache", "coverage", ".turbo",
    "Cirk", "screenshots",
}
CODE_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".html": "HTML", ".css": "CSS", ".scss": "CSS",
    ".json": "JSON", ".md": "Markdown", ".sql": "SQL", ".sh": "Shell",
    ".yml": "YAML", ".yaml": "YAML", ".mjs": "JavaScript", ".cjs": "JavaScript",
}
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".webm", ".woff",
    ".woff2", ".ttf", ".otf", ".ico", ".pdf", ".zip", ".glb", ".mp3",
}

META = {
    "TestovoeDevyatkin": {
        "slug": "approval",
        "num": "01",
        "name": "Approval Service",
        "kind": "Backend-сервис",
        "brief": "Сервис согласования контента перед публикацией: заявки, решения approve/reject/cancel, аудит.",
        "role": "Спроектировал API, модель данных и машину состояний; покрыл тестами.",
        "accent": "#0540F2",
        "live": "/svc/approval/docs",
        "highlights": [
            "Идемпотентность POST через Idempotency-Key",
            "Права через X-Actions: read / create / decide / cancel",
            "Alembic-миграции и SQLite/Postgres через DATABASE_URL",
        ],
    },
    "TestovoeBug": {
        "slug": "drop001",
        "num": "02",
        "name": "ДРОП / 001",
        "kind": "Каталог-витрина",
        "brief": "Секция каталога премиального стритвира: 8 товаров, тёмная сцена, акцент на съёмке.",
        "role": "Собрал сетку, состояния карточек и входные анимации без библиотек.",
        "accent": "#C8553D",
        "live": "/p/drop001/",
        "highlights": [
            "Сетка 4×2 с адаптивом до одной колонки",
            "Hover-состояние карточки: подъём, оверлей, кнопка",
            "Отключение анимаций по prefers-reduced-motion",
        ],
    },
    "BelberryTestovoe": {
        "slug": "mayhem",
        "num": "03",
        "name": "Mayhem — Pony Paradise Tour",
        "kind": "Промо-лендинг",
        "brief": "Лендинг концерта: hero с афишей, блок о группе, три тарифа билетов, модалки.",
        "role": "Свёл визуальный язык афиши, собрал сцены и модальные окна на чистом JS.",
        "accent": "#B9FF3C",
        "live": "/p/mayhem/",
        "highlights": [
            "Одиннадцать CSS-слоёв: сцены, оверлеи, модалки",
            "Модалки и тарифы на ванильном JS без зависимостей",
            "Полоса прогресса скролла как навигационный акцент",
        ],
    },
    "Igrushki": {
        "slug": "igrushki",
        "num": "04",
        "name": "Игрушечки",
        "kind": "Многопользовательское веб-приложение",
        "brief": "Сетевые партии в шахматы, шашки, морской бой, дурака и пиксельбаттл: комнаты, рейтинги, чат.",
        "role": "Продукт целиком: Next.js-клиент, Fastify-API, WebSocket-каналы, SQLite, PWA.",
        "accent": "#7B61FF",
        "live": "/p/igrushki/",
        "highlights": [
            "WebSocket-каналы: партия, присутствие, пиксельбаттл",
            "Пять игр с серверной валидацией правил",
            "PWA, push-уведомления, модерация",
        ],
    },
    "TestovoeKartochki": {
        "slug": "kartochki",
        "num": "05",
        "name": "Карточки товаров",
        "kind": "Веб-приложение + API",
        "brief": "Генератор карточек товаров: каталог задач, превью, скачивание PNG, SVG-карточки.",
        "role": "Свёл FastAPI-рендер картинок с React-интерфейсом и кэшем превью.",
        "accent": "#0F8B8D",
        "live": "/p/kartochki/",
        "highlights": [
            "Серверный рендер превью и SVG на Pillow",
            "Кэш миниатюр 320 px под сетку",
            "React + Vite на клиенте, FastAPI на сервере",
        ],
    },
    "TestovoeUsmanova": {
        "slug": "usmanova",
        "num": "06",
        "name": "Катя Усманова",
        "kind": "Лендинг (GetCourse)",
        "brief": "Реплика лендинга фитнес-тренера: hero, блок о тренере, социальное доказательство.",
        "role": "Повторил вёрстку 1:1 по макету на Bootstrap + jQuery, собрал мобильную версию.",
        "accent": "#D96C8A",
        "live": "/p/usmanova/",
        "highlights": [
            "Три экрана, desktop и mobile, пиксель в пиксель",
            "Bootstrap + jQuery + CMS-разметка GetCourse",
            "Локальные изображения вместо внешних ссылок",
        ],
    },
}


def walk(repo: Path):
    files, loc, by_lang, size = 0, 0, Counter(), 0
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                size += p.stat().st_size
            except OSError:
                continue
            ext = p.suffix.lower()
            if ext in BINARY_EXT:
                continue
            files += 1
            lang = CODE_EXT.get(ext)
            if not lang:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            n = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            loc += n
            by_lang[lang] += n
    return files, loc, by_lang, size


def git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except Exception:
        return ""


def main() -> None:
    items = []
    for dirname, meta in META.items():
        repo = REPOS / dirname
        if not repo.exists():
            continue
        files, loc, by_lang, size = walk(repo)
        item = dict(meta)
        item.update(
            repo=dirname,
            origin=git(repo, "remote", "get-url", "origin"),
            commit=git(repo, "rev-parse", "--short", "HEAD"),
            last_commit=git(repo, "log", "-1", "--format=%cs"),
            files=files,
            loc=loc,
            mb=round(size / 1024 / 1024, 1),
            languages=dict(by_lang.most_common(5)),
            tests=sum(1 for p in repo.rglob("test_*.py")) + sum(
                1 for p in repo.rglob("*.test.ts*")
            ) if "node_modules" not in str(repo) else 0,
        )
        items.append(item)

    items.sort(key=lambda i: i["num"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"projects": items}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_loc = sum(i["loc"] for i in items)
    print(f"проектов: {len(items)}, строк кода: {total_loc}")
    for i in items:
        print(f"  {i['num']} {i['slug']:<12} {i['loc']:>6} строк  {i['files']:>4} файлов  {i['mb']:>6} МБ")


if __name__ == "__main__":
    main()
