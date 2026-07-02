"""Provider factory behavior tests."""

from __future__ import annotations

from app.provider.factory import create_provider


def test_custom_openai_provider_root_base_url_defaults_to_v1():
    provider = create_provider(
        "custom_example",
        "sk-test",
        base_url="https://api.example.com/",
        models_override=[{"id": "gpt-5.5", "name": "GPT-5.5"}],
    )

    assert str(provider._client.base_url).rstrip("/") == "https://api.example.com/v1"


def test_custom_openai_provider_preserves_explicit_v1_base_url():
    provider = create_provider(
        "custom_example",
        "sk-test",
        base_url="https://api.example.com/v1",
        models_override=[{"id": "gpt-5.5", "name": "GPT-5.5"}],
    )

    assert str(provider._client.base_url).rstrip("/") == "https://api.example.com/v1"
