"""Chat workspace validation tests."""

import pytest
from fastapi import HTTPException

from app.api.chat import _validate_prompt_workspace
from app.schemas.chat import PromptRequest


def test_new_prompt_requires_workspace_folder() -> None:
    body = PromptRequest(text="你好", workspace=None)

    with pytest.raises(HTTPException) as exc:
        _validate_prompt_workspace(body, existing_directory=None, existing_session=False)

    assert exc.value.status_code == 400
    assert "工作区" in str(exc.value.detail)


def test_existing_prompt_can_use_session_workspace() -> None:
    body = PromptRequest(session_id="sess_1", text="继续", workspace=None)

    _validate_prompt_workspace(
        body,
        existing_directory="/Users/liwanx/Documents",
        existing_session=True,
    )


def test_existing_prompt_ignores_request_workspace_when_session_has_none() -> None:
    body = PromptRequest(session_id="sess_1", text="继续", workspace="/tmp/other")

    with pytest.raises(HTTPException) as exc:
        _validate_prompt_workspace(body, existing_directory=None, existing_session=True)

    assert exc.value.status_code == 400
    assert "新建对话" in str(exc.value.detail)
