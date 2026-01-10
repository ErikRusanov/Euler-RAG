"""Pytest configuration and shared fixtures."""

import os
from collections.abc import AsyncGenerator
from typing import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application import create_app
from app.config import Settings, get_settings
from app.utils.db import Base


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings instance with test-specific configuration.

    Returns:
        Test settings instance with test database configuration.
    """
    # Load .env file if it exists to get DB_PASSWORD
    from dotenv import load_dotenv

    load_dotenv()

    # Override environment variables for testing
    os.environ["API_TITLE"] = "Euler RAG Test"
    os.environ["API_VERSION"] = "0.1.0-test"
    os.environ["DEBUG"] = "True"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["HOST"] = "127.0.0.1"
    os.environ["PORT"] = "8000"

    # Database settings for tests - use test database
    # Keep DB_HOST, DB_PORT, DB_USER, DB_PASSWORD from .env if set
    if "DB_HOST" not in os.environ:
        os.environ["DB_HOST"] = "localhost"
    if "DB_PORT" not in os.environ:
        os.environ["DB_PORT"] = "5432"
    if "DB_USER" not in os.environ:
        os.environ["DB_USER"] = "postgres"
    if "DB_PASSWORD" not in os.environ:
        # If no password in .env, try empty password
        os.environ["DB_PASSWORD"] = ""

    # Always use test database name
    os.environ["DB_NAME"] = "euler_rag_test"

    # Logging
    os.environ["LOG_LEVEL"] = "DEBUG"

    # Security - use test API key
    os.environ["API_KEY"] = "test-api-key-for-testing"

    # Clear the cache to force reload with test settings
    get_settings.cache_clear()

    return get_settings()


@pytest.fixture
def settings(test_settings: Settings) -> Settings:
    """Provide test settings to individual tests.

    Args:
        test_settings: Session-scoped test settings.

    Returns:
        Test settings instance.
    """
    return test_settings


@pytest.fixture(scope="function")
async def db_session(test_settings: Settings) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing with automatic cleanup.

    Each test gets a fresh session with all tables created.
    After the test, all data is truncated to ensure test isolation.

    Args:
        test_settings: Test configuration settings.

    Yields:
        Database session for testing.
    """
    # Build test database URL
    db_url = test_settings.database_url

    # Create engine with test configuration
    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )

    # Create all tables if needed
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Provide session
    async with session_factory() as session:
        yield session
        # Rollback any uncommitted changes
        await session.rollback()

    # Clean up tables after each test to ensure isolation
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE")
            )

    # Dispose engine
    await engine.dispose()


@pytest.fixture
def app(test_settings: Settings) -> Generator:
    """Create FastAPI application instance for testing.

    The application is created with test settings and without
    database initialization (handled separately in tests).

    Args:
        test_settings: Test configuration settings.

    Yields:
        FastAPI application instance.
    """
    # Mock init_db, close_db, init_s3, close_s3 to prevent actual connections
    # during app creation
    with patch("app.application.init_db", new_callable=AsyncMock) as mock_init_db:
        with patch("app.application.close_db", new_callable=AsyncMock) as mock_close_db:
            with patch("app.application.init_s3") as mock_init_s3:
                with patch("app.application.close_s3") as mock_close_s3:
                    mock_init_db.return_value = None
                    mock_close_db.return_value = None
                    mock_init_s3.return_value = None
                    mock_close_s3.return_value = None

                    app = create_app()
                    yield app


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """Create synchronous test client for FastAPI application.

    Args:
        app: FastAPI application instance.

    Yields:
        TestClient for making synchronous HTTP requests.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client for FastAPI application.

    Args:
        app: FastAPI application instance.

    Yields:
        AsyncClient for making asynchronous HTTP requests.
    """
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client
