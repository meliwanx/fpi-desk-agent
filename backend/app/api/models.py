"""Model listing endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.dependencies import ProviderRegistryDep
from app.company_auth.store import CompanyModelEntry, CompanyModelPolicy
from app.company_auth.model_policy_sync import sync_company_model_policy
from app.company_auth.remote_control import sync_remote_model_policy_for_request
from app.provider.registry import ProviderRegistry
from app.schemas.provider import ModelInfo
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ModelPolicyResponse(BaseModel):
    default_provider_id: str
    default_model_id: str
    models: list[ModelInfo]


class RuntimeModelPolicyEntry(BaseModel):
    provider_id: str
    id: str
    name: str
    protocol: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""


class RuntimeModelPolicyResponse(BaseModel):
    default_provider_id: str
    default_model_id: str
    models: list[RuntimeModelPolicyEntry]


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
    return await _company_model_policy_for_registry(request, None)


async def _require_company_session_for_runtime_policy(request: Request) -> None:
    store = getattr(request.app.state, "company_auth_store", None)
    settings = getattr(request.app.state, "settings", None)
    if store is None or not getattr(settings, "company_auth_enabled", False):
        return

    token = request.headers.get("X-FPI-Session", "").strip()
    user = await store.get_session_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Company login required")


async def _company_model_policy_for_registry(
    request: Request,
    registry: ProviderRegistry | None,
) -> CompanyModelPolicy | None:
    store = getattr(request.app.state, "company_auth_store", None)
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return None

    if store is not None and getattr(settings, "company_auth_enabled", False):
        policy = await store.get_model_policy()
        if registry is not None:
            try:
                await sync_company_model_policy(registry, policy)
            except Exception as exc:
                logger.warning("Failed to sync company model policy: %s", exc)
        return policy

    token = request.headers.get("X-FPI-Session", "").strip()
    if registry is not None and token:
        return await sync_remote_model_policy_for_request(
            settings=settings,
            registry=registry,
            company_session_token=token,
        )
    return None


async def _policy_models(
    request: Request,
    registry: ProviderRegistry,
) -> tuple[CompanyModelPolicy | None, list[ModelInfo]]:
    policy = await _company_model_policy_for_registry(request, registry)
    models = registry.all_models()
    if not models:
        logger.info("Model index empty — attempting auto-refresh")
        await _refresh_with_token_retry(registry)
        models = registry.all_models()

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


@router.get("/models/policy/runtime", response_model=RuntimeModelPolicyResponse)
async def get_runtime_model_policy(
    request: Request,
) -> RuntimeModelPolicyResponse:
    """Return full provider config for trusted desktop backends.

    This endpoint is intended for the local desktop backend, which needs the
    provider base URL and API key in order to execute model calls locally while
    still obeying centrally managed model policy.
    """
    await _require_company_session_for_runtime_policy(request)
    policy = await _company_model_policy(request)
    if policy is None:
        return RuntimeModelPolicyResponse(
            default_provider_id="",
            default_model_id="",
            models=[],
        )
    return RuntimeModelPolicyResponse(
        default_provider_id=policy.default_provider_id,
        default_model_id=policy.default_model_id,
        models=[
            RuntimeModelPolicyEntry(
                provider_id=model.provider_id,
                id=model.id,
                name=model.name,
                protocol=model.protocol,
                base_url=model.base_url,
                api_key=model.api_key,
            )
            for model in policy.models
        ],
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
