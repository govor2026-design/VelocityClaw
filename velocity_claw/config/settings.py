import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


def parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    lowered = str(value).strip().lower()
    return lowered in {"1", "true", "yes", "on"}


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
    api_host: str = "0.0.0.0"
    api_port: int = 8000
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

    def __post_init__(self):
        self.env = os.getenv("ENV", self.env)
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.safe_mode = parse_bool(os.getenv("SAFE_MODE"), self.safe_mode)
        self.dev_mode = parse_bool(os.getenv("DEV_MODE"), self.dev_mode)
        self.trusted_mode = parse_bool(os.getenv("TRUSTED_MODE"), self.trusted_mode)
        self.memory_enabled = parse_bool(os.getenv("MEMORY_ENABLED"), self.memory_enabled)
        self.memory_db_path = os.getenv("MEMORY_DB_PATH", self.memory_db_path)
        self.api_host = os.getenv("API_HOST", self.api_host)
        self.api_port = int(os.getenv("API_PORT", self.api_port))
        self.telegram_token = os.getenv("TELEGRAM_TOKEN", self.telegram_token)
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", self.telegram_chat_id)
        self.openai_api_key = os.getenv("OPENAI_API_KEY", self.openai_api_key)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", self.openrouter_api_key)
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", self.anthropic_api_key)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", self.gemini_api_key)
        self.ollama_url = os.getenv("OLLAMA_URL", self.ollama_url)
        self.allowed_users = parse_list(os.getenv("ALLOWED_USERS"))
        self.default_model = os.getenv("DEFAULT_MODEL", self.default_model)
        self.lightweight_mode = parse_bool(os.getenv("LIGHTWEIGHT_MODE"), self.lightweight_mode)

    @property
    def provider_order(self) -> List[str]:
        return ["openai", "openrouter", "anthropic", "gemini", "ollama"]

    @property
    def safe_mode_prompt(self) -> str:
        from velocity_claw.prompts.safe_mode import SAFE_MODE_PROMPT

        return SAFE_MODE_PROMPT


def load_settings() -> Settings:
    return Settings()
