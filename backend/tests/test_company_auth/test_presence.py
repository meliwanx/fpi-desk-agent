"""Tests for optional Redis-backed company presence tracking."""

from __future__ import annotations

import json

import pytest

from app.company_auth.presence import CompanyPresenceStore


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.expirations: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex

    async def sadd(self, key: str, value: str) -> None:
        self.sets.setdefault(key, set()).add(value)

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    async def scan_iter(self, match: str):
        prefix = match.replace("*", "")
        for key in list(self.values):
            if key.startswith(prefix):
                yield key

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def scard(self, key: str) -> int:
        return len(self.sets.get(key, set()))


@pytest.mark.asyncio
async def test_presence_touch_records_online_session_and_daily_active_user():
    redis = FakeRedis()
    presence = CompanyPresenceStore(redis=redis, prefix="test", ttl_seconds=90)

    await presence.touch_session(
        user_id="user-1",
        session_id="session-1",
        metadata={"platform": "windows", "app_version": "1.4.0"},
        day="2026-06-22",
    )

    assert redis.expirations["test:presence:user:user-1:session:session-1"] == 90
    assert json.loads(redis.values["test:presence:user:user-1:session:session-1"]) == {
        "user_id": "user-1",
        "session_id": "session-1",
        "platform": "windows",
        "app_version": "1.4.0",
    }
    assert await presence.count_daily_active_users("2026-06-22") == 1
    assert await presence.online_session_ids() == {"session-1"}


@pytest.mark.asyncio
async def test_presence_noops_when_redis_is_unavailable():
    presence = CompanyPresenceStore(redis=None, prefix="test", ttl_seconds=90)

    await presence.touch_session(user_id="user-1", session_id="session-1")

    assert await presence.count_daily_active_users("2026-06-22") == 0
    assert await presence.online_session_ids() == set()
