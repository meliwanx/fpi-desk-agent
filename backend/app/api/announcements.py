"""Employee-facing notification announcement endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_serializer

from app.company_auth.store import CompanyUser
from app.utils.timezone import as_shanghai, shanghai_now

router = APIRouter()


class AppAnnouncement(BaseModel):
    id: str
    content: str
    published_at: datetime

    @field_serializer("published_at")
    def _serialize_datetime_shanghai(self, value: datetime) -> str:
        return as_shanghai(value).isoformat()


class AppAnnouncementResponse(BaseModel):
    announcement: AppAnnouncement | None
    checked_at: datetime

    @field_serializer("checked_at")
    def _serialize_checked_at(self, value: datetime) -> str:
        return as_shanghai(value).isoformat()


class AppAnnouncementReadResponse(BaseModel):
    ok: bool


def _company_store(request: Request):
    store = getattr(request.app.state, "company_auth_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Company auth store not initialized")
    return store


def _current_company_user(request: Request) -> CompanyUser:
    user = getattr(request.state, "company_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Company login required")
    return user


def _is_visible_to_user(announcement, user_id: str) -> bool:
    if not announcement.enabled or not announcement.id or not announcement.content:
        return False
    return not announcement.target_user_ids or user_id in announcement.target_user_ids


@router.get("/app/announcement", response_model=AppAnnouncementResponse)
async def get_app_announcement(request: Request) -> AppAnnouncementResponse:
    user = _current_company_user(request)
    announcement = await _company_store(request).get_unread_announcement_for_user(user.id)
    return AppAnnouncementResponse(
        announcement=(
            AppAnnouncement(
                id=announcement.id,
                content=announcement.content,
                published_at=announcement.time_created,
            )
            if announcement is not None
            else None
        ),
        checked_at=shanghai_now(),
    )


@router.post("/app/announcement/{announcement_id}/read", response_model=AppAnnouncementReadResponse)
async def mark_app_announcement_read(
    request: Request,
    announcement_id: str,
) -> AppAnnouncementReadResponse:
    user = _current_company_user(request)
    store = _company_store(request)
    announcement = await store.get_announcement()
    if announcement.id != announcement_id or not _is_visible_to_user(announcement, user.id):
        raise HTTPException(status_code=404, detail="Announcement not found")
    await store.mark_announcement_read(announcement_id, user.id)
    return AppAnnouncementReadResponse(ok=True)
