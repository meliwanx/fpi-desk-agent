"""Optional Redis-backed online presence and activity tracking."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


class CompanyPresenceStore:
    def __init__(
        self,
        *,
        redis: Any | None,
        prefix: str = "fpi_agent",
        ttl_seconds: int = 90,
    ) -> None:
        self.redis = redis
        self.prefix = prefix.strip(":") or "fpi_agent"
        self.ttl_seconds = max(30, int(ttl_seconds or 90))

    @property
    def available(self) -> bool:
        return self.redis is not None

    @classmethod
    async def from_url(
        cls,
        redis_url: str,
        *,
        prefix: str = "fpi_agent",
        ttl_seconds: int = 90,
    ) -> "CompanyPresenceStore":
        if not redis_url:
            return cls(redis=None, prefix=prefix, ttl_seconds=ttl_seconds)
        try:
            from redis import asyncio as redis_asyncio

            client = redis_asyncio.from_url(redis_url, decode_responses=True)
            await client.ping()
            return cls(redis=client, prefix=prefix, ttl_seconds=ttl_seconds)
        except Exception:
            return cls(redis=None, prefix=prefix, ttl_seconds=ttl_seconds)

    async def close(self) -> None:
        if self.redis is None:
            return
        close = getattr(self.redis, "aclose", None) or getattr(self.redis, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result

    async def touch_session(
        self,
        *,
        user_id: str,
        session_id: str,
        metadata: dict[str, Any] | None = None,
        day: str | None = None,
    ) -> None:
        if self.redis is None or not user_id or not session_id:
            return
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            **(metadata or {}),
        }
        presence_key = self._presence_key(user_id, session_id)
        active_key = self._daily_active_key(day or datetime.now(timezone.utc).date().isoformat())
        await self.redis.set(
            presence_key,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ex=self.ttl_seconds,
        )
        await self.redis.sadd(active_key, user_id)
        await self.redis.expire(active_key, 90 * 24 * 60 * 60)

    async def online_session_ids(self) -> set[str]:
        if self.redis is None:
            return set()
        ids: set[str] = set()
        async for key in self.redis.scan_iter(match=f"{self.prefix}:presence:user:*"):
            raw = await self.redis.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            session_id = str(payload.get("session_id") or "")
            if session_id:
                ids.add(session_id)
        return ids

    async def count_daily_active_users(self, day: str) -> int:
        if self.redis is None or not day:
            return 0
        return int(await self.redis.scard(self._daily_active_key(day)))

    def _presence_key(self, user_id: str, session_id: str) -> str:
        return f"{self.prefix}:presence:user:{user_id}:session:{session_id}"

    def _daily_active_key(self, day: str) -> str:
        return f"{self.prefix}:active:daily:{day}"
