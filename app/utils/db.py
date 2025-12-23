"""Database connection utilities."""

import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

# Base class for models
Base = declarative_base()

# Global engine and session factory
_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker] = None


def get_db_url() -> str:
    """Build database URL from settings."""
    return (
        f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )


async def get_db_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        db_url = get_db_url()
        _engine = create_async_engine(
            db_url,
            echo=settings.DEBUG,
            pool_pre_ping=True,  # Verify connections before using
        )
    return _engine


async def verify_db_connection():
    """Verify database connection. Raises exception if connection fails."""
    engine = await get_db_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def run_migrations():
    """Run database migrations using Alembic."""
    import asyncio

    from alembic import command
    from alembic.config import Config

    # Get the path to alembic.ini (should be in project root)
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_ini_path.exists():
        raise FileNotFoundError(
            f"Alembic configuration file not found at {alembic_ini_path}"
        )

    # Create Alembic config
    alembic_cfg = Config(str(alembic_ini_path))

    # Set the database URL dynamically
    db_url = get_db_url()
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Run migrations using command.upgrade
    # This is synchronous but works correctly with async migrations
    # because env.py handles async internally via asyncio.run
    # We run it in a thread to avoid blocking the event loop
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


async def init_db():
    """Initialize database connection and run migrations. Exits application if connection fails."""
    try:
        # Run migrations first
        await run_migrations()
        # Then verify connection
        await verify_db_connection()
    except Exception as e:
        print(f"Failed to initialize database: {e}", file=sys.stderr)
        sys.exit(1)


async def get_session() -> AsyncSession:
    """Get database session."""
    global _session_factory
    if _session_factory is None:
        engine = await get_db_engine()
        _session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory()


async def close_db():
    """Close database connections."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
