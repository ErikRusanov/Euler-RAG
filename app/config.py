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

    # Security Settings
    api_key: str = Field(
        default="",
        description="API key for authentication",
        min_length=1,
    )
    cors_origins: list[str] = Field(
        default_factory=list,
        description="Allowed CORS origins for production",
    )

    # S3 Storage Settings
    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        description="S3-compatible storage endpoint URL",
    )
    s3_access_key_id: str = Field(
        default="",
        description="S3 access key ID",
    )
    s3_secret_access_key: str = Field(
        default="",
        description="S3 secret access key",
    )
    s3_bucket_name: str = Field(
        default="euler-rag",
        description="S3 bucket name",
    )
    s3_region: str = Field(
        default="us-east-1",
        description="S3 region",
    )

    # Redis Settings
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    redis_password: str = Field(default="", description="Redis password")

    # Worker Settings
    worker_concurrency: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of concurrent worker tasks",
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

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        """Ensure API key is set and secure."""
        environment = info.data.get("environment", "development")
        if not v:
            raise ValueError("API key must be set")
        if environment == "production" and len(v) < 32:
            raise ValueError("API key must be at least 32 characters in production")
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
    def redis_url(self) -> str:
        """Build Redis connection URL."""
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}@{self.redis_host}"
                f":{self.redis_port}/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

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
