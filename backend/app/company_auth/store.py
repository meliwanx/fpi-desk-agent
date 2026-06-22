"""Async persistence for company users and login sessions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    func,
    insert,
    select,
    inspect,
    update,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.company_auth.security import (
    generate_session_token,
    generate_temporary_password,
    hash_password,
    hash_token,
    verify_password,
)
from app.config import internal_default_custom_endpoints_json
from app.utils.id import generate_ulid


@dataclass(frozen=True)
class CompanyUser:
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool


@dataclass(frozen=True)
class CompanySession:
    id: str
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class CompanySessionRecord:
    id: str
    user_id: str
    user_email: str
    user_display_name: str
    user_role: str
    user_is_active: bool
    expires_at: datetime
    revoked_at: datetime | None
    time_created: datetime
    last_seen_at: datetime
    device_id: str
    device_name: str
    platform: str
    app_version: str
    ip_address: str
    user_agent: str
    revoked_by_user_id: str
    revoked_by_email: str
    revoked_reason: str


@dataclass(frozen=True)
class CompanySessionContext:
    user: CompanyUser
    session_id: str
    device_id: str
    device_name: str
    platform: str
    app_version: str


@dataclass(frozen=True)
class CompanyActivityDay:
    date: str
    active_users: int
    session_count: int


@dataclass(frozen=True)
class CompanyModelEntry:
    provider_id: str
    id: str
    name: str
    protocol: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""


@dataclass(frozen=True)
class CompanyModelPolicy:
    default_provider_id: str
    default_model_id: str
    models: list[CompanyModelEntry]


@dataclass(frozen=True)
class CompanyUpdatePolicy:
    enabled: bool = False
    latest_version: str = ""
    min_supported_version: str = ""
    force_update: bool = False
    release_notes: str = ""
    macos_asset_id: str = ""
    windows_asset_id: str = ""
    linux_asset_id: str = ""
    default_asset_id: str = ""
    macos_download_url: str = ""
    windows_download_url: str = ""
    linux_download_url: str = ""
    default_download_url: str = ""


@dataclass(frozen=True)
class CompanyUpdateAsset:
    id: str
    platform: str
    version: str
    original_filename: str
    stored_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    uploaded_by_user_id: str
    uploaded_by_email: str
    uploaded_by_display_name: str
    download_count: int
    time_created: datetime
    time_updated: datetime


@dataclass(frozen=True)
class CompanyFeedback:
    id: str
    user_id: str
    user_email: str
    user_display_name: str
    description: str
    image_original_filename: str
    image_stored_filename: str
    image_mime_type: str
    image_size_bytes: int
    image_sha256: str
    time_created: datetime
    time_updated: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_model_protocol(value: str | None) -> str:
    raw = (value or "openai_compatible").strip().lower().replace("-", "_")
    aliases = {
        "openai": "openai_compatible",
        "openai_compat": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "openai_compat_custom": "openai_compatible",
        "anthropic": "anthropic",
        "anthropic_native": "anthropic",
        "claude": "anthropic",
    }
    return aliases.get(raw, raw)


def _default_custom_endpoint() -> dict:
    try:
        endpoints = json.loads(internal_default_custom_endpoints_json())
    except Exception:
        return {}
    if not isinstance(endpoints, list) or not endpoints:
        return {}
    first = endpoints[0]
    return first if isinstance(first, dict) else {}


def _default_model_policy() -> CompanyModelPolicy:
    endpoint = _default_custom_endpoint()
    models = endpoint.get("models") if isinstance(endpoint.get("models"), list) else []
    first_model = models[0] if models and isinstance(models[0], dict) else {}
    provider_id = str(endpoint.get("id") or "custom_onlyme")
    model_id = str(first_model.get("id") or "gpt-5.5")
    model_name = str(first_model.get("name") or "GPT-5.5")
    return CompanyModelPolicy(
        default_provider_id=provider_id,
        default_model_id=model_id,
        models=[
            CompanyModelEntry(
                provider_id=provider_id,
                id=model_id,
                name=model_name,
                protocol="openai_compatible",
                base_url=str(endpoint.get("base_url") or ""),
                api_key=str(endpoint.get("api_key") or ""),
            )
        ],
    )


def _default_update_policy() -> CompanyUpdatePolicy:
    return CompanyUpdatePolicy()


class CompanyAuthStore:
    """Company-auth table manager backed by a separate SQLAlchemy engine."""

    def __init__(
        self,
        database_url: str,
        *,
        table_prefix: str = "fpi_desk",
        session_days: int = 30,
        echo: bool = False,
    ) -> None:
        self.database_url = database_url
        self.table_prefix = table_prefix
        self.session_days = session_days
        self.metadata = MetaData()
        self.users = Table(
            f"{table_prefix}_users",
            self.metadata,
            Column("id", String(32), primary_key=True),
            Column("email", String(255), nullable=False, unique=True, index=True),
            Column("display_name", String(255), nullable=False, default=""),
            Column("password_hash", String(512), nullable=False),
            Column("role", String(50), nullable=False, default="user"),
            Column("is_active", Boolean, nullable=False, default=True),
            Column("time_created", DateTime(timezone=True), nullable=False),
            Column("time_updated", DateTime(timezone=True), nullable=False),
        )
        self.sessions = Table(
            f"{table_prefix}_sessions",
            self.metadata,
            Column("id", String(32), primary_key=True),
            Column("user_id", String(32), ForeignKey(f"{table_prefix}_users.id"), nullable=False, index=True),
            Column("token_hash", String(64), nullable=False, unique=True, index=True),
            Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
            Column("revoked_at", DateTime(timezone=True), nullable=True),
            Column("time_created", DateTime(timezone=True), nullable=False),
            Column("last_seen_at", DateTime(timezone=True), nullable=False),
            Column("device_id", String(128), nullable=True),
            Column("device_name", String(255), nullable=True),
            Column("platform", String(50), nullable=True),
            Column("app_version", String(64), nullable=True),
            Column("ip_address", String(64), nullable=True),
            Column("user_agent", Text, nullable=True),
            Column("revoked_by_user_id", String(32), nullable=True),
            Column("revoked_by_email", String(255), nullable=True),
            Column("revoked_reason", Text, nullable=True),
        )
        self.settings = Table(
            f"{table_prefix}_settings",
            self.metadata,
            Column("key", String(100), primary_key=True),
            Column("value", Text, nullable=False),
            Column("time_updated", DateTime(timezone=True), nullable=False),
        )
        self.update_assets = Table(
            f"{table_prefix}_update_assets",
            self.metadata,
            Column("id", String(32), primary_key=True),
            Column("platform", String(20), nullable=False, index=True),
            Column("version", String(64), nullable=False, index=True),
            Column("original_filename", String(512), nullable=False, default=""),
            Column("stored_filename", String(512), nullable=False),
            Column("mime_type", String(255), nullable=False, default=""),
            Column("size_bytes", Integer, nullable=False, default=0),
            Column("sha256", String(64), nullable=False),
            Column("uploaded_by_user_id", String(32), nullable=False, default=""),
            Column("uploaded_by_email", String(255), nullable=False, default=""),
            Column("uploaded_by_display_name", String(255), nullable=False, default=""),
            Column("download_count", Integer, nullable=False, default=0),
            Column("time_created", DateTime(timezone=True), nullable=False),
            Column("time_updated", DateTime(timezone=True), nullable=False),
        )
        self.feedback = Table(
            f"{table_prefix}_feedback",
            self.metadata,
            Column("id", String(32), primary_key=True),
            Column("user_id", String(32), nullable=False, index=True),
            Column("user_email", String(255), nullable=False, default=""),
            Column("user_display_name", String(255), nullable=False, default=""),
            Column("description", Text, nullable=False),
            Column("image_original_filename", String(512), nullable=False, default=""),
            Column("image_stored_filename", String(512), nullable=False, default=""),
            Column("image_mime_type", String(255), nullable=False, default=""),
            Column("image_size_bytes", Integer, nullable=False, default=0),
            Column("image_sha256", String(64), nullable=False, default=""),
            Column("time_created", DateTime(timezone=True), nullable=False, index=True),
            Column("time_updated", DateTime(timezone=True), nullable=False),
        )
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        if database_url.startswith("sqlite"):
            db_path = database_url.split("///")[-1]
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=False,
            connect_args=connect_args,
        )

    async def startup(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(self.metadata.create_all)
            await conn.run_sync(self._add_missing_columns)

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def ensure_bootstrap_admin(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        bootstrap_file: Path,
    ) -> bool:
        normalized = email.strip().lower()
        if not normalized:
            raise ValueError("Bootstrap email cannot be empty")

        async with self.engine.begin() as conn:
            existing = await conn.execute(
                select(self.users.c.id).where(self.users.c.email == normalized).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                return False

            effective_password = password or generate_temporary_password()
            now = _utcnow()
            await conn.execute(
                insert(self.users).values(
                    id=generate_ulid(),
                    email=normalized,
                    display_name=display_name.strip() or normalized,
                    password_hash=hash_password(effective_password),
                    role="admin",
                    is_active=True,
                    time_created=now,
                    time_updated=now,
                )
            )

        if not password:
            self._write_bootstrap_file(
                bootstrap_file,
                {
                    "email": normalized,
                    "password": effective_password,
                    "created_at": _utcnow().isoformat(),
                },
            )
        return True

    async def authenticate(self, email: str, password: str) -> CompanyUser | None:
        normalized = email.strip().lower()
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(
                    self.users.c.id,
                    self.users.c.email,
                    self.users.c.display_name,
                    self.users.c.password_hash,
                    self.users.c.role,
                    self.users.c.is_active,
                )
                .where(self.users.c.email == normalized)
                .limit(1)
            )
            row = result.mappings().first()

        if row is None or not row["is_active"]:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return self._user_from_mapping(row)

    async def list_users(self) -> list[CompanyUser]:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(
                    self.users.c.id,
                    self.users.c.email,
                    self.users.c.display_name,
                    self.users.c.role,
                    self.users.c.is_active,
                ).order_by(self.users.c.time_created.asc())
            )
            rows = result.mappings().all()
        return [self._user_from_mapping(row) for row in rows]

    async def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        role: str = "user",
    ) -> CompanyUser:
        normalized = email.strip().lower()
        if not normalized:
            raise ValueError("Email cannot be empty")
        if not password:
            raise ValueError("Password cannot be empty")
        safe_role = role.strip().lower() if role.strip().lower() in {"admin", "user"} else "user"
        now = _utcnow()
        user_id = generate_ulid()
        async with self.engine.begin() as conn:
            await conn.execute(
                insert(self.users).values(
                    id=user_id,
                    email=normalized,
                    display_name=display_name.strip() or normalized,
                    password_hash=hash_password(password),
                    role=safe_role,
                    is_active=True,
                    time_created=now,
                    time_updated=now,
                )
            )
            row = (
                await conn.execute(
                    select(
                        self.users.c.id,
                        self.users.c.email,
                        self.users.c.display_name,
                        self.users.c.role,
                        self.users.c.is_active,
                    ).where(self.users.c.id == user_id)
                )
            ).mappings().one()
        return self._user_from_mapping(row)

    async def update_user(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        password: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> CompanyUser | None:
        values: dict = {"time_updated": _utcnow()}
        if display_name is not None:
            values["display_name"] = display_name.strip()
        if password is not None:
            if not password:
                raise ValueError("Password cannot be empty")
            values["password_hash"] = hash_password(password)
        if role is not None:
            safe_role = role.strip().lower()
            if safe_role not in {"admin", "user"}:
                raise ValueError("Role must be admin or user")
            values["role"] = safe_role
        if is_active is not None:
            values["is_active"] = bool(is_active)

        async with self.engine.begin() as conn:
            result = await conn.execute(
                update(self.users)
                .where(self.users.c.id == user_id)
                .values(**values)
            )
            if (result.rowcount or 0) == 0:
                return None
            row = (
                await conn.execute(
                    select(
                        self.users.c.id,
                        self.users.c.email,
                        self.users.c.display_name,
                        self.users.c.role,
                        self.users.c.is_active,
                    ).where(self.users.c.id == user_id)
                )
            ).mappings().one()
        return self._user_from_mapping(row)

    def _add_missing_columns(self, sync_conn) -> None:
        inspector = inspect(sync_conn)
        existing = {column["name"] for column in inspector.get_columns(self.sessions.name)}
        table = sync_conn.dialect.identifier_preparer.quote(self.sessions.name)
        columns = {
            "device_id": "VARCHAR(128)",
            "device_name": "VARCHAR(255)",
            "platform": "VARCHAR(50)",
            "app_version": "VARCHAR(64)",
            "ip_address": "VARCHAR(64)",
            "user_agent": "TEXT",
            "revoked_by_user_id": "VARCHAR(32)",
            "revoked_by_email": "VARCHAR(255)",
            "revoked_reason": "TEXT",
        }
        for name, ddl_type in columns.items():
            if name not in existing:
                sync_conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")

    async def create_session(
        self,
        user_id: str,
        *,
        device_id: str = "",
        device_name: str = "",
        platform: str = "",
        app_version: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ) -> CompanySession:
        token = generate_session_token()
        now = _utcnow()
        expires_at = now + timedelta(days=self.session_days)
        session_id = generate_ulid()
        async with self.engine.begin() as conn:
            await conn.execute(
                insert(self.sessions).values(
                    id=session_id,
                    user_id=user_id,
                    token_hash=hash_token(token),
                    expires_at=expires_at,
                    revoked_at=None,
                    time_created=now,
                    last_seen_at=now,
                    device_id=str(device_id or "").strip(),
                    device_name=str(device_name or "").strip(),
                    platform=str(platform or "").strip().lower(),
                    app_version=str(app_version or "").strip().lstrip("vV"),
                    ip_address=str(ip_address or "").strip(),
                    user_agent=str(user_agent or "").strip()[:1000],
                    revoked_by_user_id="",
                    revoked_by_email="",
                    revoked_reason="",
                )
            )
        return CompanySession(id=session_id, token=token, expires_at=expires_at)

    async def get_session_user(self, token: str) -> CompanyUser | None:
        context = await self.get_session_context(token)
        return context.user if context is not None else None

    async def get_session_context(self, token: str) -> CompanySessionContext | None:
        if not token:
            return None
        now = _utcnow()
        token_digest = hash_token(token)
        async with self.engine.begin() as conn:
            result = await conn.execute(
                select(
                    self.sessions.c.id.label("session_id"),
                    self.sessions.c.device_id,
                    self.sessions.c.device_name,
                    self.sessions.c.platform,
                    self.sessions.c.app_version,
                    self.users.c.id,
                    self.users.c.email,
                    self.users.c.display_name,
                    self.users.c.role,
                    self.users.c.is_active,
                )
                .select_from(self.sessions.join(self.users, self.sessions.c.user_id == self.users.c.id))
                .where(
                    and_(
                        self.sessions.c.token_hash == token_digest,
                        self.sessions.c.revoked_at.is_(None),
                        self.sessions.c.expires_at > now,
                        self.users.c.is_active.is_(True),
                    )
                )
                .limit(1)
            )
            row = result.mappings().first()
            if row is None:
                return None
            await conn.execute(
                update(self.sessions)
                .where(self.sessions.c.token_hash == token_digest)
                .values(last_seen_at=now)
            )
        return CompanySessionContext(
            user=self._user_from_mapping(row),
            session_id=row["session_id"],
            device_id=row["device_id"] or "",
            device_name=row["device_name"] or "",
            platform=row["platform"] or "",
            app_version=row["app_version"] or "",
        )

    async def revoke_session(self, token: str) -> bool:
        if not token:
            return False
        async with self.engine.begin() as conn:
            result = await conn.execute(
                update(self.sessions)
                .where(
                    and_(
                        self.sessions.c.token_hash == hash_token(token),
                        self.sessions.c.revoked_at.is_(None),
                    )
                )
                .values(revoked_at=_utcnow())
            )
            return (result.rowcount or 0) > 0

    async def revoke_session_by_id(
        self,
        session_id: str,
        *,
        revoked_by_user_id: str = "",
        revoked_by_email: str = "",
        reason: str = "",
    ) -> int:
        if not session_id:
            return 0
        now = _utcnow()
        async with self.engine.begin() as conn:
            result = await conn.execute(
                update(self.sessions)
                .where(
                    and_(
                        self.sessions.c.id == session_id,
                        self.sessions.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now,
                    revoked_by_user_id=str(revoked_by_user_id or "").strip(),
                    revoked_by_email=str(revoked_by_email or "").strip(),
                    revoked_reason=str(reason or "").strip(),
                )
            )
        return int(result.rowcount or 0)

    async def revoke_sessions(
        self,
        *,
        session_ids: list[str] | None = None,
        user_ids: list[str] | None = None,
        revoked_by_user_id: str = "",
        revoked_by_email: str = "",
        reason: str = "",
    ) -> int:
        clean_session_ids = [value for value in (session_ids or []) if value]
        clean_user_ids = [value for value in (user_ids or []) if value]
        if not clean_session_ids and not clean_user_ids:
            return 0
        conditions = [self.sessions.c.revoked_at.is_(None)]
        id_conditions = []
        if clean_session_ids:
            id_conditions.append(self.sessions.c.id.in_(clean_session_ids))
        if clean_user_ids:
            id_conditions.append(self.sessions.c.user_id.in_(clean_user_ids))
        conditions.append(id_conditions[0] if len(id_conditions) == 1 else id_conditions[0] | id_conditions[1])
        now = _utcnow()
        async with self.engine.begin() as conn:
            result = await conn.execute(
                update(self.sessions)
                .where(and_(*conditions))
                .values(
                    revoked_at=now,
                    revoked_by_user_id=str(revoked_by_user_id or "").strip(),
                    revoked_by_email=str(revoked_by_email or "").strip(),
                    revoked_reason=str(reason or "").strip(),
                )
            )
        return int(result.rowcount or 0)

    async def list_sessions(
        self,
        *,
        include_revoked: bool = False,
        user_id: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[int, list[CompanySessionRecord]]:
        stmt = (
            select(
                self.sessions.c.id,
                self.sessions.c.user_id,
                self.sessions.c.expires_at,
                self.sessions.c.revoked_at,
                self.sessions.c.time_created,
                self.sessions.c.last_seen_at,
                self.sessions.c.device_id,
                self.sessions.c.device_name,
                self.sessions.c.platform,
                self.sessions.c.app_version,
                self.sessions.c.ip_address,
                self.sessions.c.user_agent,
                self.sessions.c.revoked_by_user_id,
                self.sessions.c.revoked_by_email,
                self.sessions.c.revoked_reason,
                self.users.c.email.label("user_email"),
                self.users.c.display_name.label("user_display_name"),
                self.users.c.role.label("user_role"),
                self.users.c.is_active.label("user_is_active"),
            )
            .select_from(self.sessions.join(self.users, self.sessions.c.user_id == self.users.c.id))
            .order_by(self.sessions.c.last_seen_at.desc())
        )
        count_stmt = select(func.count()).select_from(self.sessions)
        if not include_revoked:
            stmt = stmt.where(self.sessions.c.revoked_at.is_(None))
            count_stmt = count_stmt.where(self.sessions.c.revoked_at.is_(None))
        if user_id:
            stmt = stmt.where(self.sessions.c.user_id == user_id)
            count_stmt = count_stmt.where(self.sessions.c.user_id == user_id)
        stmt = stmt.offset(max(0, int(offset or 0))).limit(min(max(int(limit or 200), 1), 500))
        async with self.engine.connect() as conn:
            total = (await conn.execute(count_stmt)).scalar_one()
            rows = (await conn.execute(stmt)).mappings().all()
        return int(total or 0), [self._session_record_from_mapping(row) for row in rows]

    async def activity_days(self, *, days: int = 30) -> list[CompanyActivityDay]:
        total, sessions = await self.list_sessions(include_revoked=True, limit=10_000)
        del total
        today = _utcnow().date()
        start = today - timedelta(days=max(1, days) - 1)
        buckets: dict[str, dict[str, set[str] | int]] = {
            (start + timedelta(days=offset)).isoformat(): {"users": set(), "sessions": 0}
            for offset in range(max(1, days))
        }
        for session in sessions:
            day = session.last_seen_at.date()
            if day < start or day > today:
                continue
            key = day.isoformat()
            bucket = buckets.setdefault(key, {"users": set(), "sessions": 0})
            users = bucket["users"]
            if isinstance(users, set):
                users.add(session.user_id)
            bucket["sessions"] = int(bucket["sessions"]) + 1
        return [
            CompanyActivityDay(
                date=day,
                active_users=len(bucket["users"]) if isinstance(bucket["users"], set) else 0,
                session_count=int(bucket["sessions"]),
            )
            for day, bucket in sorted(buckets.items())
        ]

    async def get_model_policy(self) -> CompanyModelPolicy:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(self.settings.c.value).where(self.settings.c.key == "model_policy").limit(1)
            )
            raw = result.scalar_one_or_none()
        if not raw:
            return _default_model_policy()
        try:
            payload = json.loads(raw)
        except Exception:
            return _default_model_policy()
        return self._policy_from_payload(payload)

    async def update_model_policy(
        self,
        *,
        default_provider_id: str,
        default_model_id: str,
        models: list[dict],
    ) -> CompanyModelPolicy:
        existing_policy = await self.get_model_policy()
        policy = self._policy_from_payload(
            {
                "default_provider_id": default_provider_id,
                "default_model_id": default_model_id,
                "models": models,
            },
            strict=True,
            existing=existing_policy,
        )
        payload = json.dumps(self._policy_to_payload(policy), ensure_ascii=False)
        now = _utcnow()
        async with self.engine.begin() as conn:
            existing = await conn.execute(
                select(self.settings.c.key).where(self.settings.c.key == "model_policy").limit(1)
            )
            if existing.scalar_one_or_none() is None:
                await conn.execute(
                    insert(self.settings).values(
                        key="model_policy",
                        value=payload,
                        time_updated=now,
                    )
                )
            else:
                await conn.execute(
                    update(self.settings)
                    .where(self.settings.c.key == "model_policy")
                    .values(value=payload, time_updated=now)
                )
        return policy

    async def get_update_policy(self) -> CompanyUpdatePolicy:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(self.settings.c.value).where(self.settings.c.key == "update_policy").limit(1)
            )
            raw = result.scalar_one_or_none()
        if not raw:
            return _default_update_policy()
        try:
            payload = json.loads(raw)
        except Exception:
            return _default_update_policy()
        return self._update_policy_from_payload(payload)

    async def update_update_policy(
        self,
        *,
        enabled: bool,
        latest_version: str,
        min_supported_version: str,
        force_update: bool,
        release_notes: str,
        macos_asset_id: str = "",
        windows_asset_id: str = "",
        linux_asset_id: str = "",
        default_asset_id: str = "",
        macos_download_url: str = "",
        windows_download_url: str = "",
        linux_download_url: str = "",
        default_download_url: str = "",
    ) -> CompanyUpdatePolicy:
        policy = self._update_policy_from_payload(
            {
                "enabled": enabled,
                "latest_version": latest_version,
                "min_supported_version": min_supported_version,
                "force_update": force_update,
                "release_notes": release_notes,
                "macos_asset_id": macos_asset_id,
                "windows_asset_id": windows_asset_id,
                "linux_asset_id": linux_asset_id,
                "default_asset_id": default_asset_id,
                "macos_download_url": macos_download_url,
                "windows_download_url": windows_download_url,
                "linux_download_url": linux_download_url,
                "default_download_url": default_download_url,
            },
            strict=True,
        )
        payload = json.dumps(self._update_policy_to_payload(policy), ensure_ascii=False)
        now = _utcnow()
        async with self.engine.begin() as conn:
            existing = await conn.execute(
                select(self.settings.c.key).where(self.settings.c.key == "update_policy").limit(1)
            )
            if existing.scalar_one_or_none() is None:
                await conn.execute(
                    insert(self.settings).values(
                        key="update_policy",
                        value=payload,
                        time_updated=now,
                    )
                )
            else:
                await conn.execute(
                    update(self.settings)
                    .where(self.settings.c.key == "update_policy")
                    .values(value=payload, time_updated=now)
                )
        return policy

    async def create_update_asset(
        self,
        *,
        platform: str,
        version: str,
        original_filename: str,
        stored_filename: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        uploaded_by_user_id: str,
        uploaded_by_email: str,
        uploaded_by_display_name: str,
    ) -> CompanyUpdateAsset:
        normalized_platform = self._normalise_update_platform(platform, strict=True)
        normalized_version = str(version or "").strip().lstrip("vV")
        if not normalized_version:
            raise ValueError("Update asset version is required")
        normalized_sha = str(sha256 or "").strip().lower()
        if len(normalized_sha) != 64:
            raise ValueError("Update asset SHA-256 must be 64 hex characters")

        asset_id = generate_ulid()
        now = _utcnow()
        async with self.engine.begin() as conn:
            await conn.execute(
                insert(self.update_assets).values(
                    id=asset_id,
                    platform=normalized_platform,
                    version=normalized_version,
                    original_filename=str(original_filename or "").strip(),
                    stored_filename=str(stored_filename or "").strip(),
                    mime_type=str(mime_type or "").strip(),
                    size_bytes=max(0, int(size_bytes or 0)),
                    sha256=normalized_sha,
                    uploaded_by_user_id=str(uploaded_by_user_id or "").strip(),
                    uploaded_by_email=str(uploaded_by_email or "").strip(),
                    uploaded_by_display_name=str(uploaded_by_display_name or "").strip(),
                    download_count=0,
                    time_created=now,
                    time_updated=now,
                )
            )
        asset = await self.get_update_asset(asset_id)
        if asset is None:
            raise RuntimeError("Created update asset could not be loaded")
        return asset

    async def list_update_assets(self) -> list[CompanyUpdateAsset]:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(self.update_assets).order_by(self.update_assets.c.time_created.asc())
            )
            return [self._update_asset_from_mapping(row) for row in result.mappings().all()]

    async def get_update_asset(self, asset_id: str) -> CompanyUpdateAsset | None:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(self.update_assets).where(self.update_assets.c.id == asset_id).limit(1)
            )
            row = result.mappings().first()
        return self._update_asset_from_mapping(row) if row is not None else None

    async def increment_update_asset_download_count(self, asset_id: str) -> CompanyUpdateAsset | None:
        now = _utcnow()
        async with self.engine.begin() as conn:
            existing = await conn.execute(
                select(self.update_assets.c.download_count)
                .where(self.update_assets.c.id == asset_id)
                .limit(1)
            )
            current = existing.scalar_one_or_none()
            if current is None:
                return None
            await conn.execute(
                update(self.update_assets)
                .where(self.update_assets.c.id == asset_id)
                .values(download_count=int(current) + 1, time_updated=now)
            )
        return await self.get_update_asset(asset_id)

    async def create_feedback(
        self,
        *,
        user_id: str,
        user_email: str,
        user_display_name: str,
        description: str,
        image_original_filename: str = "",
        image_stored_filename: str = "",
        image_mime_type: str = "",
        image_size_bytes: int = 0,
        image_sha256: str = "",
    ) -> CompanyFeedback:
        normalized_description = str(description or "").strip()
        if not normalized_description:
            raise ValueError("Feedback description is required")
        normalized_sha = str(image_sha256 or "").strip().lower()
        if normalized_sha and len(normalized_sha) != 64:
            raise ValueError("Feedback image SHA-256 must be 64 hex characters")

        feedback_id = generate_ulid()
        now = _utcnow()
        async with self.engine.begin() as conn:
            await conn.execute(
                insert(self.feedback).values(
                    id=feedback_id,
                    user_id=str(user_id or "").strip(),
                    user_email=str(user_email or "").strip(),
                    user_display_name=str(user_display_name or "").strip(),
                    description=normalized_description,
                    image_original_filename=str(image_original_filename or "").strip(),
                    image_stored_filename=str(image_stored_filename or "").strip(),
                    image_mime_type=str(image_mime_type or "").strip(),
                    image_size_bytes=max(0, int(image_size_bytes or 0)),
                    image_sha256=normalized_sha,
                    time_created=now,
                    time_updated=now,
                )
            )
        feedback = await self.get_feedback(feedback_id)
        if feedback is None:
            raise RuntimeError("Created feedback could not be loaded")
        return feedback

    async def list_feedback(self) -> list[CompanyFeedback]:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(self.feedback).order_by(self.feedback.c.time_created.desc())
            )
            return [self._feedback_from_mapping(row) for row in result.mappings().all()]

    async def get_feedback(self, feedback_id: str) -> CompanyFeedback | None:
        async with self.engine.connect() as conn:
            result = await conn.execute(
                select(self.feedback).where(self.feedback.c.id == feedback_id).limit(1)
            )
            row = result.mappings().first()
        return self._feedback_from_mapping(row) if row is not None else None

    @staticmethod
    def _write_bootstrap_file(path: Path, payload: dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _user_from_mapping(row) -> CompanyUser:
        return CompanyUser(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            role=row["role"],
            is_active=bool(row["is_active"]),
        )

    @staticmethod
    def _session_record_from_mapping(row) -> CompanySessionRecord:
        return CompanySessionRecord(
            id=row["id"],
            user_id=row["user_id"],
            user_email=row["user_email"],
            user_display_name=row["user_display_name"],
            user_role=row["user_role"],
            user_is_active=bool(row["user_is_active"]),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            time_created=row["time_created"],
            last_seen_at=row["last_seen_at"],
            device_id=row["device_id"] or "",
            device_name=row["device_name"] or "",
            platform=row["platform"] or "",
            app_version=row["app_version"] or "",
            ip_address=row["ip_address"] or "",
            user_agent=row["user_agent"] or "",
            revoked_by_user_id=row["revoked_by_user_id"] or "",
            revoked_by_email=row["revoked_by_email"] or "",
            revoked_reason=row["revoked_reason"] or "",
        )

    @staticmethod
    def _update_asset_from_mapping(row) -> CompanyUpdateAsset:
        return CompanyUpdateAsset(
            id=row["id"],
            platform=row["platform"],
            version=row["version"],
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            mime_type=row["mime_type"],
            size_bytes=int(row["size_bytes"] or 0),
            sha256=row["sha256"],
            uploaded_by_user_id=row["uploaded_by_user_id"],
            uploaded_by_email=row["uploaded_by_email"],
            uploaded_by_display_name=row["uploaded_by_display_name"],
            download_count=int(row["download_count"] or 0),
            time_created=row["time_created"],
            time_updated=row["time_updated"],
        )

    @staticmethod
    def _normalise_update_platform(value: str | None, *, strict: bool = False) -> str:
        raw = (value or "default").strip().lower()
        aliases = {
            "darwin": "macos",
            "mac": "macos",
            "macos": "macos",
            "osx": "macos",
            "win": "windows",
            "win32": "windows",
            "win64": "windows",
            "windows": "windows",
            "linux": "linux",
            "linux-x64": "linux",
            "ubuntu": "linux",
            "debian": "linux",
            "default": "default",
        }
        normalized = aliases.get(raw, raw)
        if strict and normalized not in {"macos", "windows", "linux", "default"}:
            raise ValueError(f"Unsupported update asset platform: {value}")
        return normalized

    @staticmethod
    def _feedback_from_mapping(row) -> CompanyFeedback:
        return CompanyFeedback(
            id=row["id"],
            user_id=row["user_id"],
            user_email=row["user_email"],
            user_display_name=row["user_display_name"],
            description=row["description"],
            image_original_filename=row["image_original_filename"],
            image_stored_filename=row["image_stored_filename"],
            image_mime_type=row["image_mime_type"],
            image_size_bytes=int(row["image_size_bytes"] or 0),
            image_sha256=row["image_sha256"],
            time_created=row["time_created"],
            time_updated=row["time_updated"],
        )

    @staticmethod
    def _policy_from_payload(
        payload: dict,
        *,
        strict: bool = False,
        existing: CompanyModelPolicy | None = None,
    ) -> CompanyModelPolicy:
        default = _default_model_policy()
        if not isinstance(payload, dict):
            if strict:
                raise ValueError("Model policy must be an object")
            return default

        entries: list[CompanyModelEntry] = []
        seen: set[tuple[str, str]] = set()
        default_by_model = {(entry.provider_id, entry.id): entry for entry in default.models}
        existing_models = list(existing.models) if existing is not None else []
        existing_by_model = {(entry.provider_id, entry.id): entry for entry in existing_models}
        existing_by_provider = {entry.provider_id: entry for entry in existing_models}
        raw_models = payload.get("models")
        if isinstance(raw_models, list):
            for raw in raw_models:
                if not isinstance(raw, dict):
                    continue
                provider_id = str(raw.get("provider_id") or "").strip()
                model_id = str(raw.get("id") or raw.get("model_id") or "").strip()
                if not provider_id or not model_id:
                    continue
                key = (provider_id, model_id)
                if key in seen:
                    continue
                seen.add(key)
                fallback = existing_by_model.get(key) or default_by_model.get(key) or existing_by_provider.get(provider_id)
                protocol = _normalise_model_protocol(
                    str(raw.get("protocol") or (fallback.protocol if fallback else "openai_compatible"))
                )
                if strict and protocol not in {"openai_compatible", "anthropic"}:
                    raise ValueError(f"Unsupported model protocol: {protocol}")
                base_url = str(raw.get("base_url") or (fallback.base_url if fallback else "")).strip()
                if protocol == "anthropic":
                    base_url = ""
                api_key = str(raw.get("api_key") or "").strip()
                if not api_key and fallback is not None:
                    api_key = fallback.api_key
                if strict:
                    if protocol == "openai_compatible" and not base_url:
                        raise ValueError("Base URL is required for OpenAI-compatible models")
                    if not api_key:
                        if protocol == "anthropic":
                            raise ValueError("API key is required for Anthropic models")
                        raise ValueError("API key is required for OpenAI-compatible models")
                entries.append(
                    CompanyModelEntry(
                        provider_id=provider_id,
                        id=model_id,
                        name=str(raw.get("name") or model_id).strip() or model_id,
                        protocol=protocol,
                        base_url=base_url,
                        api_key=api_key,
                    )
                )
        if not entries:
            if strict:
                raise ValueError("At least one model must be allowed")
            entries = list(default.models)

        if strict:
            provider_configs: dict[str, tuple[str, str, str]] = {}
            for entry in entries:
                config = (entry.protocol, entry.base_url, entry.api_key)
                existing_config = provider_configs.get(entry.provider_id)
                if existing_config is not None and existing_config != config:
                    raise ValueError("Models with the same provider_id must use the same protocol, Base URL and API key")
                provider_configs[entry.provider_id] = config

        default_provider_id = str(payload.get("default_provider_id") or default.default_provider_id).strip()
        default_model_id = str(payload.get("default_model_id") or default.default_model_id).strip()
        if (default_provider_id, default_model_id) not in {(entry.provider_id, entry.id) for entry in entries}:
            if strict:
                raise ValueError("Default model must be present in the allowed model list")
            default_provider_id = entries[0].provider_id
            default_model_id = entries[0].id

        return CompanyModelPolicy(
            default_provider_id=default_provider_id,
            default_model_id=default_model_id,
            models=entries,
        )

    @staticmethod
    def _policy_to_payload(policy: CompanyModelPolicy) -> dict:
        return {
            "default_provider_id": policy.default_provider_id,
            "default_model_id": policy.default_model_id,
            "models": [
                {
                    "provider_id": model.provider_id,
                    "id": model.id,
                    "name": model.name,
                    "protocol": model.protocol,
                    "base_url": model.base_url,
                    "api_key": model.api_key,
                }
                for model in policy.models
            ],
        }

    @staticmethod
    def _update_policy_from_payload(payload: dict, *, strict: bool = False) -> CompanyUpdatePolicy:
        if not isinstance(payload, dict):
            if strict:
                raise ValueError("Update policy must be an object")
            return _default_update_policy()

        latest_version = str(payload.get("latest_version") or "").strip().lstrip("vV")
        min_supported_version = str(payload.get("min_supported_version") or "").strip().lstrip("vV")
        enabled = bool(payload.get("enabled", False))
        if strict and enabled and not latest_version:
            raise ValueError("Latest version is required when update policy is enabled")

        return CompanyUpdatePolicy(
            enabled=enabled,
            latest_version=latest_version,
            min_supported_version=min_supported_version,
            force_update=bool(payload.get("force_update", False)),
            release_notes=str(payload.get("release_notes") or "").strip(),
            macos_asset_id=str(payload.get("macos_asset_id") or "").strip(),
            windows_asset_id=str(payload.get("windows_asset_id") or "").strip(),
            linux_asset_id=str(payload.get("linux_asset_id") or "").strip(),
            default_asset_id=str(payload.get("default_asset_id") or "").strip(),
            macos_download_url=str(payload.get("macos_download_url") or "").strip(),
            windows_download_url=str(payload.get("windows_download_url") or "").strip(),
            linux_download_url=str(payload.get("linux_download_url") or "").strip(),
            default_download_url=str(payload.get("default_download_url") or "").strip(),
        )

    @staticmethod
    def _update_policy_to_payload(policy: CompanyUpdatePolicy) -> dict:
        return {
            "enabled": policy.enabled,
            "latest_version": policy.latest_version,
            "min_supported_version": policy.min_supported_version,
            "force_update": policy.force_update,
            "release_notes": policy.release_notes,
            "macos_asset_id": policy.macos_asset_id,
            "windows_asset_id": policy.windows_asset_id,
            "linux_asset_id": policy.linux_asset_id,
            "default_asset_id": policy.default_asset_id,
            "macos_download_url": policy.macos_download_url,
            "windows_download_url": policy.windows_download_url,
            "linux_download_url": policy.linux_download_url,
            "default_download_url": policy.default_download_url,
        }
