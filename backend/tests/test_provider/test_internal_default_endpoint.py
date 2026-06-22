"""Tests for the built-in internal GPT-5.5 custom endpoint seed."""

from __future__ import annotations

import json

from app.config import internal_default_custom_endpoints_json


def test_internal_default_endpoint_is_empty_without_configured_key(monkeypatch):
    monkeypatch.delenv("OPENYAK_INTERNAL_DEFAULT_API_KEY", raising=False)

    assert json.loads(internal_default_custom_endpoints_json()) == []


def test_internal_default_endpoint_seeds_gpt55_custom_provider(monkeypatch):
    monkeypatch.setenv("OPENYAK_INTERNAL_DEFAULT_API_KEY", "sk-test-internal")
    endpoints = json.loads(internal_default_custom_endpoints_json())

    assert endpoints == [
        {
            "id": "custom_onlyme",
            "slug": "onlyme",
            "name": "OnlyMe GPT-5.5",
            "base_url": "https://sub2api.onlymeok.com/v1",
            "api_key": "sk-test-internal",
            "enabled": True,
            "models": [{"id": "gpt-5.5", "name": "GPT-5.5"}],
            "headers": {},
        }
    ]
