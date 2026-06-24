"""Tests for model listing API endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.schemas.provider import ModelCapabilities, ModelInfo
from app.company_auth.store import CompanyModelEntry, CompanyModelPolicy, CompanyUser

pytestmark = pytest.mark.asyncio


def _model(mid: str) -> ModelInfo:
    return ModelInfo(id=mid, name=mid, provider_id="or", capabilities=ModelCapabilities())


class TestListModels:
    async def test_with_models(self, app_client):
        app_client.app.state.provider_registry.all_models.return_value = [_model("m1"), _model("m2")]
        resp = await app_client.get("/api/models")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_empty_triggers_refresh(self, app_client):
        pr = app_client.app.state.provider_registry
        pr.all_models.return_value = []
        resp = await app_client.get("/api/models")
        assert resp.status_code == 200
        pr.refresh_models.assert_called()

    async def test_company_model_policy_filters_available_models(self, app_client):
        class FakeCompanyStore:
            async def get_session_user(self, token: str):
                return CompanyUser(
                    id="employee-1",
                    email="employee@example.com",
                    display_name="Employee One",
                    role="user",
                    is_active=True,
                )

            async def get_model_policy(self):
                return CompanyModelPolicy(
                    default_provider_id="custom_onlyme",
                    default_model_id="gpt-5.5",
                    models=[
                        CompanyModelEntry(
                            provider_id="custom_onlyme",
                            id="gpt-5.5",
                            name="GPT-5.5",
                            protocol="openai_compatible",
                            base_url="https://sub2api.onlymeok.com/v1",
                            api_key="sk-secret",
                        ),
                    ],
                )

        app_client.app.state.settings.company_auth_enabled = True
        app_client.app.state.company_auth_store = FakeCompanyStore()
        app_client.app.state.provider_registry.all_models.return_value = [
            ModelInfo(id="gpt-5.5", name="GPT-5.5", provider_id="custom_onlyme", capabilities=ModelCapabilities()),
            ModelInfo(id="other", name="Other", provider_id="custom_onlyme", capabilities=ModelCapabilities()),
        ]

        resp = await app_client.get("/api/models", headers={"X-FPI-Session": "token"})

        assert resp.status_code == 200
        assert [(m["provider_id"], m["id"]) for m in resp.json()] == [
            ("custom_onlyme", "gpt-5.5")
        ]

    async def test_company_model_policy_hides_disabled_models(self, app_client):
        class FakeCompanyStore:
            async def get_session_user(self, token: str):
                return CompanyUser(
                    id="employee-1",
                    email="employee@example.com",
                    display_name="Employee One",
                    role="user",
                    is_active=True,
                )

            async def get_model_policy(self):
                return CompanyModelPolicy(
                    default_provider_id="custom_onlyme",
                    default_model_id="gpt-5.5",
                    models=[
                        CompanyModelEntry(
                            provider_id="custom_onlyme",
                            id="gpt-5.5",
                            name="GPT-5.5",
                            protocol="openai_compatible",
                            base_url="https://sub2api.onlymeok.com/v1",
                            api_key="sk-secret",
                            enabled=True,
                        ),
                        CompanyModelEntry(
                            provider_id="custom_onlyme",
                            id="gpt-5-disabled",
                            name="GPT Disabled",
                            protocol="openai_compatible",
                            base_url="https://sub2api.onlymeok.com/v1",
                            api_key="sk-secret",
                            enabled=False,
                        ),
                    ],
                )

        app_client.app.state.settings.company_auth_enabled = True
        app_client.app.state.company_auth_store = FakeCompanyStore()
        app_client.app.state.provider_registry.all_models.return_value = [
            ModelInfo(id="gpt-5.5", name="GPT-5.5", provider_id="custom_onlyme", capabilities=ModelCapabilities()),
            ModelInfo(id="gpt-5-disabled", name="GPT Disabled", provider_id="custom_onlyme", capabilities=ModelCapabilities()),
        ]

        listed = await app_client.get("/api/models", headers={"X-FPI-Session": "token"})
        runtime = await app_client.get("/api/models/policy/runtime", headers={"X-FPI-Session": "token"})

        assert listed.status_code == 200
        assert [(m["provider_id"], m["id"]) for m in listed.json()] == [
            ("custom_onlyme", "gpt-5.5")
        ]
        assert runtime.status_code == 200
        assert [(m["provider_id"], m["id"]) for m in runtime.json()["models"]] == [
            ("custom_onlyme", "gpt-5.5")
        ]

    async def test_company_model_policy_endpoint_returns_default(self, app_client):
        class FakeCompanyStore:
            async def get_session_user(self, token: str):
                return CompanyUser(
                    id="employee-1",
                    email="employee@example.com",
                    display_name="Employee One",
                    role="user",
                    is_active=True,
                )

            async def get_model_policy(self):
                return CompanyModelPolicy(
                    default_provider_id="custom_onlyme",
                    default_model_id="gpt-5.5",
                    models=[
                        CompanyModelEntry(
                            provider_id="custom_onlyme",
                            id="gpt-5.5",
                            name="GPT-5.5",
                            protocol="openai_compatible",
                            base_url="https://sub2api.onlymeok.com/v1",
                            api_key="sk-secret",
                        ),
                    ],
                )

        app_client.app.state.settings.company_auth_enabled = True
        app_client.app.state.company_auth_store = FakeCompanyStore()
        app_client.app.state.provider_registry.all_models.return_value = [
            ModelInfo(id="gpt-5.5", name="GPT-5.5", provider_id="custom_onlyme", capabilities=ModelCapabilities()),
        ]

        resp = await app_client.get("/api/models/policy", headers={"X-FPI-Session": "token"})

        assert resp.status_code == 200
        assert resp.json()["default_provider_id"] == "custom_onlyme"
        assert resp.json()["default_model_id"] == "gpt-5.5"
        assert resp.json()["models"][0]["id"] == "gpt-5.5"
        assert "api_key" not in resp.json()["models"][0]
        assert "base_url" not in resp.json()["models"][0]
        assert "protocol" not in resp.json()["models"][0]

    async def test_runtime_model_policy_endpoint_returns_provider_config(self, app_client):
        class FakeCompanyStore:
            async def get_session_user(self, token: str):
                return CompanyUser(
                    id="employee-1",
                    email="employee@example.com",
                    display_name="Employee One",
                    role="user",
                    is_active=True,
                )

            async def get_model_policy(self):
                return CompanyModelPolicy(
                    default_provider_id="custom_onlyme",
                    default_model_id="gpt-5.5",
                    models=[
                        CompanyModelEntry(
                            provider_id="custom_onlyme",
                            id="gpt-5.5",
                            name="GPT-5.5",
                            protocol="openai_compatible",
                            base_url="https://sub2api.onlymeok.com/v1",
                            api_key="sk-runtime-secret",
                        ),
                    ],
                )

        app_client.app.state.settings.company_auth_enabled = True
        app_client.app.state.company_auth_store = FakeCompanyStore()

        resp = await app_client.get("/api/models/policy/runtime", headers={"X-FPI-Session": "token"})

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["default_provider_id"] == "custom_onlyme"
        assert payload["default_model_id"] == "gpt-5.5"
        assert payload["models"][0]["provider_id"] == "custom_onlyme"
        assert payload["models"][0]["id"] == "gpt-5.5"
        assert payload["models"][0]["protocol"] == "openai_compatible"
        assert payload["models"][0]["base_url"] == "https://sub2api.onlymeok.com/v1"
        assert payload["models"][0]["api_key"] == "sk-runtime-secret"

    async def test_runtime_model_policy_requires_company_session(self, app_client):
        class FakeCompanyStore:
            async def get_session_user(self, token: str):
                return None

            async def get_model_policy(self):
                return CompanyModelPolicy(
                    default_provider_id="custom_onlyme",
                    default_model_id="gpt-5.5",
                    models=[
                        CompanyModelEntry(
                            provider_id="custom_onlyme",
                            id="gpt-5.5",
                            name="GPT-5.5",
                            protocol="openai_compatible",
                            base_url="https://sub2api.onlymeok.com/v1",
                            api_key="sk-runtime-secret",
                        ),
                    ],
                )

        app_client.app.state.settings.company_auth_enabled = True
        app_client.app.state.company_auth_store = FakeCompanyStore()

        resp = await app_client.get("/api/models/policy/runtime")

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Company login required"


class TestRefreshModels:
    async def test_success(self, app_client):
        pr = app_client.app.state.provider_registry
        pr.refresh_models = AsyncMock(return_value={"or": [_model("m1")]})
        resp = await app_client.post("/api/models/refresh")
        assert resp.status_code == 200
        assert "refreshed" in resp.json()

    async def test_non_auth_error(self, app_client):
        pr = app_client.app.state.provider_registry
        pr.refresh_models = AsyncMock(side_effect=RuntimeError("Connection refused"))
        resp = await app_client.post("/api/models/refresh")
        assert resp.status_code == 200
        assert resp.json()["refreshed"] == {}
