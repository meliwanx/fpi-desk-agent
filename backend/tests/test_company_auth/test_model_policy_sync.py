"""Tests for company model-policy provider registration."""

from __future__ import annotations

import pytest

from app.company_auth.model_policy_sync import sync_company_model_policy
from app.company_auth.store import CompanyModelEntry, CompanyModelPolicy
from app.provider.registry import ProviderRegistry

pytestmark = pytest.mark.asyncio


async def test_sync_company_model_policy_registers_openai_compatible_provider():
    registry = ProviderRegistry()
    policy = CompanyModelPolicy(
        default_provider_id="custom_backup",
        default_model_id="gpt-5.4",
        models=[
            CompanyModelEntry(
                provider_id="custom_backup",
                id="gpt-5.4",
                name="GPT-5.4",
                protocol="openai_compatible",
                base_url="https://backup.example.com/v1",
                api_key="sk-backup",
            )
        ],
    )

    await sync_company_model_policy(registry, policy)

    assert registry.get_provider("custom_backup") is not None
    assert [(model.provider_id, model.id, model.name) for model in registry.all_models()] == [
        ("custom_backup", "gpt-5.4", "GPT-5.4")
    ]


async def test_sync_company_model_policy_registers_anthropic_provider_with_allowed_models():
    registry = ProviderRegistry()
    policy = CompanyModelPolicy(
        default_provider_id="anthropic_team",
        default_model_id="claude-sonnet-4-20250514",
        models=[
            CompanyModelEntry(
                provider_id="anthropic_team",
                id="claude-sonnet-4-20250514",
                name="Claude Sonnet 4",
                protocol="anthropic",
                api_key="sk-ant-company",
            )
        ],
    )

    await sync_company_model_policy(registry, policy)

    provider = registry.get_provider("anthropic_team")
    assert provider is not None
    assert provider.id == "anthropic_team"
    assert [(model.provider_id, model.id, model.name) for model in registry.all_models()] == [
        ("anthropic_team", "claude-sonnet-4-20250514", "Claude Sonnet 4")
    ]


async def test_sync_company_model_policy_unregisters_removed_company_provider():
    registry = ProviderRegistry()
    original = CompanyModelPolicy(
        default_provider_id="custom_backup",
        default_model_id="gpt-5.4",
        models=[
            CompanyModelEntry(
                provider_id="custom_backup",
                id="gpt-5.4",
                name="GPT-5.4",
                protocol="openai_compatible",
                base_url="https://backup.example.com/v1",
                api_key="sk-backup",
            )
        ],
    )
    replacement = CompanyModelPolicy(
        default_provider_id="custom_onlyme",
        default_model_id="gpt-5.5",
        models=[
            CompanyModelEntry(
                provider_id="custom_onlyme",
                id="gpt-5.5",
                name="GPT-5.5",
                protocol="openai_compatible",
                base_url="https://sub2api.onlymeok.com/v1",
                api_key="sk-onlyme",
            )
        ],
    )

    await sync_company_model_policy(registry, original)
    await sync_company_model_policy(registry, replacement)

    assert registry.get_provider("custom_backup") is None
    assert registry.get_provider("custom_onlyme") is not None
