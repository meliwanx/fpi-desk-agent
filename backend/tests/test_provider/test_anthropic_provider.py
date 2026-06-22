"""Anthropic provider adapter tests."""

from __future__ import annotations

import pytest

from app.provider.anthropic_provider import AnthropicDesktopProvider



@pytest.mark.asyncio
async def test_anthropic_provider_uses_company_model_overrides_without_network():
    provider = AnthropicDesktopProvider(
        api_key="sk-ant-company",
        provider_id="anthropic_team",
        models_override=[
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        ],
    )

    models = await provider.list_models()

    assert provider.id == "anthropic_team"
    assert [(model.provider_id, model.id, model.name) for model in models] == [
        ("anthropic_team", "claude-sonnet-4-20250514", "Claude Sonnet 4")
    ]
    assert models[0].capabilities.function_calling is True
    assert models[0].capabilities.prompt_caching is True


def test_anthropic_message_conversion_preserves_tool_history():
    messages = AnthropicDesktopProvider._build_messages(
        [
            {"role": "user", "content": "查一下文件"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"query":"report"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "report.pdf"},
        ]
    )

    assert messages == [
        {"role": "user", "content": [{"type": "text", "text": "查一下文件"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "search",
                    "input": {"query": "report"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": "report.pdf",
                }
            ],
        },
    ]
