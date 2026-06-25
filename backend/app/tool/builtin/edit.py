"""Edit tool — precise string replacement in files, single or batch.

Supports two calling modes:
  - Single edit: provide old_string + new_string at top level
  - Batch edit: provide an edits array for multiple sequential replacements
    (all succeed atomically, or none are applied)
"""

from __future__ import annotations

import os
from typing import Any

from app.tool.base import ToolDefinition, ToolResult
from app.tool.context import ToolContext
from app.tool.workspace import WorkspaceViolation, resolve_for_write
from app.utils.diff import generate_unified_diff


class EditTool(ToolDefinition):

    @property
    def id(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return (
            "通过精确字符串匹配替换来修改文件。"
            "两种模式：1. 单次编辑，在顶层提供 old_string 和 new_string；"
            "2. 批量编辑，提供 edits 数组按顺序执行多个替换。"
            "批量模式会整体成功或整体失败。需要替换所有匹配项时设置 replace_all=true。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要编辑的文件路径",
                },
                "old_string": {
                    "type": "string",
                    "description": "要查找并替换的精确字符串（单次编辑模式）",
                },
                "new_string": {
                    "type": "string",
                    "description": "替换后的字符串（单次编辑模式）",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "是否替换所有匹配项（默认 false，单次编辑模式）",
                    "default": False,
                },
                "edits": {
                    "type": "array",
                    "description": "批量编辑的有序列表；与 old_string/new_string 互斥",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_string": {
                                "type": "string",
                                "description": "要查找并替换的精确字符串",
                            },
                            "new_string": {
                                "type": "string",
                                "description": "替换后的字符串",
                            },
                            "replace_all": {
                                "type": "boolean",
                                "description": "是否替换所有匹配项（默认 false）",
                                "default": False,
                            },
                        },
                        "required": ["old_string", "new_string"],
                    },
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        file_path = args["file_path"]
        has_single = "old_string" in args
        has_batch = "edits" in args

        # Determine mode
        if has_single and has_batch:
            return ToolResult(
                error="Provide either old_string/new_string (single edit) or edits array (batch edit), not both."
            )
        if not has_single and not has_batch:
            return ToolResult(
                error="Provide old_string and new_string for a single edit, or an edits array for batch edits."
            )

        # Normalize to a list of edits
        if has_single:
            if "new_string" not in args:
                return ToolResult(error="new_string is required for single edit mode")
            edits = [{
                "old_string": args["old_string"],
                "new_string": args["new_string"],
                "replace_all": args.get("replace_all", False),
            }]
        else:
            edits = args["edits"]
            if not edits:
                return ToolResult(error="No edits provided")

        # Workspace restriction
        try:
            file_path = resolve_for_write(file_path, ctx.workspace)
        except WorkspaceViolation as e:
            return ToolResult(error=str(e))

        if not os.path.exists(file_path):
            return ToolResult(error=f"File not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()
        except UnicodeDecodeError:
            return ToolResult(error=f"Cannot edit binary file: {file_path}")

        # Apply edits sequentially, validating each before proceeding
        content = original
        total_replacements = 0
        for i, edit in enumerate(edits, 1):
            old_string = edit["old_string"]
            new_string = edit["new_string"]
            replace_all = edit.get("replace_all", False)

            prefix = f"Edit {i}: " if len(edits) > 1 else ""

            if old_string == new_string:
                return ToolResult(
                    error=f"{prefix}old_string and new_string are identical"
                )

            count = content.count(old_string)
            if count == 0:
                suffix = (
                    " (may have been modified by a previous edit in this batch)"
                    if i > 1 else ""
                )
                return ToolResult(
                    error=f"{prefix}old_string not found in {file_path}{suffix}"
                )

            if count > 1 and not replace_all:
                return ToolResult(
                    error=f"{prefix}old_string found {count} times in {file_path}. "
                    "Provide more context to make it unique, or use replace_all=true."
                )

            if replace_all:
                content = content.replace(old_string, new_string)
                total_replacements += count
            else:
                content = content.replace(old_string, new_string, 1)
                total_replacements += 1

        # All edits validated and applied — write atomically
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

        diff = generate_unified_diff(original, content, file_path)

        if len(edits) == 1:
            title = (
                f"Edited {os.path.basename(file_path)} "
                f"({total_replacements} replacement{'s' if total_replacements > 1 else ''})"
            )
        else:
            title = (
                f"Edited {os.path.basename(file_path)} "
                f"({len(edits)} edits, {total_replacements} replacement{'s' if total_replacements > 1 else ''})"
            )

        return ToolResult(
            output=diff,
            title=title,
            metadata={"edits": len(edits), "replacements": total_replacements, "file_path": file_path},
        )
