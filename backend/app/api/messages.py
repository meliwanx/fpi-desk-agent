"""Message listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.message import Message
from app.schemas.message import MessageResponse, PaginatedMessages, PartResponse
from app.session.manager import get_messages

router = APIRouter()

_INTERNAL_PART_TYPES = {"step-start", "step-finish"}


def _part_has_visible_content(data: dict) -> bool:
    part_type = data.get("type")
    if part_type in _INTERNAL_PART_TYPES:
        return False
    if part_type in {"text", "reasoning"}:
        return bool(str(data.get("text") or "").strip())
    return bool(part_type)


def _is_visible_chat_message(msg: Message) -> bool:
    data = dict(msg.data) if msg.data else {}
    if data.get("system") is True:
        return False
    if data.get("role") != "assistant":
        return True
    if data.get("error"):
        return True
    return any(_part_has_visible_content(p.data or {}) for p in msg.parts)


def _msg_to_response(msg: Message) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        session_id=msg.session_id,
        time_created=msg.time_created,
        data=msg.data or {},
        parts=[
            PartResponse(
                id=p.id,
                message_id=p.message_id,
                session_id=p.session_id,
                time_created=p.time_created,
                data=p.data or {},
            )
            for p in msg.parts
        ],
    )


@router.get("/messages/{session_id}", response_model=PaginatedMessages)
async def list_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=-1),
    db: AsyncSession = Depends(get_db),
) -> PaginatedMessages:
    """Get messages for a session with pagination.

    offset=-1 (default) returns the latest page.
    """
    visible_messages = [
        msg for msg in await get_messages(db, session_id)
        if _is_visible_chat_message(msg)
    ]
    total = len(visible_messages)
    actual_offset = max(0, total - limit) if offset < 0 else offset
    messages = visible_messages[actual_offset:actual_offset + limit]
    return PaginatedMessages(
        total=total,
        offset=actual_offset,
        messages=[_msg_to_response(msg) for msg in messages],
    )


@router.get("/messages/{session_id}/{message_id}", response_model=MessageResponse)
async def get_message(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Get a single message with its parts."""
    stmt = (
        select(Message)
        .where(Message.id == message_id)
        .options(selectinload(Message.parts))
    )
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if msg is None or msg.session_id != session_id:
        raise HTTPException(status_code=404, detail="Message not found")

    return _msg_to_response(msg)
