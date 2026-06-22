"""Tests for the company-auth persistence layer."""

from __future__ import annotations

import json

import pytest

from app.company_auth.store import CompanyAuthStore


@pytest.mark.asyncio
async def test_bootstrap_creates_admin_and_allows_login(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        created = await store.ensure_bootstrap_admin(
            email="admin@example.com",
            display_name="Admin",
            password="TempPassword123!",
            bootstrap_file=tmp_path / "bootstrap.json",
        )

        assert created is True
        user = await store.authenticate("ADMIN@example.com", "TempPassword123!")
        assert user is not None
        assert user.email == "admin@example.com"
        assert user.role == "admin"

        session = await store.create_session(user.id)
        current = await store.get_session_user(session.token)
        assert current is not None
        assert current.email == "admin@example.com"
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_authenticate_rejects_wrong_password(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        await store.ensure_bootstrap_admin(
            email="admin@example.com",
            display_name="Admin",
            password="TempPassword123!",
            bootstrap_file=tmp_path / "bootstrap.json",
        )

        assert await store.authenticate("admin@example.com", "wrong") is None
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_bootstrap_generates_password_file_when_password_missing(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    bootstrap_file = tmp_path / "bootstrap.json"
    await store.startup()
    try:
        created = await store.ensure_bootstrap_admin(
            email="admin@example.com",
            display_name="Admin",
            password="",
            bootstrap_file=bootstrap_file,
        )

        assert created is True
        payload = json.loads(bootstrap_file.read_text(encoding="utf-8"))
        assert payload["email"] == "admin@example.com"
        assert len(payload["password"]) >= 20
        assert await store.authenticate("admin@example.com", payload["password"]) is not None
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_admin_can_create_list_and_deactivate_users(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        created = await store.create_user(
            email="employee@example.com",
            display_name="Employee One",
            password="EmployeePassword123!",
            role="user",
        )

        assert created.email == "employee@example.com"
        assert created.display_name == "Employee One"
        assert created.role == "user"
        assert created.is_active is True
        assert await store.authenticate("employee@example.com", "EmployeePassword123!") is not None

        users = await store.list_users()
        assert [(user.email, user.role, user.is_active) for user in users] == [
            ("employee@example.com", "user", True)
        ]

        updated = await store.update_user(
            created.id,
            is_active=False,
            password="NewPassword123!",
        )
        assert updated is not None
        assert updated.is_active is False
        assert await store.authenticate("employee@example.com", "NewPassword123!") is None
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_model_policy_defaults_and_updates(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENYAK_INTERNAL_DEFAULT_API_KEY", "sk-test-internal")
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        default_policy = await store.get_model_policy()

        assert default_policy.default_provider_id == "custom_onlyme"
        assert default_policy.default_model_id == "gpt-5.5"
        assert [(m.provider_id, m.id, m.name, m.protocol, m.base_url) for m in default_policy.models] == [
            ("custom_onlyme", "gpt-5.5", "GPT-5.5", "openai_compatible", "https://sub2api.onlymeok.com/v1")
        ]
        assert default_policy.models[0].api_key.startswith("sk-")

        updated = await store.update_model_policy(
            default_provider_id="custom_backup",
            default_model_id="gpt-5.4",
            models=[
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
        )

        assert updated.default_provider_id == "custom_backup"
        assert updated.default_model_id == "gpt-5.4"
        reloaded = await store.get_model_policy()
        assert [(m.provider_id, m.id, m.protocol, m.base_url, m.api_key) for m in reloaded.models] == [
            ("custom_onlyme", "gpt-5.5", "openai_compatible", "https://sub2api.onlymeok.com/v1", "sk-onlyme"),
            ("custom_backup", "gpt-5.4", "openai_compatible", "https://backup.example.com/v1", "sk-backup"),
        ]
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_model_policy_preserves_api_key_when_admin_leaves_key_blank(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        await store.update_model_policy(
            default_provider_id="custom_backup",
            default_model_id="gpt-5.4",
            models=[
                {
                    "provider_id": "custom_backup",
                    "id": "gpt-5.4",
                    "name": "GPT-5.4",
                    "protocol": "openai_compatible",
                    "base_url": "https://backup.example.com/v1",
                    "api_key": "sk-original",
                },
            ],
        )

        updated = await store.update_model_policy(
            default_provider_id="custom_backup",
            default_model_id="gpt-5.4",
            models=[
                {
                    "provider_id": "custom_backup",
                    "id": "gpt-5.4",
                    "name": "GPT-5.4 Plus",
                    "protocol": "openai_compatible",
                    "base_url": "https://backup.example.com/v1",
                    "api_key": "",
                },
            ],
        )

        assert updated.models[0].name == "GPT-5.4 Plus"
        assert updated.models[0].api_key == "sk-original"
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_model_policy_accepts_anthropic_protocol_without_base_url(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        updated = await store.update_model_policy(
            default_provider_id="anthropic_team",
            default_model_id="claude-sonnet-4-20250514",
            models=[
                {
                    "provider_id": "anthropic_team",
                    "id": "claude-sonnet-4-20250514",
                    "name": "Claude Sonnet 4",
                    "protocol": "anthropic",
                    "base_url": "",
                    "api_key": "sk-ant-company",
                },
            ],
        )

        assert updated.default_provider_id == "anthropic_team"
        assert updated.default_model_id == "claude-sonnet-4-20250514"
        assert [(m.provider_id, m.id, m.protocol, m.base_url, m.api_key) for m in updated.models] == [
            ("anthropic_team", "claude-sonnet-4-20250514", "anthropic", "", "sk-ant-company")
        ]
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_model_policy_requires_api_key_for_anthropic_protocol(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        with pytest.raises(ValueError, match="API key is required for Anthropic models"):
            await store.update_model_policy(
                default_provider_id="anthropic_team",
                default_model_id="claude-sonnet-4-20250514",
                models=[
                    {
                        "provider_id": "anthropic_team",
                        "id": "claude-sonnet-4-20250514",
                        "name": "Claude Sonnet 4",
                        "protocol": "anthropic",
                        "base_url": "",
                        "api_key": "",
                    },
                ],
            )
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_update_policy_defaults_and_updates(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        assert callable(getattr(store, "get_update_policy", None))
        assert callable(getattr(store, "update_update_policy", None))

        default_policy = await store.get_update_policy()
        assert default_policy.enabled is False
        assert default_policy.latest_version == ""
        assert default_policy.force_update is False
        assert default_policy.macos_asset_id == ""

        updated = await store.update_update_policy(
            enabled=True,
            latest_version="1.4.0",
            min_supported_version="1.2.0",
            force_update=True,
            release_notes="修复本地沙箱执行问题",
            macos_asset_id="asset-macos",
            windows_asset_id="asset-windows",
            linux_asset_id="",
            default_asset_id="asset-default",
            macos_download_url="https://example.com/fpi-agent-1.4.0.dmg",
            windows_download_url="https://example.com/fpi-agent-1.4.0.exe",
            linux_download_url="",
            default_download_url="https://example.com/fpi-agent-1.4.0.zip",
        )

        assert updated.enabled is True
        assert updated.latest_version == "1.4.0"
        assert updated.min_supported_version == "1.2.0"
        assert updated.force_update is True
        assert updated.macos_asset_id == "asset-macos"
        assert updated.default_asset_id == "asset-default"
        assert updated.macos_download_url.endswith(".dmg")

        reloaded = await store.get_update_policy()
        assert reloaded == updated
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_update_assets_persist_metadata_and_download_counts(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        asset = await store.create_update_asset(
            platform="macos",
            version="v1.4.0",
            original_filename="FPI Agent 1.4.0.dmg",
            stored_filename="asset-1.dmg",
            mime_type="application/x-apple-diskimage",
            size_bytes=12345,
            sha256="a" * 64,
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )

        assert asset.platform == "macos"
        assert asset.version == "1.4.0"
        assert asset.original_filename == "FPI Agent 1.4.0.dmg"
        assert asset.download_count == 0
        assert asset.uploaded_by_email == "admin@example.com"

        listed = await store.list_update_assets()
        assert [item.id for item in listed] == [asset.id]

        loaded = await store.get_update_asset(asset.id)
        assert loaded == asset

        incremented = await store.increment_update_asset_download_count(asset.id)
        assert incremented is not None
        assert incremented.download_count == 1

        loaded_again = await store.get_update_asset(asset.id)
        assert loaded_again is not None
        assert loaded_again.download_count == 1
    finally:
        await store.dispose()


@pytest.mark.asyncio
async def test_feedback_persists_user_content_and_optional_image_metadata(tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    try:
        feedback = await store.create_feedback(
            user_id="user-1",
            user_email="employee@example.com",
            user_display_name="员工一",
            description="点击下载按钮后没有反应",
            image_original_filename="screen.png",
            image_stored_filename="feedback-1.png",
            image_mime_type="image/png",
            image_size_bytes=3456,
            image_sha256="b" * 64,
        )

        assert feedback.description == "点击下载按钮后没有反应"
        assert feedback.user_email == "employee@example.com"
        assert feedback.image_original_filename == "screen.png"
        assert feedback.image_size_bytes == 3456

        listed = await store.list_feedback()
        assert [item.id for item in listed] == [feedback.id]

        loaded = await store.get_feedback(feedback.id)
        assert loaded == feedback
    finally:
        await store.dispose()
