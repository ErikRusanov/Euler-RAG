"""Application configuration."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""
    
    # API Settings
    API_TITLE: str = os.getenv("API_TITLE", "Euler RAG")
    API_VERSION: str = os.getenv("API_VERSION", "0.1.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


# Global settings instance
settings = Settings()

