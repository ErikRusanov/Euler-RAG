"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation and type safety.

    Uses pydantic-settings for automatic environment variable loading
    with proper type conversion and validation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    # API Settings
    api_title: str = Field(default="Euler RAG", description="API title")
    api_version: str = Field(default="0.1.0", description="API version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Application environment"
    )

    # Server Settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")

    # Database Settings
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    db_user: str = Field(default="postgres", description="Database user")
    db_password: str = Field(default="", description="Database password")
    db_name: str = Field(default="euler_rag", description="Database name")

    # Database connection pool settings
    db_pool_size: int = Field(
        default=5, ge=1, le=50, description="Database connection pool size"
    )
    db_max_overflow: int = Field(
        default=10, ge=0, le=100, description="Database max overflow connections"
    )
    db_pool_timeout: int = Field(
        default=30, ge=1, description="Database pool timeout in seconds"
    )
    db_pool_recycle: int = Field(
        default=3600,
        ge=60,
        description="Database connection recycle time in seconds",
    )

    # Logging Settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    @field_validator("db_password")
    @classmethod
    def validate_db_password_in_production(cls, v: str, info) -> str:
        """Ensure database password is set in production."""
        # Access environment through info.data instead of values
        environment = info.data.get("environment", "development")
        if environment == "production" and not v:
            raise ValueError("Database password must be set in production")
        return v

    @property
    def database_url(self) -> str:
        """Build async PostgreSQL database URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        """Build sync PostgreSQL database URL for Alembic migrations."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.

    Using lru_cache ensures we only create one Settings instance
    and reuse it throughout the application lifecycle.
    """
    return Settings()


# Convenience instance for backward compatibility
settings = get_settings()
