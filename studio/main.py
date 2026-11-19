"""Платформа «Шесть» — единая точка входа для шести проектов.

Один процесс отдаёт:
  * портал с реестром проектов            (/)
  * страницы проектов                      (/project/<slug>)
  * статические лендинги                   (/p/mayhem, /p/drop001, /p/usmanova)
  * сводный health-check                   (/api/health)
  * каталог в JSON                         (/api/catalog)
  * сервис согласования из проекта №1      (/svc/approval)
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
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
templates.env.globals["built_at"] = datetime.now(timezone.utc).strftime("%d.%m.%Y")

_HEALTH_CACHE: dict[str, object] = {"at": 0.0, "data": None}


async def _probe(client: httpx.AsyncClient, url: str) -> tuple[bool, int | None]:
    started = time.perf_counter()
    try:
        res = await client.get(url, timeout=2.0)
        ms = int((time.perf_counter() - started) * 1000)
        return res.status_code < 400, ms
    except Exception:
        return False, None


async def collect_health(force: bool = False) -> dict:
    """Проверяет все компоненты платформы. Кэш — 5 секунд."""
    now = time.time()
    if not force and _HEALTH_CACHE["data"] and now - float(_HEALTH_CACHE["at"]) < 5:
        return _HEALTH_CACHE["data"]  # type: ignore[return-value]

    components: list[dict] = []

    # Статические лендинги: достаточно наличия index.html в каталоге проекта.
    labels = {
        "mayhem": "Лендинг Mayhem",
        "drop001": "Каталог ДРОП / 001",
        "usmanova": "Лендинг Кати Усмановой",
    }
    for slug, path in config.STATIC_PROJECTS.items():
        index = Path(path) / "index.html"
        ok = index.is_file()
        components.append(
            {
                "name": labels[slug],
                "path": f"/p/{slug}/",
                "role": "статика",
                "ok": ok,
                "ms": 0 if ok else None,
            }
        )

    # Внешние стенды приложений.
    stand_labels = {
        "kartochki": ("Стенд «Карточки»", "приложение"),
        "igrushki": ("Стенд «Игрушечки»", "приложение"),
    }
    async with httpx.AsyncClient() as client:
        probes = []
        for slug, (port, health_path) in config.STAND_PROJECTS.items():
            probes.append(
                _probe(client, f"http://127.0.0.1:{port}{health_path}"),
            )
        probes.append(_probe(client, f"http://127.0.0.1:{config.IGRUSHKI_API_PORT}/api/health"))
        results = await asyncio.gather(*probes, return_exceptions=True)

    for (slug, (port, _)), result in zip(config.STAND_PROJECTS.items(), results):
        ok, ms = result if isinstance(result, tuple) else (False, None)
        name, role = stand_labels[slug]
        components.append(
            {
                "name": name,
                "path": f":{port}",
                "role": role,
                "ok": bool(ok),
                "ms": ms,
            }
        )

    components.append(
        {
            "name": "API «Игрушечек»",
            "path": f":{config.IGRUSHKI_API_PORT}",
            "role": "Fastify + WS",
            "ok": bool(results[-1][0]) if isinstance(results[-1], tuple) else False,
            "ms": results[-1][1] if isinstance(results[-1], tuple) else None,
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
        {"name": "Портал и реестр", "path": "/", "role": "портал", "ok": True, "ms": 0}
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

    app = FastAPI(title="Платформа «Шесть»", version="1.0.0", docs_url=None, redoc_url=None)

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
                    "live": p.online,
                }
                for p in projects
            ],
        }

    def _project_context(request: Request, projects, health):
        return {
            "request": request,
            "projects": projects,
            "totals": catalog.totals(projects),
            "health": health["components"],
            "live_count": sum(1 for p in projects if p.online),
            "all_live": all(p.online for p in projects),
            "port": config.PORTAL_PORT,
        }

    def _is_live(project, health) -> bool:
        ok_paths = {c["path"]: c["ok"] for c in health["components"]}
        if project.slug in config.STAND_PROJECTS:
            port = config.STAND_PROJECTS[project.slug][0]
            return ok_paths.get(f":{port}", False)
        if project.slug == "approval":
            return approval_bridge.MOUNTED
        return ok_paths.get(f"/p/{project.slug}/", False)

    @app.get("/", response_class=HTMLResponse)
    async def portal(request: Request):
        projects = catalog.load()
        health = await collect_health()
        for project in projects:
            project.online = _is_live(project, health)
        return templates.TemplateResponse(request, "index.html", _project_context(request, projects, health))

    @app.get("/project/{slug}", response_class=HTMLResponse)
    async def project_page(slug: str, request: Request):
        project = catalog.by_slug(slug)
        if project is None:
            raise HTTPException(status_code=404, detail="Проект не найден в реестре")
        projects = catalog.load()
        health = await collect_health()
        for p in projects:
            p.online = _is_live(p, health)
        project = next(p for p in projects if p.slug == slug)

        host = request.headers.get("host", "").split(":")[0] or "127.0.0.1"
        if project.slug in config.STAND_PROJECTS:
            port = config.STAND_PROJECTS[project.slug][0]
            open_url = f"http://{host}:{port}/"
            unit = "kartochki-stand" if project.slug == "kartochki" else "igrushki-web"
        elif project.slug == "approval":
            open_url = "/svc/approval/docs"
            unit = "portfolio-platform"
        else:
            open_url = f"/p/{project.slug}/"
            unit = "portfolio-platform"

        ctx = _project_context(request, projects, health)
        ctx.update({"p": project, "open_url": open_url, "unit": unit})
        return templates.TemplateResponse(request, "project.html", ctx)

    @app.get("/review")
    async def review_redirect():
        # Консоль живёт секцией на главной — прямой адрес ведёт туда.
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/#review", status_code=307)

    return app


app = create_app()
