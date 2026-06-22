"""Tests for the company-auth API router."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.company_auth import router
from app.company_auth.store import CompanyAuthStore
from app.dependencies import set_company_auth_store


@pytest.mark.asyncio
async def test_login_session_and_logout_flow(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    await store.ensure_bootstrap_admin(
        email="admin@example.com",
        display_name="Admin",
        password="TempPassword123!",
        bootstrap_file=tmp_path / "bootstrap.json",
    )
    set_company_auth_store(store)

    app = FastAPI()
    app.include_router(router, prefix="/api")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            bad = await client.post(
                "/api/company-auth/login",
                json={"email": "admin@example.com", "password": "wrong"},
            )
            assert bad.status_code == 401

            login = await client.post(
                "/api/company-auth/login",
                json={"email": "admin@example.com", "password": "TempPassword123!"},
            )
            assert login.status_code == 200
            token = login.json()["token"]
            assert token.startswith("fpi_sess_")

            current = await client.get(
                "/api/company-auth/session",
                headers={"X-FPI-Session": token},
            )
            assert current.status_code == 200
            assert current.json()["user"]["email"] == "admin@example.com"

            logout = await client.post(
                "/api/company-auth/logout",
                headers={"X-FPI-Session": token},
            )
            assert logout.status_code == 204

            expired = await client.get(
                "/api/company-auth/session",
                headers={"X-FPI-Session": token},
            )
            assert expired.status_code == 401
    finally:
        set_company_auth_store(None)
        await store.dispose()


@pytest.mark.asyncio
async def test_employee_login_revokes_previous_session(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    await store.create_user(
        email="employee@example.com",
        display_name="Employee",
        password="EmployeePassword123!",
        role="user",
    )
    set_company_auth_store(store)

    app = FastAPI()
    app.include_router(router, prefix="/api")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first = await client.post(
                "/api/company-auth/login",
                json={"email": "employee@example.com", "password": "EmployeePassword123!"},
                headers={"X-FPI-Device-ID": "device-a"},
            )
            assert first.status_code == 200
            first_token = first.json()["token"]

            second = await client.post(
                "/api/company-auth/login",
                json={"email": "employee@example.com", "password": "EmployeePassword123!"},
                headers={"X-FPI-Device-ID": "device-b"},
            )
            assert second.status_code == 200
            second_token = second.json()["token"]

            old_session = await client.get(
                "/api/company-auth/session",
                headers={"X-FPI-Session": first_token},
            )
            assert old_session.status_code == 401

            current_session = await client.get(
                "/api/company-auth/session",
                headers={"X-FPI-Session": second_token},
            )
            assert current_session.status_code == 200
    finally:
        set_company_auth_store(None)
        await store.dispose()


@pytest.mark.asyncio
async def test_admin_login_does_not_revoke_previous_session(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    await store.create_user(
        email="admin@example.com",
        display_name="Admin",
        password="AdminPassword123!",
        role="admin",
    )
    set_company_auth_store(store)

    app = FastAPI()
    app.include_router(router, prefix="/api")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first = await client.post(
                "/api/company-auth/login",
                json={"email": "admin@example.com", "password": "AdminPassword123!"},
            )
            assert first.status_code == 200
            first_token = first.json()["token"]

            second = await client.post(
                "/api/company-auth/login",
                json={"email": "admin@example.com", "password": "AdminPassword123!"},
            )
            assert second.status_code == 200
            second_token = second.json()["token"]

            first_session = await client.get(
                "/api/company-auth/session",
                headers={"X-FPI-Session": first_token},
            )
            assert first_session.status_code == 200

            second_session = await client.get(
                "/api/company-auth/session",
                headers={"X-FPI-Session": second_token},
            )
            assert second_session.status_code == 200
    finally:
        set_company_auth_store(None)
        await store.dispose()
