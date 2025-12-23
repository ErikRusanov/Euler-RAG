"""Application configuration."""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        """Initialize settings from environment variables."""
        # API Settings
        self.API_TITLE: str = os.getenv("API_TITLE", "Euler RAG")
        self.API_VERSION: str = os.getenv("API_VERSION", "0.1.0")
        self.DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

        # Server Settings
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        # Database Settings
        self.DB_HOST: str = os.getenv("DB_HOST", "localhost")
        self.DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
        self.DB_USER: str = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
        self.DB_NAME: str = os.getenv("DB_NAME", "euler_rag")


# Global settings instance
settings = Settings()
