"""Application configuration via Pydantic Settings."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


def internal_default_custom_endpoints_json() -> str:
    """Default internal OpenAI-compatible endpoint for the company build."""
    api_key = os.environ.get("OPENYAK_INTERNAL_DEFAULT_API_KEY", "").strip()
    if not api_key:
        return "[]"
    base_url = os.environ.get("OPENYAK_INTERNAL_DEFAULT_BASE_URL", "https://sub2api.onlymeok.com/v1").strip()
    model_id = os.environ.get("OPENYAK_INTERNAL_DEFAULT_MODEL", "gpt-5.5").strip() or "gpt-5.5"
    model_name = os.environ.get("OPENYAK_INTERNAL_DEFAULT_MODEL_NAME", "GPT-5.5").strip() or model_id
    return json.dumps([
        {
            "id": "custom_onlyme",
            "slug": "onlyme",
            "name": "OnlyMe GPT-5.5",
            "base_url": base_url,
            "api_key": api_key,
            "enabled": True,
            "models": [{"id": model_id, "name": model_name}],
            "headers": {},
        }
    ])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENYAK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Provider ---
    openrouter_api_key: str = ""

    # --- Direct Provider API Keys (BYOK) ---
    openai_api_key: str = ""        # OPENYAK_OPENAI_API_KEY
    anthropic_api_key: str = ""     # OPENYAK_ANTHROPIC_API_KEY
    google_api_key: str = ""        # OPENYAK_GOOGLE_API_KEY
    groq_api_key: str = ""          # OPENYAK_GROQ_API_KEY
    deepseek_api_key: str = ""      # OPENYAK_DEEPSEEK_API_KEY
    mistral_api_key: str = ""       # OPENYAK_MISTRAL_API_KEY
    xai_api_key: str = ""           # OPENYAK_XAI_API_KEY
    together_api_key: str = ""      # OPENYAK_TOGETHER_API_KEY
    deepinfra_api_key: str = ""     # OPENYAK_DEEPINFRA_API_KEY
    cerebras_api_key: str = ""      # OPENYAK_CEREBRAS_API_KEY
    cohere_api_key: str = ""        # OPENYAK_COHERE_API_KEY
    perplexity_api_key: str = ""    # OPENYAK_PERPLEXITY_API_KEY
    fireworks_api_key: str = ""     # OPENYAK_FIREWORKS_API_KEY
    azure_openai_api_key: str = ""  # OPENYAK_AZURE_OPENAI_API_KEY
    azure_openai_base_url: str = "" # OPENYAK_AZURE_OPENAI_BASE_URL
    qwen_api_key: str = ""          # OPENYAK_QWEN_API_KEY (Alibaba DashScope)
    kimi_api_key: str = ""          # OPENYAK_KIMI_API_KEY (Moonshot)
    minimax_api_key: str = ""       # OPENYAK_MINIMAX_API_KEY
    zhipu_api_key: str = ""         # OPENYAK_ZHIPU_API_KEY (智谱 GLM)
    siliconflow_api_key: str = ""   # OPENYAK_SILICONFLOW_API_KEY (硅基流动)
    xiaomi_api_key: str = ""        # OPENYAK_XIAOMI_API_KEY (MiMo)
    custom_endpoints: str = internal_default_custom_endpoints_json()  # OPENYAK_CUSTOM_ENDPOINTS

    # Comma-separated list of provider IDs to disable (e.g. "groq,deepseek")
    # Disabled providers are not registered even if their API key is set.
    disabled_providers: str = ""  # OPENYAK_DISABLED_PROVIDERS
    provider_configuration_locked: bool = True

    # --- Optional hosted proxy for managed tools such as web search ---
    proxy_url: str = ""
    proxy_token: str = ""
    proxy_refresh_token: str = ""

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/openyak.db"

    # --- Company login (business-user auth, separate from local bearer token) ---
    enterprise_control_url: str = "http://120.26.208.161:5201"
    company_auth_enabled: bool = False
    company_auth_database_url: str = ""
    company_auth_mysql_host: str = ""
    company_auth_mysql_port: int = 3306
    company_auth_mysql_user: str = ""
    company_auth_mysql_password: str = ""
    company_auth_mysql_database: str = ""
    company_auth_table_prefix: str = "fpi_desk"
    company_auth_bootstrap_email: str = "admin"
    company_auth_bootstrap_display_name: str = "Admin"
    company_auth_bootstrap_password: str = ""
    company_auth_bootstrap_file: str = "company_auth_bootstrap.json"
    company_auth_session_days: int = 30

    # --- Enterprise audit sync ---
    audit_sync_enabled: bool = False
    audit_server_url: str = ""
    audit_sync_timeout: float = 10.0
    audit_file_upload_enabled: bool = True
    audit_file_upload_max_bytes: int = 200 * 1024 * 1024
    audit_file_storage_dir: str = "data/audit_uploads"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    # Dev-only fixed session token. Used by npm run dev:all so the Next.js
    # dev server can authenticate browser-originated /api requests without
    # weakening backend auth. Ignored unless allow_dev_session_token=True.
    allow_dev_session_token: bool = False
    dev_session_token: str = ""
    local_api_auth_enabled: bool = True

    # --- Project ---
    project_dir: str = "."

    # --- Web Search ---
    daily_search_limit: int = 20  # Max free web_search calls per day (Free/BYOK)
    web_search_context_size: str = "low"  # "low" | "medium" | "high" — native search breadth (OpenAI subscription)
    max_native_searches_per_step: int = 5  # cap on native web searches per agent step

    # --- Sandbox execution ---
    # "required" refuses shell/code execution unless the configured sandbox can
    # be started. "auto" uses the sandbox when available and falls back to host
    # execution when unavailable. "off" restores direct host execution.
    sandbox_mode: str = "auto"  # required | auto | off
    sandbox_provider: str = "local"  # local | docker | tencent
    sandbox_image: str = "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest"
    sandbox_container_prefix: str = "fpi-desk-sandbox"
    sandbox_port_start: int = 28080
    sandbox_data_dir: str = "data/sandboxes"
    sandbox_client_timeout: int = 600
    tencent_sandbox_domain: str = "ap-guangzhou.tencentags.com"
    tencent_sandbox_template: str = "code-2qj6gcgh6oa"
    tencent_sandbox_lifetime: int = 3600
    tencent_sandbox_api_key: str = ""
    tencent_sandbox_validate_api_key: bool = False
    tencent_sandbox_api_key_cache_path: str = "tencent_sandbox_api_key"
    tencent_sandbox_auto_create_api_key: bool = True
    tencent_sandbox_key_name: str = "fpi-desk-agent"
    tencent_sandbox_region: str = "ap-beijing"
    tencent_sandbox_max_concurrent: int = 2
    tencent_sandbox_acquire_timeout: int = 120
    tencent_sandbox_create_retries: int = 2
    tencent_sandbox_retry_backoff: float = 1.0
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""

    # --- Compaction ---
    compaction_auto: bool = True
    compaction_reserved: int = 20_000

    # --- Agents (loaded from YAML) ---
    agents: dict[str, Any] | None = None

    # --- MCP (loaded from YAML) ---
    mcp: dict[str, Any] | None = None

    # --- OpenAI OAuth (ChatGPT Subscription) ---
    openai_oauth_access_token: str = ""
    openai_oauth_refresh_token: str = ""
    openai_oauth_account_id: str = ""
    openai_oauth_expires_at: int = 0  # milliseconds since epoch
    openai_oauth_email: str = ""

    # --- Google Workspace MCP Proxy ---
    google_client_id: str = ""
    google_client_secret: str = ""

    # --- Ollama (Local LLM) ---
    ollama_base_url: str = ""  # e.g. "http://localhost:11434" — empty = not configured
    ollama_auto_start: bool = True  # Auto-start managed Ollama binary on app launch
    ollama_last_model: str = ""  # Last-used model name for startup pre-warming

    # --- Rapid-MLX (Apple Silicon local LLM) ---
    rapid_mlx_base_url: str = ""  # e.g. "http://localhost:8000/v1" — empty = not configured
    rapid_mlx_auto_start: bool = True
    rapid_mlx_model: str = "qwen3.5-4b"

    # --- Local OpenAI-compatible endpoint ---
    local_base_url: str = ""  # OPENYAK_LOCAL_BASE_URL

    # --- Brave Search ---
    brave_search_api_key: str = ""

    # --- Full-Text Search ---
    fts_enabled: bool = True  # built-in FTS5, enabled by default (zero external deps)
    fts_auto_index: bool = True  # auto-index workspace on first access
    fts_poll_interval: float = 30.0  # seconds between re-index polls
    fts_max_file_size: int = 500_000  # bytes — skip files larger than this

    # --- Agent Limits ---
    max_steps: int = 50  # hard cap on agent loop iterations
    max_continuation_attempts: int = 10  # max nudges for incomplete todos
    max_tool_output_chars: int = 20_000  # truncate individual tool results beyond this
    max_assistant_content_chars: int = 40_000  # truncate accumulated assistant text
    max_request_context_chars: int = 160_000  # hard cap on total prompt size
    hard_max_output_tokens: int = 8192  # max tokens the model can generate per step
    min_output_tokens: int = 256  # minimum output tokens floor
    tool_timeout: int = 300  # seconds — per-tool execution timeout
    max_concurrent_generations: int = 20  # max parallel generation jobs

    # --- Tool Limits ---
    bash_timeout: int = 120  # default bash command timeout (seconds)
    bash_max_timeout: int = 600  # maximum bash timeout (seconds)
    subtask_max_depth: int = 3  # max nesting for sub-agent tasks
    subtask_timeout: int = 600  # seconds — sub-agent task timeout

    # --- Loop Detection ---
    loop_warn_threshold: int = 3  # warn after N repeated identical tool calls
    loop_hard_limit: int = 5  # hard-block after N repeated identical tool calls

    # --- Scheduler ---
    scheduler_poll_interval: int = 30  # seconds between task schedule checks
    scheduler_max_concurrent: int = 3  # max concurrent scheduled tasks

    # --- Shutdown ---
    shutdown_timeout: float = 8.0  # seconds to wait for active jobs on shutdown

    # --- Rate Limiting (remote access) ---
    rate_limit_max_requests: int = 120  # max requests per minute
    rate_limit_max_failed_auth: int = 5  # max failed auth attempts per minute

    # --- CSRF / Origin protection ---
    # Comma-separated list of additional allowed origins (exact match) for
    # cross-site state-changing requests. The defaults already cover the
    # Tauri desktop shell, loopback, and the Next.js dev server — only set
    # this to extend for unusual deployments (e.g. a custom web wrapper).
    extra_allowed_origins: str = ""  # OPENYAK_EXTRA_ALLOWED_ORIGINS

    # --- Messaging Channels (nanobot-based, in-process) ---
    channels_enabled: bool = True  # OPENYAK_CHANNELS_ENABLED
    channels_config_path: str = ""  # OPENYAK_CHANNELS_CONFIG_PATH (default: data/channels.json)

    # --- Remote Access ---
    remote_access_enabled: bool = False
    remote_token_path: str = "data/remote_token.json"
    remote_tunnel_mode: str = "cloudflare"  # "cloudflare" | "manual"
    remote_tunnel_url: str = ""  # Manual tunnel URL (when mode="manual")
    remote_permission_mode: str = "auto"  # "auto" | "ask" | "deny"

    # --- Local session auth ---
    # Rotated every backend start, written 0600 so another local user on a
    # shared host cannot read it. The desktop shell (Tauri) reads this file
    # after spawning the backend and injects the token on every request —
    # it never leaves the filesystem through the network layer.
    #
    # Path may be relative (resolved against cwd) or absolute. The
    # production launcher (``run.py``) chdirs into ``--data-dir`` and then
    # the Tauri shell polls ``<data_dir>/session_token.json``, so the
    # default below assumes that working-directory contract. Override via
    # the ``OPENYAK_SESSION_TOKEN_PATH`` env var when the contract differs
    # (the dev launcher does this — see ``scripts/dev-desktop.mjs`` —
    # because it runs uvicorn without invoking ``run.py``, so cwd stays
    # at ``backend/`` and the file needs to land under ``backend/data/``
    # to match what Tauri dev mode reads).
    session_token_path: str = "session_token.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_company_auth_database_url(settings: Settings) -> str:
    """Return the SQLAlchemy URL used by the company-auth store."""
    if settings.company_auth_database_url.strip():
        return settings.company_auth_database_url.strip()
    if not (
        settings.company_auth_mysql_host
        and settings.company_auth_mysql_user
        and settings.company_auth_mysql_database
    ):
        return ""
    user = quote_plus(settings.company_auth_mysql_user)
    password = quote_plus(settings.company_auth_mysql_password)
    host = settings.company_auth_mysql_host
    port = settings.company_auth_mysql_port
    database = settings.company_auth_mysql_database
    return (
        f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
        "?charset=utf8mb4"
    )

def get_custom_endpoints(settings: Settings) -> list[dict[str, Any]]:
    """Read + normalize the persisted custom endpoint list.

    Old entries (pre-v2 schema) only have ``id/name/base_url/api_key/enabled``.
    We synthesize the new fields on read so the rest of the app can rely on
    them being present:

    * ``slug``: derived from ``id`` by stripping the ``custom_`` prefix
      (so a UUID-suffixed legacy ID like ``custom_abc12345`` reads back as
      slug ``abc12345`` — ugly but stable and unique).
    * ``models``: empty list (= auto-discover via /v1/models).
    * ``headers``: empty dict.
    """
    try:
        data = json.loads(settings.custom_endpoints)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    normalized: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        endpoint_id = str(entry.get("id", "") or "")
        if not endpoint_id:
            continue
        slug = entry.get("slug")
        if not isinstance(slug, str) or not slug:
            slug = endpoint_id[len("custom_"):] if endpoint_id.startswith("custom_") else endpoint_id

        raw_models = entry.get("models")
        models: list[dict[str, Any]] = []
        if isinstance(raw_models, list):
            for m in raw_models:
                if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]:
                    models.append({"id": m["id"], "name": m.get("name")})

        raw_headers = entry.get("headers")
        headers: dict[str, str] = {}
        if isinstance(raw_headers, dict):
            for k, v in raw_headers.items():
                if isinstance(k, str) and isinstance(v, str) and k.strip():
                    headers[k.strip()] = v

        normalized.append({
            "id": endpoint_id,
            "slug": slug,
            "name": entry.get("name") or "Custom Endpoint",
            "base_url": entry.get("base_url", "") or "",
            "api_key": entry.get("api_key", "") or "",
            "enabled": bool(entry.get("enabled", True)),
            "models": models,
            "headers": headers,
        })
    return normalized
