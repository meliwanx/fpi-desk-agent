"""Centralized enterprise audit models."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.utils.id import generate_ulid


class AuditSession(Base, TimestampMixin):
    """A session snapshot synced from an employee desktop client."""

    __tablename__ = "audit_session"
    __table_args__ = (
        UniqueConstraint("local_session_id", name="uq_audit_session_local_session_id"),
        Index("ix_audit_session_user_id", "user_id"),
        Index("ix_audit_session_workspace", "workspace"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    workspace: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_client_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class AuditMessage(Base, TimestampMixin):
    """A message snapshot synced from an employee desktop client."""

    __tablename__ = "audit_message"
    __table_args__ = (
        UniqueConstraint("local_message_id", name="uq_audit_message_local_message_id"),
        Index("ix_audit_message_session", "local_session_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    local_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AuditPart(Base, TimestampMixin):
    """A message part snapshot synced from an employee desktop client."""

    __tablename__ = "audit_part"
    __table_args__ = (
        UniqueConstraint("local_part_id", name="uq_audit_part_local_part_id"),
        Index("ix_audit_part_message", "local_message_id"),
        Index("ix_audit_part_session", "local_session_id"),
        Index("ix_audit_part_type", "part_type"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    local_part_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    part_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AuditFile(Base, TimestampMixin):
    """A file attachment observed in an audited message part."""

    __tablename__ = "audit_file"
    __table_args__ = (
        UniqueConstraint("local_part_id", name="uq_audit_file_local_part_id"),
        Index("ix_audit_file_session", "local_session_id"),
        Index("ix_audit_file_hash", "content_hash"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    local_part_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    original_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    size: Mapped[int] = mapped_column(default=0)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_uploaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class AuditToolCall(Base, TimestampMixin):
    """A searchable tool invocation derived from an audited message part."""

    __tablename__ = "audit_tool_call"
    __table_args__ = (
        UniqueConstraint("local_part_id", name="uq_audit_tool_call_local_part_id"),
        Index("ix_audit_tool_call_session", "local_session_id"),
        Index("ix_audit_tool_call_tool", "tool_name"),
        Index("ix_audit_tool_call_status", "status"),
        Index("ix_audit_tool_call_call_id", "call_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    local_part_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    call_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AuditUsage(Base, TimestampMixin):
    """Token and cost usage derived from assistant step-finish parts."""

    __tablename__ = "audit_usage"
    __table_args__ = (
        UniqueConstraint("local_part_id", name="uq_audit_usage_local_part_id"),
        Index("ix_audit_usage_session", "local_session_id"),
        Index("ix_audit_usage_message", "local_message_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    local_part_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    finish_reason: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class AuditRiskFinding(Base, TimestampMixin):
    """A derived compliance/security finding detected from audited content."""

    __tablename__ = "audit_risk_finding"
    __table_args__ = (
        UniqueConstraint("stable_key", name="uq_audit_risk_finding_stable_key"),
        Index("ix_audit_risk_finding_session", "local_session_id"),
        Index("ix_audit_risk_finding_kind", "kind"),
        Index("ix_audit_risk_finding_severity", "severity"),
        Index("ix_audit_risk_finding_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    stable_key: Mapped[str] = mapped_column(String(64), nullable=False)
    local_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_part_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    summary: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    evidence_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")


class AuditAdminAction(Base, TimestampMixin):
    """A management action performed by an administrator against audit data."""

    __tablename__ = "audit_admin_action"
    __table_args__ = (
        Index("ix_audit_admin_action_actor", "actor_user_id"),
        Index("ix_audit_admin_action_action", "action"),
        Index("ix_audit_admin_action_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_ulid)
    actor_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    actor_display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
