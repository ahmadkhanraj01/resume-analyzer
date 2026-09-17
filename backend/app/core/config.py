"""The only module that reads os.environ. Everything else takes a Settings
instance."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# RFC 7518 section 3.2: an HMAC-SHA256 key should be at least 32 bytes.
JWT_SECRET_MIN_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite:///./dev.db"

    # Auth. No fallback default: a real secret must come from the environment.
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # LLM providers
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    # CORS: comma-separated origins, no wildcard
    cors_origins: str = "http://localhost:5173"

    # Scoring thresholds
    covered_threshold: float = 0.75
    partial_threshold: float = 0.62

    # Rate limits
    analyses_per_hour: int = 10
    analyses_per_day: int = 30
    auth_attempts_per_hour: int = 20
    max_reports_per_user: int = 50

    # Upload limits
    max_upload_bytes: int = 5 * 1024 * 1024

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_long_enough(cls, value: str) -> str:
        if len(value.encode("utf-8")) < JWT_SECRET_MIN_BYTES:
            raise ValueError(f"JWT_SECRET must be at least {JWT_SECRET_MIN_BYTES} bytes")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
