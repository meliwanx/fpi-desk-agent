"""Tests for centrally managed employee announcements."""

from __future__ import annotations

import types

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.api import admin as admin_api
from app.api import announcements as announcements_api
from app.auth.company_middleware import CompanyAuthMiddleware
from app.company_auth.store import CompanyAuthStore


@pytest.mark.asyncio
async def test_admin_publishes_all_user_announcement_and_employee_reads(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    admin = await store.create_user(
        email="admin@example.com",
        display_name="Admin",
        password="AdminPassword123!",
        role="admin",
    )
    employee = await store.create_user(
        email="employee@example.com",
        display_name="Employee",
        password="EmployeePassword123!",
        role="user",
    )
    admin_session = await store.create_session(admin.id)
    employee_session = await store.create_session(employee.id)

    app = FastAPI()
    app.state.settings = types.SimpleNamespace(company_auth_enabled=True)
    app.state.company_auth_store = store
    app.include_router(admin_api.router, prefix="/api")
    app.include_router(announcements_api.router, prefix="/api")
    app.add_middleware(CompanyAuthMiddleware)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            publish = await client.put(
                "/api/admin/announcement",
                headers={"X-FPI-Session": admin_session.token},
                json={
                    "enabled": True,
                    "content": "今天 18:00 前请完成日报。",
                    "target_user_ids": [],
                },
            )
            assert publish.status_code == 200
            published = publish.json()
            assert published["enabled"] is True
            assert published["content"] == "今天 18:00 前请完成日报。"
            assert published["target_user_ids"] == []
            assert any(user["id"] == employee.id for user in published["users"])

            current = await client.get(
                "/api/app/announcement",
                headers={"X-FPI-Session": employee_session.token},
            )
            assert current.status_code == 200
            payload = current.json()
            assert payload["announcement"]["id"] == published["id"]
            assert payload["announcement"]["content"] == "今天 18:00 前请完成日报。"

            read = await client.post(
                f"/api/app/announcement/{published['id']}/read",
                headers={"X-FPI-Session": employee_session.token},
            )
            assert read.status_code == 200
            assert read.json() == {"ok": True}

            hidden = await client.get(
                "/api/app/announcement",
                headers={"X-FPI-Session": employee_session.token},
            )
            assert hidden.status_code == 200
            assert hidden.json()["announcement"] is None
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_targeted_announcement_only_reaches_selected_employee(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    admin = await store.create_user(
        email="admin@example.com",
        display_name="Admin",
        password="AdminPassword123!",
        role="admin",
    )
    selected = await store.create_user(
        email="selected@example.com",
        display_name="Selected",
        password="EmployeePassword123!",
        role="user",
    )
    unselected = await store.create_user(
        email="unselected@example.com",
        display_name="Unselected",
        password="EmployeePassword123!",
        role="user",
    )
    admin_session = await store.create_session(admin.id)
    selected_session = await store.create_session(selected.id)
    unselected_session = await store.create_session(unselected.id)

    app = FastAPI()
    app.state.settings = types.SimpleNamespace(company_auth_enabled=True)
    app.state.company_auth_store = store
    app.include_router(admin_api.router, prefix="/api")
    app.include_router(announcements_api.router, prefix="/api")
    app.add_middleware(CompanyAuthMiddleware)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            publish = await client.put(
                "/api/admin/announcement",
                headers={"X-FPI-Session": admin_session.token},
                json={
                    "enabled": True,
                    "content": "请参加专项培训。",
                    "target_user_ids": [selected.id],
                },
            )
            assert publish.status_code == 200
            announcement_id = publish.json()["id"]

            selected_current = await client.get(
                "/api/app/announcement",
                headers={"X-FPI-Session": selected_session.token},
            )
            assert selected_current.status_code == 200
            assert selected_current.json()["announcement"]["id"] == announcement_id

            unselected_current = await client.get(
                "/api/app/announcement",
                headers={"X-FPI-Session": unselected_session.token},
            )
            assert unselected_current.status_code == 200
            assert unselected_current.json()["announcement"] is None
    finally:
        await store.dispose()
