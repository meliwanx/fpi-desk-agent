"""Tests for company-auth API gating middleware."""

from __future__ import annotations

import types

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.auth.company_middleware import CompanyAuthMiddleware
from app.company_auth.store import CompanyAuthStore


@pytest.mark.asyncio
async def test_company_auth_middleware_blocks_api_until_login(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    await store.ensure_bootstrap_admin(
        email="admin@example.com",
        display_name="Admin",
        password="TempPassword123!",
        bootstrap_file=tmp_path / "bootstrap.json",
    )
    user = await store.authenticate("admin@example.com", "TempPassword123!")
    assert user is not None
    session = await store.create_session(user.id)

    app = FastAPI()
    app.state.settings = types.SimpleNamespace(company_auth_enabled=True)
    app.state.company_auth_store = store

    @app.get("/api/private")
    async def private():
        return {"ok": True}

    @app.post("/api/company-auth/login")
    async def login_public():
        return {"ok": True}

    @app.post("/shutdown")
    async def shutdown_public_to_company_auth():
        return {"ok": True}

    app.add_middleware(CompanyAuthMiddleware)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            unauthenticated = await client.get("/api/private")
            assert unauthenticated.status_code == 401

            login = await client.post("/api/company-auth/login")
            assert login.status_code == 200

            shutdown = await client.post("/shutdown")
            assert shutdown.status_code == 200

            authenticated = await client.get(
                "/api/private",
                headers={"X-FPI-Session": session.token},
            )
            assert authenticated.status_code == 200
    finally:
        await store.dispose()
