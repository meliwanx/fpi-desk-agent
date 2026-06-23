"""Employee feedback API."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.company_auth.store import CompanyFeedback, CompanyUser
from app.config import Settings
from app.dependencies import SettingsDep
from app.utils.id import generate_ulid

router = APIRouter()


def _current_company_user(request: Request) -> CompanyUser:
    user = getattr(request.state, "company_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Company login required")
    return user


def _company_store(request: Request):
    store = getattr(request.app.state, "company_auth_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Company auth store not initialized")
    return store


def _safe_filename(name: str | None) -> str:
    safe = Path(name or "feedback-image").name.replace("\x00", "").strip()
    return safe or "feedback-image"


def _feedback_storage_dir(settings: Settings) -> Path:
    return Path(settings.feedback_storage_dir).expanduser()


def _feedback_payload(feedback: CompanyFeedback) -> dict:
    return {
        "id": feedback.id,
        "user_id": feedback.user_id,
        "user_email": feedback.user_email,
        "user_display_name": feedback.user_display_name,
        "description": feedback.description,
        "image_original_filename": feedback.image_original_filename,
        "image_mime_type": feedback.image_mime_type,
        "image_size_bytes": feedback.image_size_bytes,
        "image_sha256": feedback.image_sha256,
        "time_created": feedback.time_created,
        "time_updated": feedback.time_updated,
    }


@router.post("/feedback")
async def submit_feedback(
    request: Request,
    settings: SettingsDep,
    description: str = Form(...),
    image: UploadFile | None = File(default=None),
) -> dict:
    user = _current_company_user(request)
    text = (description or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Feedback description is required")

    image_original_filename = ""
    image_stored_filename = ""
    image_mime_type = ""
    image_size_bytes = 0
    image_sha256 = ""

    if image is not None and image.filename:
        content_type = image.content_type or mimetypes.guess_type(image.filename)[0] or ""
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Feedback attachment must be an image")

        storage_dir = _feedback_storage_dir(settings)
        storage_dir.mkdir(parents=True, exist_ok=True)
        image_original_filename = _safe_filename(image.filename)
        image_stored_filename = f"{generate_ulid()}-{image_original_filename}"
        target = storage_dir / image_stored_filename
        digest = hashlib.sha256()
        try:
            with target.open("wb") as handle:
                while True:
                    chunk = await image.read(1024 * 1024)
                    if not chunk:
                        break
                    image_size_bytes += len(chunk)
                    digest.update(chunk)
                    handle.write(chunk)
        except Exception:
            if target.exists():
                target.unlink(missing_ok=True)
            raise

        if image_size_bytes == 0:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Feedback image cannot be empty")

        image_mime_type = content_type
        image_sha256 = digest.hexdigest()

    try:
        feedback = await _company_store(request).create_feedback(
            user_id=user.id,
            user_email=user.email,
            user_display_name=user.display_name,
            description=text,
            image_original_filename=image_original_filename,
            image_stored_filename=image_stored_filename,
            image_mime_type=image_mime_type,
            image_size_bytes=image_size_bytes,
            image_sha256=image_sha256,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _feedback_payload(feedback)
