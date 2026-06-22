"""Runtime sync for company-managed model providers."""

from __future__ import annotations

import logging

from app.company_auth.store import CompanyModelEntry, CompanyModelPolicy
from app.provider.registry import ProviderRegistry

logger = logging.getLogger(__name__)

_MANAGED_PROVIDER_IDS_ATTR = "_company_policy_provider_ids"


def _group_policy_models(policy: CompanyModelPolicy) -> dict[str, list[CompanyModelEntry]]:
    grouped: dict[str, list[CompanyModelEntry]] = {}
    for model in policy.models:
        if model.protocol not in {"openai_compatible", "anthropic"}:
            logger.warning("Skipping unsupported company model protocol %s for %s", model.protocol, model.id)
            continue
        if model.protocol == "openai_compatible" and not model.base_url:
            logger.warning("Skipping incomplete company model provider config for %s/%s", model.provider_id, model.id)
            continue
        if not model.api_key:
            logger.warning("Skipping incomplete company model provider config for %s/%s", model.provider_id, model.id)
            continue
        grouped.setdefault(model.provider_id, []).append(model)
    return grouped


async def sync_company_model_policy(
    registry: ProviderRegistry,
    policy: CompanyModelPolicy,
) -> dict[str, int]:
    """Register providers from the company model policy and refresh model index.

    Company-managed providers are declared in the remote auth database. We use
    explicit model overrides so listing models does not require provider-side
    model discovery.
    """
    grouped = _group_policy_models(policy)
    next_provider_ids = set(grouped)
    managed_provider_ids = set(getattr(registry, _MANAGED_PROVIDER_IDS_ATTR, set()))

    for provider_id in sorted(managed_provider_ids - next_provider_ids):
        registry.unregister(provider_id)

    registered: dict[str, int] = {}
    for provider_id, models in grouped.items():
        first = models[0]
        try:
            models_override = [{"id": model.id, "name": model.name} for model in models]
            if first.protocol == "anthropic":
                from app.provider.anthropic_provider import AnthropicDesktopProvider

                provider = AnthropicDesktopProvider(
                    api_key=first.api_key,
                    provider_id=provider_id,
                    models_override=models_override,
                )
            else:
                from app.provider.factory import create_provider

                provider = create_provider(
                    provider_id,
                    first.api_key,
                    base_url=first.base_url,
                    models_override=models_override,
                )
            registry.register(provider)
            registered[provider_id] = len(models)
        except Exception as exc:
            logger.warning("Failed to register company model provider %s: %s", provider_id, exc)

    setattr(registry, _MANAGED_PROVIDER_IDS_ATTR, set(registered))
    await registry.refresh_models()
    return registered
