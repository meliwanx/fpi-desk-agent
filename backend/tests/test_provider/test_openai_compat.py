"""Tests for OpenAI-compatible provider behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.provider.generic_openai import GenericOpenAIProvider


pytestmark = pytest.mark.asyncio


async def test_stream_chat_reraises_sdk_errors_for_processor_retry():
    provider = GenericOpenAIProvider(
        api_key="sk-test",
        provider_id="custom_test",
        base_url="https://example.invalid/v1",
        kind="openai_compat_custom",
    )

    async def fail_create(**_kwargs):
        raise RuntimeError("503 Upstream service temporarily unavailable")

    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fail_create),
        )
    )

    with pytest.raises(RuntimeError, match="503 Upstream service temporarily unavailable"):
        async for _chunk in provider.stream_chat(
            "gpt-5.5",
            [{"role": "user", "content": "你好"}],
        ):
            pass
