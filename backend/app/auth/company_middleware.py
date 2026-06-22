"""Application-level company-user auth gate.

This runs in addition to the local bearer-token middleware. The bearer token
proves the desktop shell may call the local backend; this gate proves a company
user has logged in before privileged API routes execute.
"""

from __future__ import annotations

import json

_PUBLIC_PREFIXES = (
    "/api/company-auth/",
    "/_next/",
    "/m/",
)

_PUBLIC_PATHS = {
    "/livez",
    "/health",
    "/shutdown",
    "/favicon.svg",
    "/manifest.json",
    "/m",
}


class CompanyAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("method", "").upper() == "OPTIONS":
            await self.app(scope, receive, send)
            return

        app_state = scope.get("app")
        state = getattr(app_state, "state", None) if app_state else None
        settings = getattr(state, "settings", None)
        if not getattr(settings, "company_auth_enabled", False):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not _requires_company_auth(path):
            await self.app(scope, receive, send)
            return

        store = getattr(state, "company_auth_store", None) if state else None
        if store is None:
            await self._reject(send, 503, "Company auth not initialised")
            return

        headers = dict(scope.get("headers", []))
        token = headers.get(b"x-fpi-session", b"").decode("latin-1", errors="replace").strip()
        user = await store.get_session_user(token)
        if user is None:
            await self._reject(send, 401, "Company login required")
            return

        scope.setdefault("state", {})["company_user"] = user
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": body})


def _requires_company_auth(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return False
    if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return False
    return path.startswith("/api/") or path.startswith("/v1/")
