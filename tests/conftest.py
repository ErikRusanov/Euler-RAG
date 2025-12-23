"""Pytest configuration and shared fixtures."""

import os
import pytest
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.application import create_app
from app.config import Settings


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings instance."""
    # Override environment variables for testing
    os.environ.setdefault("API_TITLE", "Euler RAG Test")
    os.environ.setdefault("API_VERSION", "0.1.0-test")
    os.environ.setdefault("DEBUG", "True")
    os.environ.setdefault("HOST", "127.0.0.1")
    os.environ.setdefault("PORT", "8000")

    return Settings()


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
