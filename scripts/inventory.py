#!/usr/bin/env python3
"""Инвентаризация проектов-источников.

Проходит по клонам в ../repos, считает файлы/строки/размер, читает последний
коммит и пишет docs/inventory.json. Витрина читает этот файл как источник правды,
поэтому цифры на ней совпадают с содержимым репозиториев.

Одна запись витрины = один проект или один самостоятельный раздел приложения:
четыре раздела «Карточек товаров» живут в одном репозитории, но показаны
отдельными записями, потому что это разные заказы.
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

META: dict[str, dict] = {
    "approval": {
        "num": "01",
        "name": "Approval Service",
        "kind": "Backend-сервис",
        "brief": "Сервис согласования контента перед публикацией: заявки, решения approve/reject/cancel, аудит.",
        "role": "Спроектировал API, модель данных и машину состояний; покрыл тестами.",
        "accent": "#0540F2",
        "repo": "TestovoeDevyatkin",
        "live": "/svc/approval/docs",
        "highlights": [
            "Идемпотентность POST через Idempotency-Key",
            "Права через X-Actions: read / create / decide / cancel",
            "Alembic-миграции и SQLite/Postgres через DATABASE_URL",
        ],
    },
    "drop001": {
        "num": "02",
        "name": "ДРОП / 001",
        "kind": "Каталог-витрина",
        "brief": "Секция каталога премиального стритвира: 8 товаров, тёмная сцена, акцент на съёмке.",
        "role": "Собрал сетку, состояния карточек и входные анимации без библиотек.",
        "accent": "#C8553D",
        "repo": "TestovoeBug",
        "live": "/p/drop001/",
        "highlights": [
            "Сетка 4×2 с адаптивом до одной колонки",
            "Hover-состояние карточки: подъём, оверлей, кнопка",
            "Отключение анимаций по prefers-reduced-motion",
        ],
    },
    "mayhem": {
        "num": "03",
        "name": "Mayhem — Pony Paradise Tour",
        "kind": "Промо-лендинг",
        "brief": "Лендинг концерта: hero с афишей, блок о группе, три тарифа билетов, модалки.",
        "role": "Свёл визуальный язык афиши, собрал сцены и модальные окна на чистом JS.",
        "accent": "#8FBF12",
        "repo": "BelberryTestovoe",
        "live": "/p/mayhem/",
        "highlights": [
            "Одиннадцать CSS-слоёв: сцены, оверлеи, модалки",
            "Модалки и тарифы на ванильном JS без зависимостей",
            "Полоса прогресса скролла как навигационный акцент",
        ],
    },
    "igrushki": {
        "num": "04",
        "name": "Игрушечки",
        "kind": "Многопользовательское приложение",
        "brief": "Сетевые партии в шахматы, шашки, морской бой, дурака и пиксельбаттл: комнаты, рейтинги, чат.",
        "role": "Продукт целиком: Next.js-клиент, Fastify-API, WebSocket-каналы, SQLite, PWA.",
        "accent": "#7B61FF",
        "repo": "Igrushki",
        "stand": "igrushki",
        "stand_path": "/",
        "highlights": [
            "WebSocket-каналы: партия, присутствие, пиксельбаттл",
            "Пять игр с серверной валидацией правил",
            "PWA, push-уведомления, модерация",
        ],
    },
    "gen": {
        "num": "05",
        "name": "Генерация карточек",
        "kind": "Раздел приложения · заказ",
        "brief": "Два набора товаров — электроника и одежда: сетка карточек, превью и скачивание файлов.",
        "role": "Серверный рендер, миниатюры и галерея с загрузкой на клиенте.",
        "accent": "#0F8B8D",
        "repo": "TestovoeKartochki",
        "stand": "kartochki",
        "stand_path": "/#/",
        "parent": "TestovoeKartochki",
        "highlights": [
            "Две задачи — два набора карточек",
            "Скачивание PNG одной кнопкой",
            "Миниатюры 320 px под сетку",
        ],
    },
    "ldlatte": {
        "num": "06",
        "name": "LD Latte",
        "kind": "Раздел приложения · заказ",
        "brief": "Капсула бренда: референсы съёмки, разбор кадров, карусели и презентация.",
        "role": "Собрал разбор референсов и галерею с лайтбоксом.",
        "accent": "#C9A227",
        "repo": "TestovoeKartochki",
        "stand": "kartochki",
        "stand_path": "/#/ldlatte",
        "parent": "TestovoeKartochki",
        "highlights": [
            "Текстовые блоки-обоснования по каждому кадру",
            "Карусели с лайтбоксом",
            "Выгрузка презентации",
        ],
    },
    "perevezrev": {
        "num": "07",
        "name": "ИП Переверзев",
        "kind": "Раздел приложения · заказ",
        "brief": "Карточки для бренда: четыре новые сетки и четыре старые карусели в одном экране.",
        "role": "Свёл восемь наборов изображений в две группы с лайтбоксом.",
        "accent": "#7A5230",
        "repo": "TestovoeKartochki",
        "stand": "kartochki",
        "stand_path": "/#/perevezrev",
        "parent": "TestovoeKartochki",
        "highlights": [
            "Сравнение «новое / старое» на одном экране",
            "Четыре сетки и четыре карусели",
            "Лайтбокс с клавиатурой",
        ],
    },
    "kwork1": {
        "num": "08",
        "name": "ЗаказКВОРК №1",
        "kind": "Раздел приложения · заказ",
        "brief": "Карточки и слайды заказа с фриланс-биржи: две карусели и скачивание презентации.",
        "role": "Собрал выдачу заказа: карточки, слайды, скачивание.",
        "accent": "#4B6FA8",
        "repo": "TestovoeKartochki",
        "stand": "kartochki",
        "stand_path": "/#/kwork1",
        "parent": "TestovoeKartochki",
        "highlights": [
            "Две карусели: карточки и слайды",
            "Скачивание файлов по клику",
            "Адаптив до 360 px",
        ],
    },
    "usmanova": {
        "num": "09",
        "name": "Катя Усманова",
        "kind": "Лендинг (GetCourse)",
        "brief": "Реплика лендинга фитнес-тренера: hero, блок о тренере, социальное доказательство.",
        "role": "Повторил вёрстку 1:1 по макету на Bootstrap + jQuery, собрал мобильную версию.",
        "accent": "#C05A78",
        "repo": "TestovoeUsmanova",
        "live": "/p/usmanova/",
        "highlights": [
            "Три экрана, desktop и mobile, пиксель в пиксель",
            "Bootstrap + jQuery + CMS-разметка GetCourse",
            "Локальные изображения вместо внешних ссылок",
        ],
    },
    "maison": {
        "num": "10",
        "name": "Maison Lumière Studio",
        "kind": "Сайт студии с бронированием",
        "brief": "Премиальная фотостудия: залы, бронирование слотов, отзывы, чат, админка и оплата.",
        "role": "Полный продукт: Express + MongoDB, React-клиент, JWT-админка, интеграция ЮKassa.",
        "accent": "#A67C52",
        "repo": "maison-lumiere-studio",
        "stand": "maison",
        "stand_path": "/",
        "highlights": [
            "Бронирование по слотам с проверкой пересечений",
            "Админка: заявки, клиенты, финансы, уборка",
            "Helmet, rate-limit, mongo-sanitize, hpp",
        ],
    },
    "tattoo": {
        "num": "11",
        "name": "TatuSait",
        "kind": "Сайт тату-студии",
        "brief": "Портфолио работ, мастера, запись на сеанс и прайс на удаление — FastAPI + React.",
        "role": "Собрал API с сидами и клиент на React + Tailwind, ограничил частоту запросов.",
        "accent": "#2F5D50",
        "repo": "TatuSait",
        "stand": "tattoo",
        "stand_path": "/",
        "highlights": [
            "Работы, мастера и удаление — три раздела каталога",
            "Форма записи с валидацией на сервере",
            "Security-headers и rate-limit через slowapi",
        ],
    },
}

# Порядок записей на витрине. Владелец задаёт его вручную: «03 — в самый конец,
# 01 — предпоследним». Номера присваиваются по этому порядку, а не по репозиториям.
ORDER = [
    "drop001",
    "igrushki",
    "gen",
    "ldlatte",
    "perevezrev",
    "kwork1",
    "usmanova",
    "maison",
    "tattoo",
    "approval",
    "mayhem",
]


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
    stats: dict[str, tuple[int, int, Counter, int]] = {}
    for repo_name in {meta["repo"] for meta in META.values()}:
        repo_path = REPOS / repo_name
        if repo_path.exists():
            stats[repo_name] = walk(repo_path)

    items = []
    ordered = [(slug, META[slug]) for slug in ORDER if slug in META]
    ordered += [(slug, meta) for slug, meta in META.items() if slug not in ORDER]
    for position, (slug, meta) in enumerate(ordered, start=1):
        repo_name = meta["repo"]
        repo_path = REPOS / repo_name
        files, loc, by_lang, size = stats.get(repo_name, (0, 0, Counter(), 0))
        item = {"slug": slug, "num": f"{position:02d}", **meta}
        item["num"] = f"{position:02d}"
        item.update(
            origin=git(repo_path, "remote", "get-url", "origin"),
            commit=git(repo_path, "rev-parse", "--short", "HEAD"),
            last_commit=git(repo_path, "log", "-1", "--format=%cs"),
            files=files,
            loc=loc,
            mb=round(size / 1024 / 1024, 1),
            languages=dict(by_lang.most_common(5)),
        )
        items.append(item)

    # порядок уже задан ORDER — сортировка не нужна
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"projects": items}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Итоги считаются по уникальным репозиториям: разделы одного приложения
    # не должны раздувать общий объём кода.
    total_loc = sum(stats[r][1] for r in stats)
    print(f"записей: {len(items)}, репозиториев: {len(stats)}, строк кода: {total_loc}")
    for i in items:
        marker = "↳" if i.get("parent") else " "
        print(f" {marker} {i['num']} {i['slug']:<12} {i['repo']:<22} {i['loc']:>6} строк")


if __name__ == "__main__":
    main()
