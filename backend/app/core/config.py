from functools import lru_cache
from pathlib import Path
import secrets

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str
    cors_origins: str = "http://localhost:5173"
    jwt_secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(48))
    )
    access_token_expire_minutes: int = 10
    refresh_token_expire_days: int = 30
    quiz_duration_minutes: int = 20
    quiz_question_count: int = 15
    refresh_cookie_name: str = "smart_school_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    refresh_cookie_domain: str | None = None
    refresh_cookie_path: str = "/api/v1/auth"
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 900
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_auth_settings(self) -> "Settings":
        if not self.jwt_secret_key.get_secret_value() and self.app_env.lower() != "production":
            self.jwt_secret_key = SecretStr(secrets.token_urlsafe(48))
        if self.app_env.lower() == "production":
            if "jwt_secret_key" not in self.model_fields_set:
                raise ValueError("JWT_SECRET_KEY must be configured in production.")
            if len(self.jwt_secret_key.get_secret_value()) < 32:
                raise ValueError("JWT_SECRET_KEY must contain at least 32 characters.")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be enabled in production.")
            if "*" in self.cors_origin_list:
                raise ValueError("Wildcard CORS origins are not allowed in production.")
        if self.access_token_expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive.")
        if self.refresh_token_expire_days < 1:
            raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS must be positive.")
        if self.quiz_duration_minutes < 1:
            raise ValueError("QUIZ_DURATION_MINUTES must be positive.")
        if self.quiz_question_count < 1:
            raise ValueError("QUIZ_QUESTION_COUNT must be positive.")
        if self.login_rate_limit_attempts < 1 or self.login_rate_limit_window_seconds < 1:
            raise ValueError("Login rate-limit settings must be positive.")
        if self.refresh_cookie_samesite.lower() not in {"strict", "lax", "none"}:
            raise ValueError("REFRESH_COOKIE_SAMESITE must be Strict, Lax, or None.")
        if self.refresh_cookie_samesite.lower() == "none" and not self.refresh_cookie_secure:
            raise ValueError("Secure cookies are required when SameSite=None.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
