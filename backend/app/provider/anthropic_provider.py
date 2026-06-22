"""Anthropic provider adapter for the desktop backend."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator

from app.provider.base import BaseProvider
from app.schemas.provider import (
    ModelCapabilities,
    ModelInfo,
    ModelPricing,
    ProviderStatus,
    StreamChunk,
)

logger = logging.getLogger(__name__)

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;,]+);base64,(?P<data>.+)$", re.I | re.S)


class AnthropicDesktopProvider(BaseProvider):
    """Native Anthropic provider backed by the official Anthropic SDK."""

    def __init__(
        self,
        api_key: str,
        *,
        provider_id: str = "anthropic",
        models_override: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        self._api_key = api_key
        self._provider_id = provider_id
        self._client_kwargs = kwargs
        self._client: Any | None = None
        self._models_cache: list[ModelInfo] | None = None
        self._models_override = [
            {"id": m["id"], "name": m.get("name") or m["id"]}
            for m in (models_override or [])
            if isinstance(m, dict) and m.get("id")
        ]

    @property
    def id(self) -> str:
        return self._provider_id

    async def list_models(self) -> list[ModelInfo]:
        if self._models_cache is not None:
            return self._models_cache

        if self._models_override:
            self._models_cache = [
                self._model_info(model["id"], model["name"])
                for model in self._models_override
            ]
            return self._models_cache

        models = await self._load_models_dev()
        if not models:
            models = await self._fetch_api_models()
        self._models_cache = models
        return models

    async def _load_models_dev(self) -> list[ModelInfo]:
        try:
            from app.provider.models_dev import models_dev

            raw = await models_dev.get_models("anthropic")
            if not raw:
                return []
            models = []
            for m in raw:
                caps = m.get("capabilities", {})
                pricing = m.get("pricing", {})
                meta = m.get("metadata", {})
                models.append(
                    ModelInfo(
                        id=m["id"],
                        name=m.get("name", m["id"]),
                        provider_id=self._provider_id,
                        capabilities=ModelCapabilities(
                            function_calling=caps.get("function_calling", True),
                            vision=caps.get("vision", True),
                            reasoning=caps.get("reasoning", True),
                            json_output=caps.get("json_output", False),
                            max_context=caps.get("max_context", 200_000),
                            max_output=caps.get("max_output"),
                            prompt_caching=caps.get("prompt_caching", True),
                        ),
                        pricing=ModelPricing(
                            prompt=pricing.get("prompt", 0),
                            completion=pricing.get("completion", 0),
                        ),
                        metadata=meta,
                    )
                )
            return models
        except Exception as exc:
            logger.debug("models.dev unavailable for anthropic: %s", exc)
            return []

    async def _fetch_api_models(self) -> list[ModelInfo]:
        try:
            response = await self._client_instance().models.list()
        except Exception as exc:
            logger.info("Skipped fetching models from Anthropic API: %s", exc)
            return []

        models = []
        for item in getattr(response, "data", []) or []:
            model_id = str(getattr(item, "id", "") or "")
            if model_id:
                models.append(self._model_info(model_id, str(getattr(item, "display_name", "") or model_id)))
        return models

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(messages),
            "max_tokens": max_tokens or 4096,
        }
        system_payload = self._build_system(system)
        if system_payload is not None:
            kwargs["system"] = system_payload
        if temperature is not None:
            kwargs["temperature"] = temperature
        converted_tools = self._convert_tools(tools)
        if converted_tools:
            kwargs["tools"] = converted_tools
        if extra_body:
            kwargs["extra_body"] = extra_body
        if response_format and response_format.get("type") == "json_object":
            kwargs["system"] = (
                f"{kwargs.get('system', '')}\n\nRespond with valid JSON only.".strip()
            )

        tool_blocks: dict[int, dict[str, str]] = {}
        finish_emitted = False

        try:
            async with self._client_instance().messages.stream(**kwargs) as stream:
                async for event in stream:
                    event_type = getattr(event, "type", "")

                    if event_type == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", "") == "tool_use":
                            tool_blocks[int(getattr(event, "index", 0) or 0)] = {
                                "id": str(getattr(block, "id", "") or ""),
                                "name": str(getattr(block, "name", "") or ""),
                                "arguments": "",
                            }
                        continue

                    if event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        delta_type = getattr(delta, "type", "")
                        if delta_type == "text_delta":
                            text = str(getattr(delta, "text", "") or "")
                            if text:
                                yield StreamChunk(type="text-delta", data={"text": text})
                        elif delta_type == "thinking_delta":
                            text = str(getattr(delta, "thinking", "") or "")
                            if text:
                                yield StreamChunk(type="reasoning-delta", data={"text": text})
                        elif delta_type == "input_json_delta":
                            index = int(getattr(event, "index", 0) or 0)
                            if index in tool_blocks:
                                tool_blocks[index]["arguments"] += str(getattr(delta, "partial_json", "") or "")
                        continue

                    if event_type == "content_block_stop":
                        index = int(getattr(event, "index", 0) or 0)
                        pending = tool_blocks.pop(index, None)
                        if pending is not None:
                            yield StreamChunk(type="tool-call", data=self._tool_call_data(pending))
                        continue

                    if event_type == "message_delta":
                        stop_reason = str(getattr(getattr(event, "delta", None), "stop_reason", "") or "")
                        if stop_reason:
                            finish_emitted = True
                            yield StreamChunk(type="finish", data={"reason": self._finish_reason(stop_reason)})

                final_message = await stream.get_final_message()

            usage = self._usage_data(getattr(final_message, "usage", None))
            if usage:
                yield StreamChunk(type="usage", data=usage)
            if not finish_emitted:
                stop_reason = str(getattr(final_message, "stop_reason", "") or "stop")
                yield StreamChunk(type="finish", data={"reason": self._finish_reason(stop_reason)})
        except Exception as exc:
            logger.error("Anthropic stream error for model %s: %s", model, exc, exc_info=True)
            yield StreamChunk(type="error", data={"message": str(exc)})

    async def health_check(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus(status="unconfigured", model_count=0, error="API key is not configured")
        if self._models_override:
            return ProviderStatus(status="connected", model_count=len(self._models_override))
        try:
            models = await self.list_models()
            return ProviderStatus(status="connected", model_count=len(models))
        except Exception as exc:
            return ProviderStatus(status="error", model_count=0, error=str(exc))

    def clear_cache(self) -> None:
        self._models_cache = None

    def _client_instance(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key, **self._client_kwargs)
        return self._client

    def _model_info(self, model_id: str, name: str) -> ModelInfo:
        return ModelInfo(
            id=model_id,
            name=name or model_id,
            provider_id=self._provider_id,
            capabilities=ModelCapabilities(
                function_calling=True,
                vision=True,
                reasoning=True,
                max_context=200_000,
                prompt_caching=True,
            ),
        )

    @staticmethod
    def _finish_reason(reason: str) -> str:
        if reason == "tool_use":
            return "tool_calls"
        if reason == "max_tokens":
            return "length"
        return reason or "stop"

    @staticmethod
    def _usage_data(usage: Any) -> dict[str, int]:
        if usage is None:
            return {}
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        return {
            "input": input_tokens,
            "output": output_tokens,
            "reasoning": 0,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "total": input_tokens + output_tokens + cache_read,
        }

    @staticmethod
    def _tool_call_data(pending: dict[str, str]) -> dict[str, Any]:
        try:
            arguments = json.loads(pending.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {"_raw": pending.get("arguments", "")}
        return {
            "id": pending.get("id") or "",
            "name": pending.get("name") or "",
            "arguments": arguments,
        }

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for tool in tools or []:
            function = tool.get("function") if isinstance(tool, dict) else None
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "").strip()
            if not name:
                continue
            converted.append(
                {
                    "name": name,
                    "description": str(function.get("description") or ""),
                    "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return converted

    @classmethod
    def _build_system(cls, system: str | list[dict[str, Any]] | None) -> str | list[dict[str, Any]] | None:
        if isinstance(system, str):
            return system.strip() or None
        if isinstance(system, list):
            blocks = []
            for part in system:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text" and part.get("text"):
                    blocks.append({"type": "text", "text": str(part["text"])})
            return blocks or None
        return None

    @classmethod
    def _build_messages(cls, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role") or "")
            if role == "system":
                continue
            if role == "tool":
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": str(message.get("tool_call_id") or ""),
                    "content": cls._content_as_text(message.get("content")),
                }
                cls._append_message(converted, "user", [tool_result])
                continue
            if role == "assistant":
                blocks = cls._content_blocks(message.get("content"))
                for tool_call in message.get("tool_calls") or []:
                    if not isinstance(tool_call, dict):
                        continue
                    function = tool_call.get("function") or {}
                    name = str(function.get("name") or "").strip()
                    if not name:
                        continue
                    raw_args = function.get("arguments")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args else (raw_args or {})
                    except json.JSONDecodeError:
                        args = {"_raw": raw_args}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": str(tool_call.get("id") or ""),
                            "name": name,
                            "input": args if isinstance(args, dict) else {"value": args},
                        }
                    )
                if blocks:
                    cls._append_message(converted, "assistant", blocks)
                continue
            if role == "user":
                blocks = cls._content_blocks(message.get("content"))
                if blocks:
                    cls._append_message(converted, "user", blocks)

        if not converted:
            return [{"role": "user", "content": "Hello"}]
        return converted

    @classmethod
    def _append_message(cls, messages: list[dict[str, Any]], role: str, blocks: list[dict[str, Any]]) -> None:
        if messages and messages[-1]["role"] == role:
            existing = messages[-1]["content"]
            if isinstance(existing, list):
                existing.extend(blocks)
            else:
                messages[-1]["content"] = cls._content_blocks(existing) + blocks
            return
        messages.append({"role": role, "content": blocks})

    @classmethod
    def _content_blocks(cls, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            return [{"type": "text", "text": content}] if content else []
        if not isinstance(content, list):
            return []

        blocks: list[dict[str, Any]] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "text" and part.get("text"):
                blocks.append({"type": "text", "text": str(part["text"])})
            elif part_type == "image":
                source = part.get("source")
                if isinstance(source, dict):
                    blocks.append({"type": "image", "source": source})
            elif part_type == "image_url":
                image = cls._convert_image_url(part.get("image_url"))
                if image is not None:
                    blocks.append(image)
        return blocks

    @staticmethod
    def _convert_image_url(image_url: Any) -> dict[str, Any] | None:
        url = image_url.get("url") if isinstance(image_url, dict) else None
        if not isinstance(url, str):
            return None
        match = _DATA_URL_RE.match(url)
        if match:
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": match.group("mime"),
                    "data": match.group("data"),
                },
            }
        return {"type": "text", "text": f"[image: {url}]"}

    @classmethod
    def _content_as_text(cls, content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return "" if content is None else str(content)
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                parts.append(str(part["text"]))
            elif part.get("type") in {"image", "image_url"}:
                parts.append("[image]")
        return "\n".join(parts)
