#!/usr/bin/env python3
"""Собирает docs/INVENTORY.md из docs/inventory.json.

Человекочитаемая инвентаризация: что за проект, сколько в нём кода,
какие языки, где живёт. Таблица не пишется руками — только генерируется.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "inventory.json"
OUT = ROOT / "docs" / "INVENTORY.md"


def sp(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def main() -> None:
    projects = json.loads(DATA.read_text(encoding="utf-8"))["projects"]
    lines = [
        "# Инвентаризация проектов",
        "",
        "Файл собран скриптом `scripts/inventory.py` по клонам в `repos/`.",
        "Правки руками не сохраняются: перезапустите скрипт.",
        "",
        "| № | Проект | Тип | Строк | Файлов | Объём | Последний коммит |",
        "|---|--------|-----|-------|--------|-------|------------------|",
    ]
    for p in projects:
        lines.append(
            f"| {p['num']} | {p['name']} (`{p['repo']}`) | {p['kind']} | "
            f"{sp(p['loc'])} | {p['files']} | {p['mb']} МБ | {p['last_commit']} |"
        )
    total_loc = sum(p["loc"] for p in projects)
    total_files = sum(p["files"] for p in projects)
    lines += [
        "",
        f"Итого: **{len(projects)} проектов**, **{sp(total_loc)} строк кода**, "
        f"**{sp(total_files)} файлов**.",
        "",
        "## Языки по проектам",
        "",
    ]
    for p in projects:
        langs = ", ".join(f"{name} — {sp(lines_)}" for name, lines_ in p["languages"].items())
        lines.append(f"- **{p['name']}**: {langs or '—'}")
    lines += ["", "## Как запускается каждый проект", ""]
    for p in projects:
        where = p.get("live") or f"стенд {p.get('stand', '')}{p.get('stand_path', '/')}"
        lines.append(f"- **{p['name']}** — {where}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"записано {OUT}")


if __name__ == "__main__":
    main()
