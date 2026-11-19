"""Витрина портфолио: одна точка входа для всех проектов.

Один процесс отдаёт:
  * витрину с записями                  (/)
  * страницы записей                     (/project/<slug>)
  * статические лендинги                 (/p/mayhem, /p/drop001, /p/usmanova)
  * сводный health-check                 (/api/health)
  * каталог в JSON                       (/api/catalog)
  * сервис согласования из проекта №1    (/svc/approval)
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import approval as approval_bridge
from . import catalog, config

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def _sp(value: int | float) -> str:
    """Тысячи через узкий неразрывный пробел — так цифры читаются в моно."""
    try:
        return f"{int(value):,}".replace(",", "\u2009")
    except (TypeError, ValueError):
        return str(value)


templates.env.filters["sp"] = _sp


def _plural(value, forms: str) -> str:
    """«1 работа / 2 работы / 11 работ» — форма выбирается по числу."""
    try:
        n = abs(int(value))
    except (TypeError, ValueError):
        return str(value)
    one, few, many = (forms.split(",") + ["", "", ""])[:3]
    if n % 10 == 1 and n % 100 != 11:
        word = one
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        word = few
    else:
        word = many
    return f"{n} {word}"


templates.env.filters["plural"] = _plural
templates.env.globals["css_version"] = int((config.STATIC_DIR / "style.css").stat().st_mtime)
templates.env.globals["built_at"] = datetime.now(timezone.utc).strftime("%d.%m.%Y")

_HEALTH_CACHE: dict[str, object] = {"at": 0.0, "data": None}

STATIC_LABELS = {
    "mayhem": "Лендинг Mayhem",
    "drop001": "Каталог ДРОП / 001",
    "usmanova": "Лендинг Кати Усмановой",
}


async def _probe(client: httpx.AsyncClient, url: str) -> tuple[bool, int | None]:
    started = time.perf_counter()
    try:
        res = await client.get(url, timeout=2.5)
        ms = int((time.perf_counter() - started) * 1000)
        return res.status_code < 400, ms
    except Exception:
        return False, None


async def collect_health(force: bool = False) -> dict:
    """Проверяет компоненты витрины. Кэш — 5 секунд."""
    now = time.time()
    if not force and _HEALTH_CACHE["data"] and now - float(_HEALTH_CACHE["at"]) < 5:
        return _HEALTH_CACHE["data"]  # type: ignore[return-value]

    components: list[dict] = []

    # Статические лендинги: достаточно наличия index.html в каталоге проекта.
    for slug, path in config.STATIC_PROJECTS.items():
        ok = (Path(path) / "index.html").is_file()
        components.append(
            {
                "name": STATIC_LABELS[slug],
                "path": f"/p/{slug}/",
                "role": "статика",
                "ok": ok,
                "ms": 0 if ok else None,
            }
        )

    # Стенды приложений: по одному HTTP-запросу на стенд.
    async with httpx.AsyncClient() as client:
        probes = [
            _probe(client, f"http://127.0.0.1:{port}{health_path}")
            for port, health_path in config.STAND_PROJECTS.values()
        ]
        probes.append(_probe(client, f"http://127.0.0.1:{config.IGRUSHKI_API_PORT}/api/health"))
        results = await asyncio.gather(*probes, return_exceptions=True)

    for (stand, (port, _)), result in zip(config.STAND_PROJECTS.items(), results):
        ok, ms = result if isinstance(result, tuple) else (False, None)
        components.append(
            {
                "name": config.STAND_TITLES[stand],
                "path": f":{port}",
                "role": "приложение",
                "ok": bool(ok),
                "ms": ms,
            }
        )

    api_ok, api_ms = results[-1] if isinstance(results[-1], tuple) else (False, None)
    components.append(
        {
            "name": "API «Игрушечек»",
            "path": f":{config.IGRUSHKI_API_PORT}",
            "role": "Fastify + WS",
            "ok": bool(api_ok),
            "ms": api_ms,
        }
    )
    components.append(
        {
            "name": "Сервис согласования",
            "path": "/svc/approval",
            "role": "API + SQLite",
            "ok": approval_bridge.MOUNTED,
            "ms": 1 if approval_bridge.MOUNTED else None,
        }
    )
    components.append(
        {"name": "Витрина", "path": "/", "role": "портал", "ok": True, "ms": 0}
    )

    data = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "components": components,
        "live": sum(1 for c in components if c["ok"]),
        "total": len(components),
    }
    _HEALTH_CACHE.update(at=now, data=data)
    return data


def create_app() -> FastAPI:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Портфолио Девяткин Даниил Дмитриевич", version="2.0.0",
                  docs_url=None, redoc_url=None)

    approval_bridge.mount(app)

    # Статические лендинги монтируются как настоящие пути, без прокси.
    for slug, directory in config.STATIC_PROJECTS.items():
        if (Path(directory) / "index.html").is_file():
            app.mount(f"/p/{slug}", StaticFiles(directory=str(directory), html=True), name=f"p-{slug}")

    app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if request.url.path.startswith(("/static/", "/p/")):
            response.headers.setdefault("Cache-Control", "public, max-age=3600")
        return response

    def _is_live(project: catalog.Project, health: dict) -> bool:
        ok_paths = {c["path"]: c["ok"] for c in health["components"]}
        if project.stand:
            port = project.stand_port
            return bool(port and ok_paths.get(f":{port}", False))
        if project.slug == "approval":
            return approval_bridge.MOUNTED
        return ok_paths.get(f"/p/{project.slug}/", False)

    def _open_url(project: catalog.Project, host: str) -> str:
        if project.stand and project.stand_port:
            return f"http://{host}:{project.stand_port}{project.stand_path}"
        if project.slug == "approval":
            return "/svc/approval/docs"
        return project.live or f"/p/{project.slug}/"

    def _unit(project: catalog.Project) -> str:
        return {
            "kartochki": "kartochki-stand",
            "igrushki": "igrushki-web",
            "maison": "maison-stand",
            "tattoo": "tattoo-stand",
        }.get(project.stand, "portfolio-platform")

    def _context(request: Request, projects: list, health: dict) -> dict:
        return {
            "request": request,
            "projects": projects,
            "totals": catalog.totals(projects),
            "port": config.PORTAL_PORT,
        }

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/api/health")
    async def api_health(force: bool = False):
        return await collect_health(force=force)

    @app.get("/api/catalog")
    async def api_catalog():
        projects = catalog.load()
        health = await collect_health()
        for project in projects:
            project.online = _is_live(project, health)
        return {
            "totals": catalog.totals(projects),
            "projects": [
                {
                    "slug": p.slug,
                    "num": p.num,
                    "name": p.name,
                    "kind": p.kind,
                    "brief": p.brief,
                    "role": p.role,
                    "stack": p.stack,
                    "loc": p.loc,
                    "files": p.files,
                    "mb": p.mb,
                    "commit": p.commit,
                    "last_commit": p.last_commit,
                    "github": p.github,
                    "live_path": p.live,
                    "stand": p.stand,
                    "stand_path": p.stand_path,
                    "parent": p.parent,
                    "live": p.online,
                }
                for p in projects
            ],
        }

    @app.get("/", response_class=HTMLResponse)
    async def portal(request: Request):
        projects = catalog.load()
        health = await collect_health()
        for project in projects:
            project.online = _is_live(project, health)
        return templates.TemplateResponse(request, "index.html", _context(request, projects, health))

    @app.get("/project/{slug}", response_class=HTMLResponse)
    async def project_page(slug: str, request: Request):
        if catalog.by_slug(slug) is None:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        projects = catalog.load()
        health = await collect_health()
        for p in projects:
            p.online = _is_live(p, health)
        project = next(p for p in projects if p.slug == slug)

        host = request.headers.get("host", "").split(":")[0] or "127.0.0.1"
        ctx = _context(request, projects, health)
        ctx.update(
            {
                "p": project,
                "open_url": _open_url(project, host),
                "unit": _unit(project),
            }
        )
        return templates.TemplateResponse(request, "project.html", ctx)

    return app


app = create_app()
