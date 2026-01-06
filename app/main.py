"""FastAPI application entry point."""

from app.application import create_app
from app.config import get_settings
from app.utils.logging import setup_logging

# Setup logging before creating app
setup_logging()

# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
