"""Session response serialization tests."""

from datetime import datetime, timezone

from app.schemas.session import SessionResponse


def _session_response(**overrides) -> SessionResponse:
    data = {
        "id": "sess_1",
        "time_created": datetime(2026, 6, 19, 14, 30, 0),
        "time_updated": datetime(2026, 6, 19, 14, 31, 0, tzinfo=timezone.utc),
    }
    data.update(overrides)
    return SessionResponse(**data)


def test_session_response_serializes_datetimes_as_shanghai() -> None:
    dumped = _session_response().model_dump(mode="json")

    assert dumped["time_created"] == "2026-06-19T14:30:00+08:00"
    assert dumped["time_updated"] == "2026-06-19T22:31:00+08:00"
