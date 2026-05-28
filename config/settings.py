from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    telegram_bot_token: str = Field(..., min_length=10)
    bot_mode: Literal["polling", "webhook"] = "polling"
    webhook_base_url: str = ""
    webhook_secret: str = "change-me"
    render_external_url: str = ""

    openai_api_key: str = Field(..., min_length=10)
    openai_model: str = "gpt-4o"
    openai_max_output_tokens: int = 1800

    database_url: str = "sqlite+aiosqlite:///./data/sales_qa.sqlite3"

    ocr_language: str = "rus+eng"
    tesseract_cmd: str = ""

    max_images_per_session: int = 10
    max_image_mb: int = 15
    session_ttl_minutes: int = 30
    album_debounce_seconds: int = 4
    rate_limit_per_minute: int = 6
    delete_images_after_analysis: bool = True

    admin_user_ids: set[int] = Field(default_factory=set)

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admins(cls, value: object) -> set[int]:
        if value in (None, ""):
            return set()
        if isinstance(value, set):
            return value
        if isinstance(value, str):
            return {int(item.strip()) for item in value.split(",") if item.strip()}
        if isinstance(value, list):
            return {int(item) for item in value}
        raise ValueError("ADMIN_USER_IDS must be comma-separated integers")

    @property
    def webhook_url(self) -> str:
        base_url = self.webhook_base_url or self.render_external_url
        return f"{base_url.rstrip('/')}/telegram/webhook/{self.webhook_secret}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
