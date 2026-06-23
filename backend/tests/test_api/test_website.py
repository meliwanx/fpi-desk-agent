"""Public website tests."""

from __future__ import annotations

import hashlib

import httpx
import pytest

from app.company_auth.store import CompanyAuthStore

pytestmark = pytest.mark.asyncio


async def test_website_landing_page_is_public_and_admin_stays_on_admin_route(app_client):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_client.app),
        base_url="http://test",
    ) as public_client:
        landing = await public_client.get("/")
        assert landing.status_code == 200
        assert "聚光智能办公助手" in landing.text
        assert "可视化发展部提供技术支持" in landing.text
        assert "从安装到反馈，流程尽量短" in landing.text
        assert "/download-options" in landing.text

        admin = await public_client.get("/admin")
        assert admin.status_code == 200
        assert "聚光智能办公助手" not in admin.text


async def test_website_download_options_are_public_and_count_downloads(app_client, tmp_path):
    store = CompanyAuthStore(f"sqlite+aiosqlite:///{tmp_path / 'company_auth.db'}")
    await store.startup()
    app_client.app.state.company_auth_store = store
    app_client.app.state.settings.update_asset_storage_dir = str(tmp_path / "update_assets")

    storage_dir = tmp_path / "update_assets"
    storage_dir.mkdir()
    mac_bytes = b"macos-dmg"
    windows_bytes = b"windows-installer"
    (storage_dir / "macos.dmg").write_bytes(mac_bytes)
    (storage_dir / "windows.exe").write_bytes(windows_bytes)

    try:
        mac_asset = await store.create_update_asset(
            platform="macos",
            version="1.5.0",
            original_filename="Juguang-Agent.dmg",
            stored_filename="macos.dmg",
            mime_type="application/x-apple-diskimage",
            size_bytes=len(mac_bytes),
            sha256=hashlib.sha256(mac_bytes).hexdigest(),
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )
        windows_asset = await store.create_update_asset(
            platform="windows",
            version="1.5.0",
            original_filename="Juguang-Agent-Setup.exe",
            stored_filename="windows.exe",
            mime_type="application/vnd.microsoft.portable-executable",
            size_bytes=len(windows_bytes),
            sha256=hashlib.sha256(windows_bytes).hexdigest(),
            uploaded_by_user_id="admin-1",
            uploaded_by_email="admin@example.com",
            uploaded_by_display_name="Admin",
        )
        await store.update_update_policy(
            enabled=True,
            latest_version="1.5.0",
            min_supported_version="1.4.0",
            force_update=False,
            release_notes="官网公开下载",
            macos_asset_id=mac_asset.id,
            windows_asset_id=windows_asset.id,
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_client.app),
            base_url="http://test",
        ) as public_client:
            options = await public_client.get("/download-options")
            assert options.status_code == 200
            payload = options.json()
            assert payload["latest_version"] == "1.5.0"
            assert payload["release_notes"] == "官网公开下载"
            assert f"/download/{mac_asset.id}" in payload["platforms"]["macos"]["download_url"]
            assert f"/download/{windows_asset.id}" in payload["platforms"]["windows"]["download_url"]

            download = await public_client.get(payload["platforms"]["windows"]["download_url"])
            assert download.status_code == 200
            assert download.content == windows_bytes
            assert (await store.get_update_asset(windows_asset.id)).download_count == 1
    finally:
        await store.dispose()
