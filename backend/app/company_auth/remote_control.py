"""Remote enterprise control-plane helpers for desktop backends."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.company_auth.model_policy_sync import sync_company_model_policy
from app.company_auth.store import CompanyModelEntry, CompanyModelPolicy
from app.config import Settings
from app.provider.registry import ProviderRegistry

logger = logging.getLogger(__name__)


def _control_url(settings: Settings) -> str:
    return settings.enterprise_control_url.strip().rstrip("/")


def _policy_from_payload(payload: dict[str, Any]) -> CompanyModelPolicy:
    models: list[CompanyModelEntry] = []
    for raw in payload.get("models") or []:
        if not isinstance(raw, dict):
            continue
        provider_id = str(raw.get("provider_id") or "").strip()
        model_id = str(raw.get("id") or "").strip()
        if not provider_id or not model_id:
            continue
        models.append(
            CompanyModelEntry(
                provider_id=provider_id,
                id=model_id,
                name=str(raw.get("name") or model_id),
                protocol=str(raw.get("protocol") or "openai_compatible"),
                base_url=str(raw.get("base_url") or ""),
                api_key=str(raw.get("api_key") or ""),
            )
        )
    return CompanyModelPolicy(
        default_provider_id=str(payload.get("default_provider_id") or ""),
        default_model_id=str(payload.get("default_model_id") or ""),
        models=models,
    )


async def fetch_runtime_model_policy(
    *,
    settings: Settings,
    company_session_token: str,
) -> CompanyModelPolicy | None:
    """Fetch full provider runtime config from the enterprise control plane."""
    base_url = _control_url(settings)
    if not base_url or not company_session_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base_url}/api/models/policy/runtime",
                headers={"X-FPI-Session": company_session_token},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Enterprise model policy fetch failed with status %s",
            exc.response.status_code,
        )
        return None
    except Exception as exc:
        logger.warning("Enterprise model policy fetch failed: %s", exc)
        return None

    if not isinstance(payload, dict):
        return None
    return _policy_from_payload(payload)


async def sync_remote_model_policy_for_request(
    *,
    settings: Settings,
    registry: ProviderRegistry,
    company_session_token: str,
) -> CompanyModelPolicy | None:
    """Pull remote model policy and register its providers in the local registry."""
    policy = await fetch_runtime_model_policy(
        settings=settings,
        company_session_token=company_session_token,
    )
    if policy is None:
        return None
    if not policy.models:
        logger.warning("Enterprise model policy has no usable models")
        return policy
    try:
        synced = await sync_company_model_policy(registry, policy)
        if synced:
            logger.info(
                "Synced enterprise model providers: %s",
                ", ".join(sorted(synced)),
            )
    except Exception as exc:
        logger.warning("Enterprise model provider sync failed: %s", exc)
    return policy
