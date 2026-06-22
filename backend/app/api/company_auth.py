"""Company-user login endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.company_auth.store import CompanyUser
from app.dependencies import CompanyAuthStoreDep
from app.schemas.company_auth import (
    CompanyLoginRequest,
    CompanyLoginResponse,
    CompanySessionResponse,
    CompanyUserInfo,
)

router = APIRouter()


def _public_user(user: CompanyUser) -> CompanyUserInfo:
    return CompanyUserInfo(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


@router.post("/company-auth/login", response_model=CompanyLoginResponse)
async def login(
    request: Request,
    body: CompanyLoginRequest,
    store: CompanyAuthStoreDep,
) -> CompanyLoginResponse:
    user = await store.authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    session = await store.create_session(
        user.id,
        device_id=request.headers.get("x-fpi-device-id", ""),
        device_name=request.headers.get("x-fpi-device-name", ""),
        platform=request.headers.get("x-fpi-platform", ""),
        app_version=request.headers.get("x-fpi-app-version", ""),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return CompanyLoginResponse(
        session_id=session.id,
        token=session.token,
        expires_at=session.expires_at,
        user=_public_user(user),
    )


@router.get("/company-auth/session", response_model=CompanySessionResponse)
async def current_session(
    store: CompanyAuthStoreDep,
    token: str = Header("", alias="X-FPI-Session"),
) -> CompanySessionResponse:
    user = await store.get_session_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Company login required")
    return CompanySessionResponse(user=_public_user(user))


@router.post("/company-auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    store: CompanyAuthStoreDep,
    token: str = Header("", alias="X-FPI-Session"),
) -> Response:
    await store.revoke_session(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
