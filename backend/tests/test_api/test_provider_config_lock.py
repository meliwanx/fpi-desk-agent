"""Provider configuration lock tests for the managed company build."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_custom_provider_mutations_are_locked(app_client):
    response = await app_client.post(
        "/api/config/custom",
        json={
            "slug": "external",
            "name": "External Provider",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-test",
            "models": [{"id": "gpt-5.5", "name": "GPT-5.5"}],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Provider configuration is managed by the company"


@pytest.mark.asyncio
async def test_byok_provider_key_mutations_are_locked(app_client):
    response = await app_client.post(
        "/api/config/providers/openrouter/key",
        json={"api_key": "sk-or-test"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Provider configuration is managed by the company"
