"""Todo tool — create and manage a task list for the session.

Persists todos to the database so they survive server restarts.
Each call replaces the entire todo list for the session (full replace strategy).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select

from app.models.todo import Todo
from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext
from app.utils.id import generate_ulid

logger = logging.getLogger(__name__)


class TodoTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "todo"

    @property
    def description(self) -> str:
        return (
            "跟踪多步骤任务（3 步及以上）的进度，用户会实时看到更新。\n\n"
            "状态：pending | in_progress（同一时间只能有一个）| completed\n\n"
            "使用方式：\n"
            "1. 创建列表时，第一个任务设为 in_progress，其余设为 pending。\n"
            "2. 每完成一个任务后，立即调用 todo 更新状态，并启动下一个任务。\n"
            "3. 不要攒到最后批量更新，每一步完成后都要及时更新。\n\n"
            "字段：\n"
            "- content：任务内容。\n"
            "- activeForm：执行中展示的文案。\n"
            "- status：pending/in_progress/completed。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                            "activeForm": {"type": "string"},
                        },
                        "required": ["content", "status"],
                    },
                    "description": "完整待办列表；每次调用都会替换现有列表",
                },
            },
            "required": ["todos"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        todos = args["todos"]

        # Access session_factory from app_state (injected by processor)
        app_state = getattr(ctx, "_app_state", None)
        if not app_state or "session_factory" not in app_state:
            logger.warning("TodoTool: no session_factory available, todos not persisted")
            return self._build_result(todos)

        session_factory = app_state["session_factory"]
        async with session_factory() as db:
            async with db.begin():
                # Delete all existing todos for this session
                await db.execute(
                    delete(Todo).where(Todo.session_id == ctx.session_id)
                )

                # Insert new todos with position ordering
                for i, todo in enumerate(todos):
                    db.add(Todo(
                        id=generate_ulid(),
                        session_id=ctx.session_id,
                        content=todo.get("content", ""),
                        status=todo.get("status", "pending"),
                        active_form=todo.get("activeForm", ""),
                        position=i,
                    ))

        return self._build_result(todos)

    @staticmethod
    def _build_result(todos: list[dict[str, Any]]) -> ToolResult:
        total = len(todos)
        completed = sum(1 for t in todos if t.get("status") == "completed")
        in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
        pending = total - completed - in_progress

        summary = f"Todo list updated: {completed}/{total} done"
        if in_progress:
            summary += f", {in_progress} in progress"
        if pending:
            summary += f", {pending} pending"

        return ToolResult(
            output=summary,
            title="Todo list",
            metadata={"todos": todos},
        )


async def get_todos(session_id: str, session_factory: Any) -> list[dict[str, Any]]:
    """Get current todos for a session from the database."""
    async with session_factory() as db:
        stmt = (
            select(Todo)
            .where(Todo.session_id == session_id)
            .order_by(Todo.position)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

    return [
        {
            "content": row.content,
            "status": row.status,
            "activeForm": row.active_form,
        }
        for row in rows
    ]
