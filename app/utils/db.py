"""Database connection utilities with proper dependency injection."""

import logging
from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models using modern DeclarativeBase."""


class DatabaseManager:
    """Database manager handling engine lifecycle and session creation.

    This class encapsulates database connection management and provides
    dependency injection for database sessions.
    """

    def __init__(self) -> None:
        """Initialize database manager with None values."""
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def init_engine(self) -> AsyncEngine:
        """Initialize and return database engine.

        Creates engine only once and reuses it for subsequent calls.
        Uses connection pooling and pre-ping for connection health checks.
        """
        if self._engine is not None:
            return self._engine

        settings = get_settings()

        self._engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,  # Verify connections before using
            future=True,  # Use SQLAlchemy 2.0 style
        )

        logger.info(
            "Database engine initialized",
            extra={
                "host": settings.db_host,
                "port": settings.db_port,
                "database": settings.db_name,
            },
        )

        return self._engine

    def init_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Initialize and return session factory.

        Creates session factory only once and reuses it.
        Sessions created by this factory are properly configured.
        """
        if self._session_factory is not None:
            return self._session_factory

        engine = self.init_engine()

        self._session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
            autoflush=False,  # Manual flush control
            autocommit=False,  # Manual commit control
        )

        logger.info("Database session factory initialized")

        return self._session_factory

    async def verify_connection(self) -> bool:
        """Verify database connection is working.

        Returns:
            True if connection is successful, False otherwise.

        Raises:
            Exception: If connection fails with detailed error.
        """
        try:
            engine = self.init_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully")
            return True
        except Exception as e:
            logger.error(f"Database connection verification failed: {e}")
            raise

    async def close(self) -> None:
        """Close database engine and clean up connections.

        Should be called during application shutdown.
        """
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("Database engine disposed")
            self._engine = None
            self._session_factory = None

    @property
    def engine(self) -> AsyncEngine:
        """Get engine instance, initializing if needed."""
        return self.init_engine()

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get session factory, initializing if needed."""
        return self.init_session_factory()


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Provides properly configured database session with automatic
    transaction management and cleanup.

    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db_session)):
            users = await User.get_all(db)
            return users

    Yields:
        AsyncSession: Database session with automatic cleanup.
    """
    session_factory = db_manager.init_session_factory()

    async with session_factory() as session:
        try:
            yield session
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()  # Auto-rollback on error
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection.

    Verifies that database connection works properly.
    Does NOT run migrations automatically - migrations should be run
    explicitly via alembic CLI in production.

    Raises:
        Exception: If database connection fails.
    """
    logger.info("Initializing database connection...")
    await db_manager.verify_connection()
    logger.info("Database initialized successfully")


async def close_db() -> None:
    """Close database connections.

    Should be called during application shutdown.
    """
    logger.info("Closing database connections...")
    await db_manager.close()
    logger.info("Database connections closed")
