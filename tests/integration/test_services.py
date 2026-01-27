"""Integration tests for service layer with transaction management.

Tests the BaseService behavior using a concrete implementation.
All services inherit from BaseService, so testing one is sufficient.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    RecordNotFoundError,
)
from app.services.base import BaseService

# Import test model from conftest to avoid duplicate table definition
from tests.conftest import IntegrationUser


class UserService(BaseService[IntegrationUser]):
    """Test service for integration tests."""

    model = IntegrationUser


@pytest.mark.asyncio
async def test_create_commits_automatically(db_session: AsyncSession):
    """Create operation flushes changes to database."""
    service = UserService(db_session)

    user = await service.create(name="John", email="john@example.com")
    await db_session.commit()

    assert user.id is not None
    found = await service.get_by_id(user.id)
    assert found is not None
    assert found.name == "John"


@pytest.mark.asyncio
async def test_create_rollback_on_constraint_violation(db_session: AsyncSession):
    """Create rolls back on unique constraint violation."""
    service = UserService(db_session)
    await service.create(name="John", email="john@example.com")
    await db_session.commit()

    with pytest.raises(DatabaseConnectionError):
        await service.create(name="Jane", email="john@example.com")

    users = await service.get_all()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_update_commits_automatically(db_session: AsyncSession):
    """Update operation flushes changes to database."""
    service = UserService(db_session)
    user = await service.create(name="Old", email="user@example.com")
    await db_session.commit()

    updated = await service.update(user.id, name="New")
    await db_session.commit()

    assert updated.name == "New"
    found = await service.get_by_id(user.id)
    assert found.name == "New"


@pytest.mark.asyncio
async def test_update_rollback_on_constraint_violation(db_session: AsyncSession):
    """Update rolls back on unique constraint violation."""
    service = UserService(db_session)
    await service.create(name="User1", email="user1@example.com")
    user2 = await service.create(name="User2", email="user2@example.com")
    await db_session.commit()
    user2_id = user2.id  # Save id before potential session invalidation

    with pytest.raises(DatabaseConnectionError):
        await service.update(user2_id, email="user1@example.com")

    found = await service.get_by_id(user2_id)
    assert found.email == "user2@example.com"


@pytest.mark.asyncio
async def test_delete_commits_automatically(db_session: AsyncSession):
    """Delete operation flushes changes to database."""
    service = UserService(db_session)
    user = await service.create(name="Delete Me", email="delete@example.com")
    await db_session.commit()
    user_id = user.id

    await service.delete(user_id)
    await db_session.commit()

    found = await service.get_by_id(user_id)
    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_returns_existing(db_session: AsyncSession):
    """get_by_id returns existing record."""
    service = UserService(db_session)
    user = await service.create(name="Test", email="test@example.com")
    await db_session.commit()

    found = await service.get_by_id(user.id)

    assert found is not None
    assert found.id == user.id


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_missing(db_session: AsyncSession):
    """get_by_id returns None for non-existent ID."""
    service = UserService(db_session)

    found = await service.get_by_id(9999)

    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_or_fail_raises_for_missing(db_session: AsyncSession):
    """get_by_id_or_fail raises RecordNotFoundError."""
    service = UserService(db_session)

    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.get_by_id_or_fail(9999)

    assert exc_info.value.record_id == 9999


@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session: AsyncSession):
    """get_all supports limit and offset."""
    service = UserService(db_session)
    for i in range(5):
        await service.create(name=f"User{i}", email=f"user{i}@example.com")
    await db_session.commit()

    page1 = await service.get_all(limit=2, offset=0)
    page2 = await service.get_all(limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_find_filters_records(db_session: AsyncSession):
    """find filters records by criteria."""
    service = UserService(db_session)
    await service.create(name="Alice", email="alice@example.com")
    await service.create(name="Bob", email="bob@example.com")
    await service.create(name="Alice", email="alice2@example.com")
    await db_session.commit()

    found = await service.find(name="Alice")

    assert len(found) == 2
    assert all(u.name == "Alice" for u in found)


@pytest.mark.asyncio
async def test_find_raises_for_invalid_filter(db_session: AsyncSession):
    """find raises InvalidFilterError for invalid field."""
    service = UserService(db_session)

    with pytest.raises(InvalidFilterError):
        await service.find(invalid_field="value")


@pytest.mark.asyncio
async def test_count_counts_records(db_session: AsyncSession):
    """count returns record count."""
    service = UserService(db_session)
    await service.create(name="Alice", email="alice@example.com")
    await service.create(name="Bob", email="bob@example.com")
    await db_session.commit()

    total = await service.count()
    alice_count = await service.count(name="Alice")

    assert total == 2
    assert alice_count == 1


@pytest.mark.asyncio
async def test_update_raises_for_invalid_attribute(db_session: AsyncSession):
    """update raises InvalidFilterError for invalid attribute."""
    service = UserService(db_session)
    user = await service.create(name="Test", email="test@example.com")
    await db_session.commit()

    with pytest.raises(InvalidFilterError):
        await service.update(user.id, invalid_field="value")


@pytest.mark.asyncio
async def test_update_raises_for_missing_record(db_session: AsyncSession):
    """update raises RecordNotFoundError for missing ID."""
    service = UserService(db_session)

    with pytest.raises(RecordNotFoundError):
        await service.update(9999, name="New")


@pytest.mark.asyncio
async def test_delete_raises_for_missing_record(db_session: AsyncSession):
    """delete raises RecordNotFoundError for missing ID."""
    service = UserService(db_session)

    with pytest.raises(RecordNotFoundError):
        await service.delete(9999)
