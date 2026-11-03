"""
config.py — Application configuration loaded from environment variables.

All settings are read from a .env file (or from the real environment).
We use pydantic-settings so that every required variable is validated
at startup — the app refuses to boot if something is missing.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """
    Central configuration object.
    Values are pulled from the .env file in the quiz-backend/ directory,
    then overridden by actual environment variables if they exist.
    """

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Media uploads ─────────────────────────────────────────────────────────
    MEDIA_DIR: str = "media"
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_VIDEO_UPLOAD_SIZE_MB: int = 100

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Stored as a single comma-separated string in .env, parsed to a list here.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── Miscellaneous ─────────────────────────────────────────────────────────
    ENVIRONMENT: str = "production"

    model_config = SettingsConfigDict(
        env_file=".env",          # look for .env in the current working directory
        env_file_encoding="utf-8",
        extra="ignore",           # silently ignore unrecognised variables
    )

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def jwt_secret_must_be_long_enough(cls, v: str) -> str:
        """Refuse to start with a weak signing secret."""
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters long. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a Python list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """Return the maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached Settings instance.
    The @lru_cache means we only read the .env file once per process,
    which is fast and avoids repeated I/O.
    """
    return Settings()
