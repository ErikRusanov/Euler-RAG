"""Pytest configuration and shared fixtures."""

import os
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application import create_app
from app.config import Settings
from app.utils.db import Base


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings instance."""
    # Override environment variables for testing
    os.environ.setdefault("API_TITLE", "Euler RAG Test")
    os.environ.setdefault("API_VERSION", "0.1.0-test")
    os.environ.setdefault("DEBUG", "True")
    os.environ.setdefault("HOST", "127.0.0.1")
    os.environ.setdefault("PORT", "8000")
    # Database settings for tests - use test database
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_USER", "postgres")
    os.environ.setdefault("DB_PASSWORD", "postgres")
    os.environ.setdefault("DB_NAME", "euler_rag_test")

    return Settings()


@pytest.fixture(scope="function")
async def db_session(test_settings: Settings) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing with automatic cleanup."""
    # Build test database URL
    db_url = (
        f"postgresql+asyncpg://{test_settings.DB_USER}:{test_settings.DB_PASSWORD}"
        f"@{test_settings.DB_HOST}:{test_settings.DB_PORT}/{test_settings.DB_NAME}"
    )

    # Create engine
    engine = create_async_engine(db_url, echo=False, future=True)

    # Create all tables if needed
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Provide session
    async with session_factory() as session:
        yield session

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
    """Create FastAPI application instance for testing."""
    app = create_app()
    yield app


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """Create test client for FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client for FastAPI application."""
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client
