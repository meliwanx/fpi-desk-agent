"""Admin and audit API tests."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.company_auth.store import CompanyAuthStore, CompanyModelEntry, CompanyModelPolicy, CompanyUser
from app.models.audit import (
    AuditAdminAction,
    AuditFile,
    AuditMessage,
    AuditPart,
    AuditRiskFinding,
    AuditSession,
    AuditToolCall,
    AuditUsage,
)

pytestmark = pytest.mark.asyncio


class _FakeCompanyStore:
    def __init__(self) -> None:
        self.users: list[CompanyUser] = []
        self.model_policy = CompanyModelPolicy(
            default_provider_id="custom_onlyme",
            default_model_id="gpt-5.5",
            models=[
                CompanyModelEntry(
                    provider_id="custom_onlyme",
                    id="gpt-5.5",
                    name="GPT-5.5",
                    protocol="openai_compatible",
                    base_url="https://sub2api.onlymeok.com/v1",
                    api_key="sk-default",
                )
            ],
        )
        self.update_policy = {
            "enabled": False,
            "latest_version": "",
            "min_supported_version": "",
            "force_update": False,
            "release_notes": "",
            "macos_asset_id": "",
            "windows_asset_id": "",
            "linux_asset_id": "",
            "default_asset_id": "",
            "macos_download_url": "",
            "windows_download_url": "",
            "linux_download_url": "",
            "default_download_url": "",
        }

    async def list_users(self) -> list[CompanyUser]:
        return self.users

    async def create_user(self, *, email: str, display_name: str, password: str, role: str) -> CompanyUser:
        user = CompanyUser(
            id=f"user-{len(self.users) + 1}",
            email=email,
            display_name=display_name,
            role=role,
            is_active=True,
        )
        self.users.append(user)
        return user

    async def get_model_policy(self) -> CompanyModelPolicy:
        return self.model_policy

    async def update_model_policy(
        self,
        *,
        default_provider_id: str,
        default_model_id: str,
        models: list[dict],
    ) -> CompanyModelPolicy:
        self.model_policy = CompanyModelPolicy(
            default_provider_id=default_provider_id,
            default_model_id=default_model_id,
            models=[
                CompanyModelEntry(
                    provider_id=str(model["provider_id"]),
                    id=str(model["id"]),
                    name=str(model.get("name") or model["id"]),
                    protocol=str(model.get("protocol") or "openai_compatible"),
                    base_url=str(model.get("base_url") or ""),
                    api_key=str(model.get("api_key") or "sk-existing"),
                )
                for model in models
            ],
        )
        return self.model_policy

    async def get_update_policy(self):
        return self.update_policy

    async def update_update_policy(self, **values):
        self.update_policy = values
        return self.update_policy


async def test_admin_can_create_and_list_company_users(app_client):
    app_client.app.state.company_auth_store = _FakeCompanyStore()
    app_client.app.middleware_stack = None

    async def inject_admin(request, call_next):
        request.state.company_user = CompanyUser(
            id="admin-1",
            email="admin",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    created = await app_client.post(
        "/api/admin/users",
        json={
            "email": "employee@example.com",
            "display_name": "Employee One",
            "password": "EmployeePassword123!",
            "role": "user",
        },
    )
    assert created.status_code == 201
    assert created.json()["email"] == "employee@example.com"

    listed = await app_client.get("/api/admin/users")
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": "user-1",
            "email": "employee@example.com",
            "display_name": "Employee One",
            "role": "user",
            "is_active": True,
        }
    ]


async def test_admin_can_update_company_model_policy(app_client):
    app_client.app.state.company_auth_store = _FakeCompanyStore()
    app_client.app.middleware_stack = None

    async def inject_admin(request, call_next):
        request.state.company_user = CompanyUser(
            id="admin-1",
            email="admin",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    updated = await app_client.put(
        "/api/admin/model-policy",
        json={
            "default_provider_id": "custom_backup",
            "default_model_id": "gpt-5.4",
            "models": [
                {
                    "provider_id": "custom_onlyme",
                    "id": "gpt-5.5",
                    "name": "GPT-5.5",
                    "protocol": "openai_compatible",
                    "base_url": "https://sub2api.onlymeok.com/v1",
                    "api_key": "sk-onlyme",
                },
                {
                    "provider_id": "custom_backup",
                    "id": "gpt-5.4",
                    "name": "GPT-5.4",
                    "protocol": "openai_compatible",
                    "base_url": "https://backup.example.com/v1",
                    "api_key": "sk-backup",
                },
            ],
        },
    )

    assert updated.status_code == 200
    assert updated.json()["default_provider_id"] == "custom_backup"
    assert [model["id"] for model in updated.json()["models"]] == ["gpt-5.5", "gpt-5.4"]
    assert updated.json()["models"][1]["protocol"] == "openai_compatible"
    assert updated.json()["models"][1]["base_url"] == "https://backup.example.com/v1"
    assert updated.json()["models"][1]["masked_key"] == "sk-b...ckup"
    assert "api_key" not in updated.json()["models"][1]

    loaded = await app_client.get("/api/admin/model-policy")
    assert loaded.status_code == 200
    assert loaded.json()["default_model_id"] == "gpt-5.4"
    assert loaded.json()["models"][0]["masked_key"] == "sk-o...lyme"


async def test_admin_can_update_company_app_update_policy(app_client):
    app_client.app.state.company_auth_store = _FakeCompanyStore()
    app_client.app.middleware_stack = None

    async def inject_admin(request, call_next):
        request.state.company_user = CompanyUser(
            id="admin-1",
            email="admin",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    updated = await app_client.put(
        "/api/admin/update-policy",
        json={
            "enabled": True,
            "latest_version": "1.4.0",
            "min_supported_version": "1.2.0",
            "force_update": True,
            "release_notes": "新增企业更新策略",
            "macos_download_url": "https://example.com/fpi-agent-1.4.0.dmg",
            "windows_download_url": "https://example.com/fpi-agent-1.4.0.exe",
            "linux_download_url": "",
            "default_download_url": "https://example.com/fpi-agent-1.4.0.zip",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["latest_version"] == "1.4.0"
    assert updated.json()["force_update"] is True

    loaded = await app_client.get("/api/admin/update-policy")
    assert loaded.status_code == 200
    assert loaded.json()["macos_download_url"].endswith(".dmg")


async def test_admin_can_upload_update_asset_and_bind_policy(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.state.settings.update_asset_storage_dir = str(tmp_path / "update_assets")
    app_client.app.middleware_stack = None

    async def inject_admin(request, call_next):
        request.state.company_user = CompanyUser(
            id="admin-1",
            email="admin@example.com",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    try:
        uploaded = await app_client.post(
            "/api/admin/update-assets/upload",
            data={
                "platform": "macos",
                "name": "macOS 1.4.0 正式安装包",
                "version": "v1.4.0",
                "signature": "signed-updater-package-signature",
            },
            files={
                "file": (
                    "FPI Agent 1.4.0.dmg",
                    b"installer-bytes",
                    "application/x-apple-diskimage",
                )
            },
        )

        assert uploaded.status_code == 200
        asset = uploaded.json()
        assert asset["platform"] == "macos"
        assert asset["name"] == "macOS 1.4.0 正式安装包"
        assert asset["version"] == "1.4.0"
        assert asset["original_filename"] == "FPI Agent 1.4.0.dmg"
        assert asset["size_bytes"] == len(b"installer-bytes")
        assert asset["download_count"] == 0
        assert asset["uploaded_by_email"] == "admin@example.com"
        assert asset["md5"] == hashlib.md5(b"installer-bytes").hexdigest()
        assert len(asset["sha256"]) == 64
        assert asset["signature"] == "signed-updater-package-signature"

        listed = await app_client.get("/api/admin/update-assets")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["id"] == asset["id"]

        saved_asset = await store.get_update_asset(asset["id"])
        assert saved_asset is not None
        stored_file = tmp_path / "update_assets" / saved_asset.stored_filename
        assert stored_file.read_bytes() == b"installer-bytes"

        updated = await app_client.put(
            "/api/admin/update-policy",
            json={
                "enabled": True,
                "latest_version": "1.4.0",
                "min_supported_version": "1.3.0",
                "force_update": True,
                "release_notes": "本地上传安装包",
                "macos_asset_id": asset["id"],
                "windows_asset_id": "",
                "linux_asset_id": "",
                "default_asset_id": "",
            },
        )

        assert updated.status_code == 200
        policy = updated.json()
        assert policy["macos_asset_id"] == asset["id"]
        assert policy["macos_asset"]["id"] == asset["id"]
        assert policy["macos_asset"]["name"] == "macOS 1.4.0 正式安装包"
        assert policy["macos_asset"]["md5"] == hashlib.md5(b"installer-bytes").hexdigest()
        assert policy["macos_asset"]["uploaded_by_display_name"] == "Admin"
        assert policy["macos_asset"]["signature"] == "signed-updater-package-signature"
    finally:
        await store.dispose()


async def test_admin_can_list_and_revoke_company_sessions(app_client, db, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.middleware_stack = None

    admin = CompanyUser(
        id="admin-1",
        email="admin@example.com",
        display_name="Admin",
        role="admin",
        is_active=True,
    )

    async def inject_admin(request, call_next):
        request.state.company_user = admin
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    try:
        employee = await store.create_user(
            email="employee@example.com",
            display_name="员工一",
            password="EmployeePassword123!",
            role="user",
        )
        session = await store.create_session(
            employee.id,
            device_id="desktop-001",
            device_name="财务部电脑",
            platform="windows",
            app_version="1.4.0",
            ip_address="203.0.113.10",
            user_agent="fpi-agent/1.4.0",
        )

        listed = await app_client.get("/api/admin/sessions")
        assert listed.status_code == 200
        payload = listed.json()
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["id"] == session.id
        assert item["user_email"] == "employee@example.com"
        assert item["device_name"] == "财务部电脑"
        assert item["platform"] == "windows"
        assert item["app_version"] == "1.4.0"
        assert item["is_online"] is True

        revoked = await app_client.post(
            f"/api/admin/sessions/{session.id}/revoke",
            json={"reason": "账号风险，需要重新登录"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["revoked_count"] == 1
        assert await store.get_session_user(session.token) is None

        actions = (await db.execute(select(AuditAdminAction))).scalars().all()
        assert [(action.action, action.target_type, action.target_id) for action in actions] == [
            ("revoke_company_session", "company_session", session.id)
        ]
        assert actions[0].metadata_json["reason"] == "账号风险，需要重新登录"

        action_log = await app_client.get("/api/admin/audit/admin-actions")
        assert action_log.status_code == 200
        action_item = action_log.json()["items"][0]
        assert action_item["actor_email"] == "admin@example.com"
        assert action_item["action"] == "revoke_company_session"
        assert action_item["target_id"] == session.id
        assert action_item["metadata"]["reason"] == "账号风险，需要重新登录"
    finally:
        await store.dispose()


async def test_admin_sessions_hide_offline_sessions_by_default(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.middleware_stack = None

    async def inject_admin(request, call_next):
        request.state.company_user = CompanyUser(
            id="admin-1",
            email="admin@example.com",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    try:
        employee = await store.create_user(
            email="employee@example.com",
            display_name="员工一",
            password="EmployeePassword123!",
            role="user",
        )
        online_session = await store.create_session(employee.id, device_name="在线设备")
        offline_session = await store.create_session(employee.id, device_name="离线设备")
        async with store.engine.begin() as conn:
            await conn.execute(
                store.sessions.update()
                .where(store.sessions.c.id == offline_session.id)
                .values(last_seen_at=datetime.now(timezone.utc) - timedelta(minutes=10))
            )

        listed = await app_client.get("/api/admin/sessions")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["items"]] == [online_session.id]

        listed_with_offline = await app_client.get("/api/admin/sessions?online_only=false")
        assert listed_with_offline.status_code == 200
        assert {item["id"] for item in listed_with_offline.json()["items"]} == {
            online_session.id,
            offline_session.id,
        }
    finally:
        await store.dispose()


async def test_admin_can_bulk_revoke_user_sessions(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.middleware_stack = None

    async def inject_admin(request, call_next):
        request.state.company_user = CompanyUser(
            id="admin-1",
            email="admin@example.com",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    try:
        first = await store.create_user(
            email="first@example.com",
            display_name="员工一",
            password="Password123!",
            role="user",
        )
        second = await store.create_user(
            email="second@example.com",
            display_name="员工二",
            password="Password123!",
            role="user",
        )
        first_session = await store.create_session(first.id)
        second_session = await store.create_session(second.id)

        response = await app_client.post(
            "/api/admin/sessions/revoke-bulk",
            json={"user_ids": [first.id, second.id], "reason": "批量安全复核"},
        )

        assert response.status_code == 200
        assert response.json()["revoked_count"] == 2
        assert await store.get_session_user(first_session.token) is None
        assert await store.get_session_user(second_session.token) is None
    finally:
        await store.dispose()


async def test_admin_summary_includes_activity_and_online_metrics(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.middleware_stack = None

    async def inject_admin(request, call_next):
        request.state.company_user = CompanyUser(
            id="admin-1",
            email="admin@example.com",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_admin)

    try:
        employee = await store.create_user(
            email="employee@example.com",
            display_name="员工一",
            password="Password123!",
            role="user",
        )
        await store.create_session(employee.id, platform="macos", app_version="1.4.0")

        response = await app_client.get("/api/admin/audit/summary")

        assert response.status_code == 200
        activity = response.json()["activity"]
        assert activity["daily_active_users"] == 1
        assert activity["online_users"] == 1
        assert activity["online_sessions"] == 1
        assert activity["series"][-1]["active_users"] == 1
    finally:
        await store.dispose()


async def test_employee_update_policy_marks_force_update_for_unsupported_version(app_client):
    class FakeCompanyStore(_FakeCompanyStore):
        async def get_update_policy(self):
            return {
                "enabled": True,
                "latest_version": "1.4.0",
                "min_supported_version": "1.3.0",
                "force_update": False,
                "release_notes": "必须升级到 1.4.0",
                "macos_download_url": "https://example.com/fpi-agent-1.4.0.dmg",
                "windows_download_url": "https://example.com/fpi-agent-1.4.0.exe",
                "linux_download_url": "",
                "default_download_url": "",
            }

    app_client.app.state.company_auth_store = FakeCompanyStore()
    app_client.app.middleware_stack = None

    async def inject_employee(request, call_next):
        request.state.company_user = CompanyUser(
            id="employee-1",
            email="10001",
            display_name="员工一",
            role="user",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_employee)

    response = await app_client.get(
        "/api/app/update-policy?current_version=1.2.9&platform=macos&arch=aarch64"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["update_available"] is True
    assert payload["force_update"] is True
    assert payload["download_url"].endswith(".dmg")


async def test_employee_update_policy_allows_current_version(app_client):
    class FakeCompanyStore(_FakeCompanyStore):
        async def get_update_policy(self):
            return {
                "enabled": True,
                "latest_version": "1.4.0",
                "min_supported_version": "1.2.0",
                "force_update": True,
                "release_notes": "新版",
                "macos_download_url": "https://example.com/fpi-agent-1.4.0.dmg",
                "windows_download_url": "https://example.com/fpi-agent-1.4.0.exe",
                "linux_download_url": "",
                "default_download_url": "",
            }

    app_client.app.state.company_auth_store = FakeCompanyStore()
    app_client.app.middleware_stack = None

    async def inject_employee(request, call_next):
        request.state.company_user = CompanyUser(
            id="employee-1",
            email="10001",
            display_name="员工一",
            role="user",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_employee)

    response = await app_client.get(
        "/api/app/update-policy?current_version=1.4.0&platform=windows&arch=x64"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["update_available"] is False
    assert payload["force_update"] is False
    assert payload["download_url"].endswith(".exe")


async def test_employee_update_policy_serves_local_asset_and_counts_downloads(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.state.settings.update_asset_storage_dir = str(tmp_path / "update_assets")
    app_client.app.middleware_stack = None

    async def inject_employee(request, call_next):
        request.state.company_user = CompanyUser(
            id="employee-1",
            email="10001",
            display_name="员工一",
            role="user",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_employee)

    storage_dir = tmp_path / "update_assets"
    storage_dir.mkdir()
    windows_bytes = b"windows-installer"
    default_bytes = b"default-installer"
    (storage_dir / "windows.exe").write_bytes(windows_bytes)
    (storage_dir / "default.zip").write_bytes(default_bytes)

    try:
        windows_asset = await store.create_update_asset(
            platform="windows",
            name="Windows 1.4.0 正式包",
            version="1.4.0",
            original_filename="FPI Agent Setup.exe",
            stored_filename="windows.exe",
            mime_type="application/vnd.microsoft.portable-executable",
            size_bytes=len(windows_bytes),
            sha256=hashlib.sha256(windows_bytes).hexdigest(),
            md5=hashlib.md5(windows_bytes).hexdigest(),
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )
        default_asset = await store.create_update_asset(
            platform="default",
            name="默认 1.4.0 包",
            version="1.4.0",
            original_filename="FPI Agent.zip",
            stored_filename="default.zip",
            mime_type="application/zip",
            size_bytes=len(default_bytes),
            sha256=hashlib.sha256(default_bytes).hexdigest(),
            md5=hashlib.md5(default_bytes).hexdigest(),
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )
        await store.update_update_policy(
            enabled=True,
            latest_version="1.4.0",
            min_supported_version="1.2.0",
            force_update=False,
            release_notes="本地包",
            windows_asset_id=windows_asset.id,
            default_asset_id=default_asset.id,
        )

        response = await app_client.get(
            "/api/app/update-policy?current_version=1.3.0&platform=windows&arch=x64"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["update_available"] is True
        assert payload["latest_package_name"] == "Windows 1.4.0 正式包"
        assert payload["latest_package_sha256"] == hashlib.sha256(windows_bytes).hexdigest()
        assert payload["latest_package_md5"] == hashlib.md5(windows_bytes).hexdigest()
        assert f"/download/{windows_asset.id}" in payload["download_url"]
        assert payload["download_filename"] == "FPI Agent Setup.exe"
        assert payload["download_sha256"] == hashlib.sha256(windows_bytes).hexdigest()

        current_hash = await app_client.get(
            "/api/app/update-policy"
            f"?current_version=1.3.0&platform=windows&arch=x64&current_package_sha256={windows_asset.sha256}"
        )
        assert current_hash.status_code == 200
        assert current_hash.json()["update_available"] is True

        same_version_different_hash = await app_client.get(
            "/api/app/update-policy"
            "?current_version=1.4.0&platform=windows&arch=x64&current_package_sha256="
            + ("0" * 64)
        )
        assert same_version_different_hash.status_code == 200
        assert same_version_different_hash.json()["update_available"] is False
        assert same_version_different_hash.json()["force_update"] is False

        download = await app_client.get(payload["download_url"])
        assert download.status_code == 200
        assert download.content == windows_bytes
        assert (await store.get_update_asset(windows_asset.id)).download_count == 1

        fallback = await app_client.get(
            "/api/app/update-policy?current_version=1.3.0&platform=linux&arch=x64"
        )
        assert fallback.status_code == 200
        assert f"/download/{default_asset.id}" in fallback.json()["download_url"]
    finally:
        await store.dispose()


async def test_employee_update_manifest_serves_signed_tauri_assets(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.state.settings.update_asset_storage_dir = str(tmp_path / "update_assets")
    app_client.app.middleware_stack = None

    async def inject_employee(request, call_next):
        request.state.company_user = CompanyUser(
            id="employee-1",
            email="10001",
            display_name="员工一",
            role="user",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_employee)

    storage_dir = tmp_path / "update_assets"
    storage_dir.mkdir()
    mac_bytes = b"macos-updater-archive"
    windows_bytes = b"windows-updater-installer"
    (storage_dir / "fpi-agent.app.tar.gz").write_bytes(mac_bytes)
    (storage_dir / "fpi-agent-setup.exe").write_bytes(windows_bytes)

    try:
        mac_asset = await store.create_update_asset(
            platform="macos",
            version="1.4.0",
            original_filename="fpi-agent_1.4.0_arm64.app.tar.gz",
            stored_filename="fpi-agent.app.tar.gz",
            mime_type="application/gzip",
            size_bytes=len(mac_bytes),
            sha256=hashlib.sha256(mac_bytes).hexdigest(),
            signature="macos-updater-signature",
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )
        windows_asset = await store.create_update_asset(
            platform="windows",
            version="1.4.0",
            original_filename="fpi-agent_1.4.0_x64-setup.exe",
            stored_filename="fpi-agent-setup.exe",
            mime_type="application/vnd.microsoft.portable-executable",
            size_bytes=len(windows_bytes),
            sha256=hashlib.sha256(windows_bytes).hexdigest(),
            signature="windows-updater-signature",
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )
        await store.update_update_policy(
            enabled=True,
            latest_version="1.4.0",
            min_supported_version="1.2.0",
            force_update=True,
            release_notes="应用内更新包",
            macos_asset_id=mac_asset.id,
            windows_asset_id=windows_asset.id,
        )

        response = await app_client.get(
            "/api/app/update-manifest/darwin/aarch64/1.3.0?bundle=app"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["version"] == "1.4.0"
        assert payload["notes"] == "应用内更新包"
        assert payload["pub_date"]
        assert payload["platforms"]["darwin-aarch64-app"]["signature"] == "macos-updater-signature"
        assert mac_asset.id in payload["platforms"]["darwin-aarch64-app"]["url"]
        assert payload["platforms"]["darwin-aarch64"]["signature"] == "macos-updater-signature"
        assert payload["platforms"]["windows-x86_64-nsis"]["signature"] == "windows-updater-signature"
        assert windows_asset.id in payload["platforms"]["windows-x86_64-nsis"]["url"]

        current = await app_client.get(
            "/api/app/update-manifest/darwin/aarch64/1.4.0?bundle=app"
        )
        assert current.status_code == 204
    finally:
        await store.dispose()


async def test_employee_update_policy_uses_selected_asset_version_not_hash(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.state.settings.update_asset_storage_dir = str(tmp_path / "update_assets")
    app_client.app.middleware_stack = None

    async def inject_employee(request, call_next):
        request.state.company_user = CompanyUser(
            id="employee-1",
            email="10001",
            display_name="员工一",
            role="user",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_employee)

    storage_dir = tmp_path / "update_assets"
    storage_dir.mkdir()
    windows_bytes = b"windows-installer"
    (storage_dir / "windows.exe").write_bytes(windows_bytes)

    try:
        windows_asset = await store.create_update_asset(
            platform="windows",
            name="Windows hotfix rebuild",
            version="1.3.0",
            original_filename="FPI Agent Setup.exe",
            stored_filename="windows.exe",
            mime_type="application/vnd.microsoft.portable-executable",
            size_bytes=len(windows_bytes),
            sha256=hashlib.sha256(windows_bytes).hexdigest(),
            md5=hashlib.md5(windows_bytes).hexdigest(),
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )
        await store.update_update_policy(
            enabled=True,
            latest_version="1.4.0",
            min_supported_version="",
            force_update=True,
            release_notes="macOS already moved ahead",
            windows_asset_id=windows_asset.id,
        )

        response = await app_client.get(
            "/api/app/update-policy"
            "?current_version=1.3.0&platform=windows&arch=x64&current_package_sha256="
            + ("0" * 64)
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["latest_version"] == "1.3.0"
        assert payload["update_available"] is False
        assert payload["force_update"] is False
        assert payload["latest_package_sha256"] == windows_asset.sha256

        current = await app_client.get(
            "/api/app/update-policy"
            f"?current_version=1.3.0&platform=windows&arch=x64&current_package_sha256={windows_asset.sha256}"
        )
        assert current.status_code == 200
        assert current.json()["update_available"] is False
        assert current.json()["force_update"] is False
    finally:
        await store.dispose()


async def test_employee_can_submit_feedback_and_admin_can_review_image(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.state.settings.feedback_storage_dir = str(tmp_path / "feedback_uploads")
    app_client.app.middleware_stack = None

    async def inject_company_user(request, call_next):
        role = request.headers.get("x-test-company-role", "user")
        request.state.company_user = CompanyUser(
            id=f"{role}-1",
            email=f"{role}@example.com",
            display_name="管理员" if role == "admin" else "员工一",
            role=role,
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_company_user)

    image_bytes = b"\x89PNG\r\nfeedback-image"
    try:
        created = await app_client.post(
            "/api/feedback",
            data={"description": "聊天窗口无法上传截图"},
            files={"image": ("screen.png", image_bytes, "image/png")},
        )

        assert created.status_code == 200
        payload = created.json()
        assert payload["description"] == "聊天窗口无法上传截图"
        assert payload["user_email"] == "user@example.com"
        assert payload["image_original_filename"] == "screen.png"
        assert payload["image_size_bytes"] == len(image_bytes)

        listed = await app_client.get(
            "/api/admin/feedback",
            headers={"x-test-company-role": "admin"},
        )
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == payload["id"]
        assert items[0]["user_display_name"] == "员工一"
        assert items[0]["description"] == "聊天窗口无法上传截图"
        assert items[0]["image_download_url"].endswith(f"/api/admin/feedback/{payload['id']}/image")

        image = await app_client.get(
            items[0]["image_download_url"],
            headers={"x-test-company-role": "admin"},
        )
        assert image.status_code == 200
        assert image.content == image_bytes

        deleted = await app_client.delete(
            f"/api/admin/feedback/{payload['id']}",
            headers={"x-test-company-role": "admin"},
        )
        assert deleted.status_code == 204

        listed_after_delete = await app_client.get(
            "/api/admin/feedback",
            headers={"x-test-company-role": "admin"},
        )
        assert listed_after_delete.status_code == 200
        assert listed_after_delete.json()["items"] == []

        image_after_delete = await app_client.get(
            items[0]["image_download_url"],
            headers={"x-test-company-role": "admin"},
        )
        assert image_after_delete.status_code == 404
        assert list((tmp_path / "feedback_uploads").glob("*")) == []
    finally:
        await store.dispose()


async def test_feedback_requires_description(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.state.settings.feedback_storage_dir = str(tmp_path / "feedback_uploads")
    app_client.app.middleware_stack = None

    async def inject_employee(request, call_next):
        request.state.company_user = CompanyUser(
            id="user-1",
            email="user@example.com",
            display_name="员工一",
            role="user",
            is_active=True,
        )
        return await call_next(request)

    app_client.app.middleware("http")(inject_employee)

    try:
        response = await app_client.post("/api/feedback", data={"description": "   "})

        assert response.status_code == 400
        assert "description" in response.text
    finally:
        await store.dispose()


async def test_audit_ingest_and_admin_query(app_client, session_factory, tmp_path):
    app_client.app.state.settings.audit_file_storage_dir = str(tmp_path / "audit_uploads")
    app_client.app.middleware_stack = None

    async def inject_company_user(request, call_next):
        role = request.headers.get("x-test-company-role", "user")
        if role == "admin":
            request.state.company_user = CompanyUser(
                id="admin-1",
                email="admin",
                display_name="Admin",
                role="admin",
                is_active=True,
            )
        else:
            request.state.company_user = CompanyUser(
                id="employee-1",
                email="employee@example.com",
                display_name="Employee One",
                role="user",
                is_active=True,
            )
        return await call_next(request)

    app_client.app.middleware("http")(inject_company_user)

    ingest = await app_client.post(
        "/api/audit/ingest",
        json={
            "sessions": [
                {
                    "id": "local-session-1",
                    "title": "Quarterly report",
                    "workspace": "/Users/employee/work/acme",
                    "model_id": "gpt-5.5",
                    "provider_id": "custom_onlyme",
                }
            ],
            "messages": [
                {
                    "id": "local-message-1",
                    "session_id": "local-session-1",
                    "role": "user",
                    "data": {"role": "user", "agent": "build"},
                }
            ],
            "parts": [
                {
                    "id": "local-part-step-start",
                    "message_id": "local-message-1",
                    "session_id": "local-session-1",
                    "data": {"type": "step-start", "step": 1},
                },
                {
                    "id": "local-part-1",
                    "message_id": "local-message-1",
                    "session_id": "local-session-1",
                    "data": {"type": "text", "text": "请分析这个销售表"},
                },
                {
                    "id": "local-part-2",
                    "message_id": "local-message-1",
                    "session_id": "local-session-1",
                    "data": {
                        "type": "file",
                        "name": "sales.xlsx",
                        "path": "/Users/employee/Desktop/sales.xlsx",
                        "source": "referenced",
                        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "size": 1024,
                    },
                },
            ],
        },
    )
    assert ingest.status_code == 200
    assert ingest.json() == {"sessions": 1, "messages": 1, "parts": 3}

    async with session_factory() as db:
        sessions = list((await db.execute(AuditSession.__table__.select())).mappings())
        messages = list((await db.execute(AuditMessage.__table__.select())).mappings())
        parts = list((await db.execute(AuditPart.__table__.select())).mappings())
        files = list((await db.execute(AuditFile.__table__.select())).mappings())

    assert sessions[0]["user_email"] == "employee@example.com"
    assert sessions[0]["workspace"] == "/Users/employee/work/acme"
    assert messages[0]["role"] == "user"
    assert {part["part_type"] for part in parts} == {"step-start", "text", "file"}
    assert files[0]["local_part_id"] == "local-part-2"
    assert files[0]["content_uploaded"] is False

    upload = await app_client.post(
        "/api/audit/files/upload",
        data={"part_id": "local-part-2"},
        files={"file": ("sales.xlsx", b"sales-data", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 200
    assert upload.json()["uploaded"] is True

    audit_sessions = await app_client.get(
        "/api/admin/audit/sessions",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert audit_sessions.status_code == 200
    body = audit_sessions.json()
    assert body["items"][0]["user_email"] == "employee@example.com"
    assert body["items"][0]["title"] == "Quarterly report"

    transcript = await app_client.get(
        "/api/admin/audit/sessions/local-session-1/messages",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert transcript.status_code == 200
    transcript_body = transcript.json()
    assert {part["type"] for part in transcript_body["messages"][0]["parts"]} == {"text", "file"}
    assert transcript_body["messages"][0]["parts"][0]["data"]["text"] == "请分析这个销售表"
    file_part = next(part for part in transcript_body["messages"][0]["parts"] if part["type"] == "file")
    assert file_part["file"]["content_uploaded"] is True
    assert file_part["file"]["download_url"] == "/api/admin/audit/files/local-part-2/download"

    entries = await app_client.get(
        "/api/admin/audit/entries?limit=20",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert entries.status_code == 200
    assert {item["type"] for item in entries.json()["items"]} == {"text", "file"}

    download = await app_client.get(
        "/api/admin/audit/files/local-part-2/download",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert download.status_code == 200
    assert download.content == b"sales-data"


async def test_enterprise_audit_tracks_usage_tools_risks_and_admin_actions(
    app_client,
    session_factory,
    tmp_path,
):
    app_client.app.state.settings.audit_file_storage_dir = str(tmp_path / "audit_uploads")
    app_client.app.middleware_stack = None

    async def inject_company_user(request, call_next):
        role = request.headers.get("x-test-company-role", "user")
        if role == "admin":
            request.state.company_user = CompanyUser(
                id="admin-1",
                email="admin",
                display_name="Admin",
                role="admin",
                is_active=True,
            )
        else:
            request.state.company_user = CompanyUser(
                id="employee-1",
                email="employee@example.com",
                display_name="Employee One",
                role="user",
                is_active=True,
            )
        return await call_next(request)

    app_client.app.middleware("http")(inject_company_user)

    ingest = await app_client.post(
        "/api/audit/ingest",
        json={
            "sessions": [
                {
                    "id": "local-session-observe",
                    "title": "查 VPN 配置",
                    "workspace": "/Users/employee/work/ops",
                    "model_id": "gpt-5.5",
                    "provider_id": "custom_onlyme",
                    "source_client_id": "mac-client-1",
                }
            ],
            "messages": [
                {
                    "id": "local-message-user",
                    "session_id": "local-session-observe",
                    "role": "user",
                    "data": {"role": "user"},
                },
                {
                    "id": "local-message-assistant",
                    "session_id": "local-session-observe",
                    "role": "assistant",
                    "data": {
                        "role": "assistant",
                        "model_id": "claude-sonnet-4",
                        "provider_id": "anthropic",
                    },
                },
            ],
            "parts": [
                {
                    "id": "local-part-secret-text",
                    "message_id": "local-message-user",
                    "session_id": "local-session-observe",
                    "data": {
                        "type": "text",
                        "text": "VPN 订阅链接 https://gaosu.click/iqiyi/abcdef 以及 key sk-test-secret",
                    },
                },
                {
                    "id": "local-part-tool",
                    "message_id": "local-message-assistant",
                    "session_id": "local-session-observe",
                    "data": {
                        "type": "tool",
                        "tool": "read",
                        "call_id": "call-read-1",
                        "state": {
                            "status": "completed",
                            "input": {"file_path": "/Users/employee/.config/clash/profiles.yaml"},
                            "output": "proxy subscription: https://gaosu.click/iqiyi/abcdef",
                            "title": "profiles.yaml",
                        },
                    },
                },
                {
                    "id": "local-part-usage",
                    "message_id": "local-message-assistant",
                    "session_id": "local-session-observe",
                    "data": {
                        "type": "step-finish",
                        "reason": "stop",
                        "tokens": {
                            "input": 1000,
                            "output": 200,
                            "reasoning": 30,
                            "cache_read": 40,
                            "cache_write": 5,
                            "total": 1275,
                        },
                        "cost": 0.0123,
                    },
                },
                {
                    "id": "local-part-file",
                    "message_id": "local-message-user",
                    "session_id": "local-session-observe",
                    "data": {
                        "type": "file",
                        "name": "vpn.txt",
                        "path": str(tmp_path / "vpn.txt"),
                        "source": "uploaded",
                        "mime_type": "text/plain",
                        "size": 12,
                    },
                },
            ],
        },
    )
    assert ingest.status_code == 200

    async with session_factory() as db:
        usage_rows = list((await db.execute(AuditUsage.__table__.select())).mappings())
        tool_rows = list((await db.execute(AuditToolCall.__table__.select())).mappings())
        risk_rows = list((await db.execute(AuditRiskFinding.__table__.select())).mappings())

    assert usage_rows[0]["input_tokens"] == 1000
    assert usage_rows[0]["total_tokens"] == 1275
    assert usage_rows[0]["cost"] == 0.0123
    assert tool_rows[0]["tool_name"] == "read"
    assert tool_rows[0]["status"] == "completed"
    assert "profiles.yaml" in tool_rows[0]["output_preview"]
    assert {row["kind"] for row in risk_rows} >= {"api_key", "vpn_subscription_url"}

    summary = await app_client.get(
        "/api/admin/audit/summary",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert summary.status_code == 200
    assert summary.json()["usage"]["total_tokens"] == 1275
    assert summary.json()["tool_calls"]["total"] == 1
    assert summary.json()["risks"]["open"] >= 2

    risks = await app_client.get(
        "/api/admin/audit/risks?severity=high",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert risks.status_code == 200
    assert risks.json()["items"][0]["session_id"] == "local-session-observe"

    tool_calls = await app_client.get(
        "/api/admin/audit/tool-calls?tool=read",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert tool_calls.status_code == 200
    assert tool_calls.json()["items"][0]["call_id"] == "call-read-1"

    transcript = await app_client.get(
        "/api/admin/audit/sessions/local-session-observe/messages",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert transcript.status_code == 200
    assistant_message = next(message for message in transcript.json()["messages"] if message["role"] == "assistant")
    assert assistant_message["model_id"] == "claude-sonnet-4"
    assert assistant_message["provider_id"] == "anthropic"

    tool_analytics = await app_client.get(
        "/api/admin/audit/analytics/tools",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert tool_analytics.status_code == 200
    assert tool_analytics.json()["total_calls"] == 1
    assert tool_analytics.json()["tool_list"][0]["tool_name"] == "read"
    assert tool_analytics.json()["tool_list"][0]["success_count"] == 1

    user_analytics = await app_client.get(
        "/api/admin/audit/analytics/users",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert user_analytics.status_code == 200
    assert user_analytics.json()["total_users"] == 1
    assert user_analytics.json()["user_list"][0]["message_count"] == 2
    assert user_analytics.json()["user_list"][0]["total_tokens"] == 1275

    model_analytics = await app_client.get(
        "/api/admin/audit/analytics/models",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert model_analytics.status_code == 200
    assert model_analytics.json()["model_list"][0]["message_count"] == 2
    assert model_analytics.json()["model_list"][0]["total_tokens"] == 1275

    entries = await app_client.get(
        "/api/admin/audit/entries?limit=20",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert entries.status_code == 200
    entry_payload = entries.json()
    assert entry_payload["total"] == 4
    assert {item["type"] for item in entry_payload["items"]} == {"text", "tool", "step-finish", "file"}
    assert entry_payload["items"][0]["session"]["title"] == "查 VPN 配置"

    (tmp_path / "vpn.txt").write_text("vpn evidence", encoding="utf-8")
    upload = await app_client.post(
        "/api/audit/files/upload",
        data={"part_id": "local-part-file"},
        files={"file": ("vpn.txt", b"vpn evidence", "text/plain")},
    )
    assert upload.status_code == 200
    download = await app_client.get(
        "/api/admin/audit/files/local-part-file/download",
        headers={"X-Test-Company-Role": "admin"},
    )
    assert download.status_code == 200
    assert download.content == b"vpn evidence"

    async with session_factory() as db:
        actions = list((await db.execute(AuditAdminAction.__table__.select())).mappings())
    assert actions[0]["actor_display_name"] == "Admin"
    assert actions[0]["action"] == "audit.file.download"
    assert actions[0]["target_id"] == "local-part-file"
