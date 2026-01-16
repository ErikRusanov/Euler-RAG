"""Pytest configuration and shared fixtures."""

import os
from collections.abc import AsyncGenerator
from typing import Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from app.application import create_app
from app.config import Settings, get_settings
from app.models.base import BaseModel
from app.utils.db import Base
from app.utils.s3 import S3Storage, s3_manager


# Test model for integration tests (not prefixed with Test to avoid pytest collection)
class IntegrationUser(BaseModel):
    """Model for service integration tests."""

    __tablename__ = "integration_users"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings with test database configuration."""
    from dotenv import load_dotenv

    load_dotenv()

    os.environ["API_TITLE"] = "Euler RAG Test"
    os.environ["API_VERSION"] = "0.1.0-test"
    os.environ["DEBUG"] = "True"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["HOST"] = "127.0.0.1"
    os.environ["PORT"] = "8000"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["API_KEY"] = "test-api-key-for-testing"

    if "DB_HOST" not in os.environ:
        os.environ["DB_HOST"] = "localhost"
    if "DB_PORT" not in os.environ:
        os.environ["DB_PORT"] = "5432"
    if "DB_USER" not in os.environ:
        os.environ["DB_USER"] = "postgres"
    if "DB_PASSWORD" not in os.environ:
        os.environ["DB_PASSWORD"] = ""

    os.environ["DB_NAME"] = "euler_rag_test"

    # Use separate Redis database for tests (db=1)
    # to avoid conflicts with running app (db=0)
    os.environ["REDIS_DB"] = "1"

    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def settings(test_settings: Settings) -> Settings:
    """Provide test settings to individual tests."""
    return test_settings


# Tables created specifically for tests (will be dropped after session)
TEST_ONLY_TABLES = [
    "integration_users",
    "test_users",  # Legacy from old tests
    "test_service_users",  # Legacy from old tests
]


@pytest.fixture(scope="function")
async def db_session(test_settings: Settings) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing with automatic cleanup.

    IMPORTANT: Tests run against euler_rag_test database (never production).
    After each test, ALL tables are truncated to ensure isolation.
    """
    db_url = test_settings.database_url

    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )

    # Create all tables (application + test tables)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()

    # Truncate ALL tables in test database to ensure test isolation
    # This is safe because we always use euler_rag_test database
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE")
            )

    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database(test_settings: Settings):
    """Clean test database before and after test session.

    - Before: Truncate all tables to ensure clean state
    - After: Drop test-only tables
    """
    import asyncio

    async def truncate_all_tables():
        """Truncate all tables at session start."""
        engine = create_async_engine(test_settings.database_url)
        async with engine.begin() as conn:
            # Create tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)
            # Truncate all tables
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(
                    text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE")
                )
        await engine.dispose()

    async def drop_test_tables():
        """Drop test-only tables at session end."""
        engine = create_async_engine(test_settings.database_url)
        async with engine.begin() as conn:
            for table_name in TEST_ONLY_TABLES:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        await engine.dispose()

    # Before tests: clean slate
    asyncio.run(truncate_all_tables())

    yield  # Run all tests

    # After tests: drop test-only tables
    asyncio.run(drop_test_tables())


@pytest.fixture
def app(test_settings: Settings) -> Generator:
    """Create FastAPI application instance for testing."""
    from app.utils.db import get_db_session

    with patch("app.application.init_db", new_callable=AsyncMock) as mock_init_db:
        with patch("app.application.close_db", new_callable=AsyncMock) as mock_close_db:
            with patch("app.application.init_s3") as mock_init_s3:
                with patch("app.application.close_s3") as mock_close_s3:
                    mock_init_db.return_value = None
                    mock_close_db.return_value = None
                    mock_init_s3.return_value = None
                    mock_close_s3.return_value = None

                    # Mock s3_manager.storage so get_s3_storage() works
                    mock_s3_storage = MagicMock(spec=S3Storage)
                    s3_manager.storage = mock_s3_storage

                    application = create_app()

                    # Override get_db_session with mock session
                    mock_db_session = MagicMock(spec=AsyncSession)
                    mock_result = MagicMock()
                    mock_result.scalars.return_value.all.return_value = []
                    mock_result.scalar_one_or_none.return_value = None
                    mock_db_session.execute = AsyncMock(return_value=mock_result)

                    async def override_get_db_session():
                        yield mock_db_session

                    application.dependency_overrides[get_db_session] = (
                        override_get_db_session
                    )

                    yield application

                    # Cleanup
                    application.dependency_overrides.clear()
                    s3_manager.storage = None


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """Create synchronous test client for FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def s3_storage(test_settings: Settings) -> Optional[S3Storage]:
    """Create S3 storage instance for integration tests.

    Returns None if S3 credentials are not configured.
    Tests using this fixture should skip if None is returned.
    """
    # Check if S3 credentials are configured
    if not test_settings.s3_access_key_id or not test_settings.s3_secret_access_key:
        return None

    storage = S3Storage(
        endpoint_url=test_settings.s3_endpoint_url,
        access_key=test_settings.s3_access_key_id,
        secret_key=test_settings.s3_secret_access_key,
        bucket_name=test_settings.s3_bucket_name,
        region=test_settings.s3_region,
    )

    return storage
