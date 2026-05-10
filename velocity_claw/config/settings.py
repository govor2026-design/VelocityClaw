import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class SettingsValidationError(ValueError):
    pass


def parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise SettingsValidationError(f"Invalid boolean value: {value}")


def parse_int(name: str, value: Optional[str], default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    if value is None:
        parsed = default
    else:
        try:
            parsed = int(str(value).strip())
        except ValueError as exc:
            raise SettingsValidationError(f"{name} must be an integer") from exc
    if min_value is not None and parsed < min_value:
        raise SettingsValidationError(f"{name} must be >= {min_value}")
    if max_value is not None and parsed > max_value:
        raise SettingsValidationError(f"{name} must be <= {max_value}")
    return parsed


def parse_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [item.strip() for item in str(value).split(",") if item.strip()]


@dataclass
class Settings:
    env: str = "production"
    log_level: str = "INFO"
    safe_mode: bool = True
    dev_mode: bool = False
    trusted_mode: bool = False
    memory_enabled: bool = True
    memory_db_path: str = "velocity_claw_memory.db"
    memory_retention_days: int = 30
    memory_retention_min_runs: int = 10
    memory_cleanup_vacuum: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: Optional[str] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    openai_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ollama_url: str = "http://127.0.0.1:11434"
    allowed_users: List[str] = field(default_factory=list)
    default_model: str = "code"
    lightweight_mode: bool = False
    workspace_root: str = "."
    allowed_hosts: List[str] = field(default_factory=lambda: ["api.github.com", "raw.githubusercontent.com"])
    command_timeout: int = 120
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    max_http_response_bytes: int = 5 * 1024 * 1024  # 5MB
    shell_enabled: bool = False
    git_enabled: bool = False
    dry_run: bool = False
    execution_profile: str = "safe"
    provider_request_timeout_seconds: int = 60
    provider_max_retries: int = 2
    provider_retry_backoff_ms: int = 250
    provider_health_cooldown_seconds: int = 30

    def __post_init__(self):
        self.env = os.getenv("ENV", self.env).strip().lower()
        self.log_level = os.getenv("LOG_LEVEL", self.log_level).strip().upper()
        self.safe_mode = parse_bool(os.getenv("SAFE_MODE"), self.safe_mode)
        self.dev_mode = parse_bool(os.getenv("DEV_MODE"), self.dev_mode)
        self.trusted_mode = parse_bool(os.getenv("TRUSTED_MODE"), self.trusted_mode)
        self.memory_enabled = parse_bool(os.getenv("MEMORY_ENABLED"), self.memory_enabled)
        self.memory_db_path = os.getenv("MEMORY_DB_PATH", self.memory_db_path)
        self.memory_retention_days = parse_int("MEMORY_RETENTION_DAYS", os.getenv("MEMORY_RETENTION_DAYS"), self.memory_retention_days, min_value=1)
        self.memory_retention_min_runs = parse_int("MEMORY_RETENTION_MIN_RUNS", os.getenv("MEMORY_RETENTION_MIN_RUNS"), self.memory_retention_min_runs, min_value=0)
        self.memory_cleanup_vacuum = parse_bool(os.getenv("MEMORY_CLEANUP_VACUUM"), self.memory_cleanup_vacuum)
        self.api_host = os.getenv("API_HOST", self.api_host)
        self.api_port = parse_int("API_PORT", os.getenv("API_PORT"), self.api_port, min_value=1, max_value=65535)
        self.api_key = os.getenv("API_KEY", self.api_key)
        self.telegram_token = os.getenv("TELEGRAM_TOKEN", self.telegram_token)
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", self.telegram_chat_id)
        self.openai_api_key = os.getenv("OPENAI_API_KEY", self.openai_api_key)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", self.openrouter_api_key)
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", self.anthropic_api_key)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", self.gemini_api_key)
        self.ollama_url = os.getenv("OLLAMA_URL", self.ollama_url)
        self.allowed_users = parse_list(os.getenv("ALLOWED_USERS"))
        self.default_model = os.getenv("DEFAULT_MODEL", self.default_model).strip()
        self.lightweight_mode = parse_bool(os.getenv("LIGHTWEIGHT_MODE"), self.lightweight_mode)
        self.workspace_root = os.getenv("WORKSPACE_ROOT", self.workspace_root)
        self.allowed_hosts = parse_list(os.getenv("ALLOWED_HOSTS")) or self.allowed_hosts
        self.command_timeout = parse_int("COMMAND_TIMEOUT", os.getenv("COMMAND_TIMEOUT"), self.command_timeout, min_value=1)
        self.max_file_size = parse_int("MAX_FILE_SIZE", os.getenv("MAX_FILE_SIZE"), self.max_file_size, min_value=1)
        self.max_http_response_bytes = parse_int("MAX_HTTP_RESPONSE_BYTES", os.getenv("MAX_HTTP_RESPONSE_BYTES"), self.max_http_response_bytes, min_value=1)
        self.shell_enabled = parse_bool(os.getenv("SHELL_ENABLED"), self.shell_enabled)
        self.git_enabled = parse_bool(os.getenv("GIT_ENABLED"), self.git_enabled)
        self.dry_run = parse_bool(os.getenv("DRY_RUN"), self.dry_run)
        self.execution_profile = os.getenv("EXECUTION_PROFILE", self.execution_profile).strip().lower()
        self.provider_request_timeout_seconds = parse_int("PROVIDER_REQUEST_TIMEOUT_SECONDS", os.getenv("PROVIDER_REQUEST_TIMEOUT_SECONDS"), self.provider_request_timeout_seconds, min_value=1)
        self.provider_max_retries = parse_int("PROVIDER_MAX_RETRIES", os.getenv("PROVIDER_MAX_RETRIES"), self.provider_max_retries, min_value=0, max_value=10)
        self.provider_retry_backoff_ms = parse_int("PROVIDER_RETRY_BACKOFF_MS", os.getenv("PROVIDER_RETRY_BACKOFF_MS"), self.provider_retry_backoff_ms, min_value=0)
        self.provider_health_cooldown_seconds = parse_int("PROVIDER_HEALTH_COOLDOWN_SECONDS", os.getenv("PROVIDER_HEALTH_COOLDOWN_SECONDS"), self.provider_health_cooldown_seconds, min_value=0)
        self.validate()

    def validate(self) -> None:
        if self.env not in {"development", "staging", "production", "test"}:
            raise SettingsValidationError("ENV must be one of: development, staging, production, test")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise SettingsValidationError("LOG_LEVEL must be a valid Python logging level")
        if self.execution_profile not in {"safe", "dev", "owner"}:
            raise SettingsValidationError("EXECUTION_PROFILE must be one of: safe, dev, owner")
        if not self.default_model:
            raise SettingsValidationError("DEFAULT_MODEL must not be empty")
        if self.telegram_token and self.telegram_token == "your-telegram-bot-token":
            raise SettingsValidationError("TELEGRAM_TOKEN still contains placeholder value")
        if self.telegram_chat_id and not str(self.telegram_chat_id).lstrip("-").isdigit():
            raise SettingsValidationError("TELEGRAM_CHAT_ID must be numeric when provided")
        if self.env == "production" and self.trusted_mode:
            raise SettingsValidationError("TRUSTED_MODE must not be enabled in production")
        if self.env == "production" and self.execution_profile == "owner" and not self.allowed_users:
            raise SettingsValidationError("ALLOWED_USERS must be set when using owner profile in production")

    @property
    def provider_order(self) -> List[str]:
        return ["openai", "openrouter", "anthropic", "gemini", "ollama"]

    @property
    def safe_mode_prompt(self) -> str:
        from velocity_claw.prompts.safe_mode import SAFE_MODE_PROMPT

        return SAFE_MODE_PROMPT


def load_settings() -> Settings:
    return Settings()
