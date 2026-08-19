from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    # LLM
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    model_name: str = "deepseek-chat"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Auth (token HMAC tự ký - xem src/services/auth.py; đổi secret_key khi deploy that)
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None
    google_client_id: str = ""
    enable_demo_accounts: bool = False

    # Transactional email. In development/test, missing SMTP settings cause the
    # verification URL to be logged instead of silently activating the account.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_FROM", "SMTP_FROM_EMAIL"),
    )
    smtp_from_name: str = ""
    smtp_starttls: bool = Field(
        default=True,
        validation_alias=AliasChoices("SMTP_STARTTLS", "SMTP_USE_TLS"),
    )

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_production_auth_settings(settings: Settings) -> None:
    if settings.app_env != "production":
        return
    problems: list[str] = []
    if settings.secret_key == "dev-secret-change-me" or len(settings.secret_key) < 32:
        problems.append("SECRET_KEY phai la gia tri ngau nhien it nhat 32 ky tu")
    if not settings.cookie_secure:
        problems.append("COOKIE_SECURE phai bat trong production")
    if not settings.google_client_id:
        problems.append("GOOGLE_CLIENT_ID chua duoc cau hinh")
    if not settings.smtp_host or not settings.smtp_from:
        problems.append("SMTP_HOST/SMTP_FROM chua duoc cau hinh")
    if problems:
        raise RuntimeError("Cau hinh auth production khong hop le: " + "; ".join(problems))
