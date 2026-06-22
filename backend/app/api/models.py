"""Model listing endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.dependencies import ProviderRegistryDep
from app.company_auth.store import CompanyModelEntry, CompanyModelPolicy
from app.provider.registry import ProviderRegistry
from app.schemas.provider import ModelInfo
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ModelPolicyResponse(BaseModel):
    default_provider_id: str
    default_model_id: str
    models: list[ModelInfo]


async def _refresh_with_token_retry(
    registry: ProviderRegistry,
) -> dict[str, list]:
    try:
        return await registry.refresh_models()
    except Exception as e:
        logger.warning("Model refresh failed: %s", e)
        return {}


def _model_from_policy_entry(entry: CompanyModelEntry, indexed: dict[tuple[str, str], ModelInfo]) -> ModelInfo:
    model = indexed.get((entry.provider_id, entry.id))
    if model is None:
        return ModelInfo(id=entry.id, name=entry.name, provider_id=entry.provider_id)
    if entry.name and entry.name != model.name:
        return model.model_copy(update={"name": entry.name})
    return model


async def _company_model_policy(request: Request) -> CompanyModelPolicy | None:
    store = getattr(request.app.state, "company_auth_store", None)
    settings = getattr(request.app.state, "settings", None)
    if store is None or not getattr(settings, "company_auth_enabled", False):
        return None
    return await store.get_model_policy()


async def _policy_models(
    request: Request,
    registry: ProviderRegistry,
) -> tuple[CompanyModelPolicy | None, list[ModelInfo]]:
    models = registry.all_models()
    if not models:
        logger.info("Model index empty — attempting auto-refresh")
        await _refresh_with_token_retry(registry)
        models = registry.all_models()

    policy = await _company_model_policy(request)
    if policy is None:
        return None, models

    indexed = {(model.provider_id, model.id): model for model in models}
    allowed = [_model_from_policy_entry(entry, indexed) for entry in policy.models]
    return policy, allowed


@router.get("/models", response_model=list[ModelInfo])
async def list_models(
    request: Request,
    registry: ProviderRegistryDep,
) -> list[ModelInfo]:
    """List all available models from registered providers.

    If the model index is empty (e.g. startup fetch failed), attempts a
    single refresh before returning so users don't see an empty list.
    """
    _, models = await _policy_models(request, registry)
    return models


@router.get("/models/policy", response_model=ModelPolicyResponse)
async def get_model_policy(
    request: Request,
    registry: ProviderRegistryDep,
) -> ModelPolicyResponse:
    policy, models = await _policy_models(request, registry)
    if policy is None:
        first = models[0] if models else None
        return ModelPolicyResponse(
            default_provider_id=first.provider_id if first else "",
            default_model_id=first.id if first else "",
            models=models,
        )
    return ModelPolicyResponse(
        default_provider_id=policy.default_provider_id,
        default_model_id=policy.default_model_id,
        models=models,
    )


@router.post("/models/refresh")
async def refresh_models(
    registry: ProviderRegistryDep,
) -> dict:
    """Force re-fetch model lists from all providers (also refreshes models.dev)."""
    # Refresh models.dev catalog first so providers pick up latest data
    from app.provider.models_dev import models_dev
    await models_dev.refresh()

    result = await _refresh_with_token_retry(registry)
    counts = {pid: len(models) for pid, models in result.items()}
    return {"refreshed": counts}
