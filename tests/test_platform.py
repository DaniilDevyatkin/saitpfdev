"""Приёмочные тесты платформы «Шесть».

Проверяют то, что видит человек: портал с реестром, статические лендинги,
страницы проектов, каталог в JSON, сводный health-check, защитные заголовки
и полный цикл согласования — создание заявки, идемпотентность, решение.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from studio.main import app

AUTH = {
    "X-Workspace-ID": "test_ws",
    "X-User-ID": "test_user",
    "X-Actions": "approval:read,approval:create,approval:decide,approval:cancel",
}
API = "/svc/approval/api/v1/workspaces/test_ws/approval-requests"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_portal_renders_all_projects(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert html.count('class="row"') == 6
    for name in ("Approval Service", "Игрушечки", "Карточки товаров", "Катя Усманова"):
        assert name in html
    assert "Согласование" in html


def test_portal_assets_are_served(client):
    html = client.get("/").text
    for asset in ("/static/portal.css", "/static/portal.js", "/static/favicon.svg"):
        assert asset in html
        assert client.get(asset).status_code == 200


def test_fonts_are_local(client):
    """Портал обязан рисоваться без интернета: шрифты лежат в static/fonts."""
    css = client.get("/static/portal.css").text
    assert "fonts/fonts.css" in css
    local = client.get("/static/fonts/fonts.css")
    assert local.status_code == 200
    assert "gstatic" not in local.text
    assert ".woff2" in local.text


@pytest.mark.parametrize("slug", ["mayhem", "drop001", "usmanova"])
def test_static_landing_is_mounted(client, slug):
    response = client.get(f"/p/{slug}/")
    assert response.status_code == 200
    assert "<html" in response.text.lower()


@pytest.mark.parametrize(
    "slug", ["approval", "drop001", "mayhem", "igrushki", "kartochki", "usmanova"]
)
def test_every_project_page_answers(client, slug):
    response = client.get(f"/project/{slug}")
    assert response.status_code == 200, slug
    assert "Исходники на GitHub" in response.text


def test_unknown_project_returns_404(client):
    assert client.get("/project/no-such-project").status_code == 404


def test_path_traversal_is_blocked(client):
    for path in ("/p/mayhem/%2e%2e/%2e%2e/etc/passwd", "/p/mayhem/../../etc/passwd"):
        response = client.get(path)
        assert response.status_code in {400, 404}
        assert "root:" not in response.text


def test_catalog_api_shape(client):
    data = client.get("/api/catalog").json()
    assert data["totals"]["projects"] == 6
    assert data["totals"]["loc"] > 30_000
    assert len(data["projects"]) == 6
    for item in data["projects"]:
        for key in ("slug", "num", "name", "stack", "loc", "github", "live"):
            assert key in item
        assert item["github"].startswith("https://github.com/DaniilDevyatkin/")


def test_health_reports_every_component(client):
    data = client.get("/api/health?force=true").json()
    names = [component["name"] for component in data["components"]]
    assert "Портал и реестр" in names
    assert "Сервис согласования" in names
    assert data["total"] == len(data["components"]) >= 8
    assert 0 <= data["live"] <= data["total"]


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"


def test_approval_requires_auth_headers(client):
    assert client.get(API).status_code == 403


def test_approval_full_cycle(client):
    key = str(uuid.uuid4())
    payload = {
        "sourceType": "publication",
        "sourceId": "TestovoeBug",
        "title": "Тестовая заявка платформы",
        "description": "Создана приёмочным тестом",
        "reviewerUserIds": ["test_user"],
    }
    created = client.post(API, json=payload, headers={**AUTH, "Idempotency-Key": key})
    assert created.status_code in (200, 201), created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    # Повтор с тем же ключом не создаёт дубль.
    again = client.post(API, json=payload, headers={**AUTH, "Idempotency-Key": key})
    assert again.json()["id"] == request_id

    approved = client.post(
        f"{API}/{request_id}/approve", json={"comment": "ок"}, headers=AUTH
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    listed = client.get(f"{API}?offset=0&limit=50", headers=AUTH)
    items = listed.json()["items"]
    assert any(item["id"] == request_id and item["status"] == "approved" for item in items)


def test_approval_cancel_flow(client):
    created = client.post(
        API,
        json={
            "sourceType": "edit",
            "sourceId": "TestovoeUsmanova",
            "title": "Заявка на отмену",
            "reviewerUserIds": ["test_user"],
        },
        headers={**AUTH, "Idempotency-Key": f"cancel-{uuid.uuid4()}"},
    )
    request_id = created.json()["id"]
    cancelled = client.post(
        f"{API}/{request_id}/cancel", json={"reason": "тест"}, headers=AUTH
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_review_page_redirect(client):
    response = client.get("/review", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].endswith("/#review")
