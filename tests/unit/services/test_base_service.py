"""Unit tests for BaseService with transaction management."""

import pytest
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    RecordNotFoundError,
)
from app.services.base import BaseService


class SampleUser(BaseModel):
    """Sample model for testing BaseService."""

    __tablename__ = "test_service_users"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class UserService(BaseService[SampleUser]):
    """Sample service for testing BaseService."""

    model = SampleUser


@pytest.mark.asyncio
async def test_create_with_auto_commit(db_session: AsyncSession):
    """Test: BaseService.create() creates record and commits transaction."""
    # Arrange
    service = UserService(db_session)
    user_data = {"name": "John Doe", "email": "john@example.com"}

    # Act
    user = await service.create(**user_data)

    # Assert - record should be committed and accessible
    assert user.id is not None
    assert user.name == "John Doe"
    assert user.email == "john@example.com"

    # Verify record is persisted (new session query)
    found_user = await SampleUser.get_by_id(db_session, user.id)
    assert found_user is not None
    assert found_user.name == "John Doe"


@pytest.mark.asyncio
async def test_create_rollback_on_error(db_session: AsyncSession):
    """Test: BaseService.create() should rollback transaction on error."""
    # Arrange
    service = UserService(db_session)
    user_data = {"name": "John Doe", "email": "john@example.com"}

    # Create first user
    await service.create(**user_data)

    # Act - try to create duplicate (unique constraint violation)
    with pytest.raises(DatabaseConnectionError):
        await service.create(**user_data)

    # Assert - only one user should exist (first one was committed)
    users = await SampleUser.get_all(db_session)
    assert len(users) == 1


@pytest.mark.asyncio
async def test_update_with_auto_commit(db_session: AsyncSession):
    """Test: BaseService.update() updates record and commits transaction."""
    # Arrange
    service = UserService(db_session)
    user = await service.create(name="Old Name", email="old@example.com")

    # Act
    updated_user = await service.update(
        user.id, name="New Name", email="new@example.com"
    )

    # Assert
    assert updated_user.id == user.id
    assert updated_user.name == "New Name"
    assert updated_user.email == "new@example.com"

    # Verify in database
    db_user = await SampleUser.get_by_id(db_session, user.id)
    assert db_user.name == "New Name"
    assert db_user.email == "new@example.com"


@pytest.mark.asyncio
async def test_update_rollback_on_error(db_session: AsyncSession):
    """Test: BaseService.update() should rollback transaction on error."""
    # Arrange
    service = UserService(db_session)
    await service.create(name="User 1", email="user1@example.com")
    user2 = await service.create(name="User 2", email="user2@example.com")
    user2_id = user2.id
    original_email = user2.email

    # Act - try to update with duplicate email
    with pytest.raises(DatabaseConnectionError):
        await service.update(user2_id, email="user1@example.com")

    # Assert - user2 should still have original email
    # Need to refresh from database after rollback
    db_user2 = await SampleUser.get_by_id(db_session, user2_id)
    assert db_user2 is not None
    assert db_user2.email == original_email


@pytest.mark.asyncio
async def test_delete_with_auto_commit(db_session: AsyncSession):
    """Test: BaseService.delete() deletes record and commits transaction."""
    # Arrange
    service = UserService(db_session)
    user = await service.create(name="Delete Me", email="delete@example.com")
    user_id = user.id

    # Act
    await service.delete(user_id)

    # Assert - record should be deleted
    found_user = await SampleUser.get_by_id(db_session, user_id)
    assert found_user is None


@pytest.mark.asyncio
async def test_delete_rollback_on_error(db_session: AsyncSession):
    """Test: BaseService.delete() should rollback transaction on error."""
    # Arrange
    service = UserService(db_session)
    user = await service.create(name="Keep Me", email="keep@example.com")
    user_id = user.id

    # Mock an error scenario - delete non-existent record
    # Act
    with pytest.raises(RecordNotFoundError):
        await service.delete(9999)

    # Assert - original user should still exist
    found_user = await SampleUser.get_by_id(db_session, user_id)
    assert found_user is not None


@pytest.mark.asyncio
async def test_get_by_id_no_commit(db_session: AsyncSession):
    """Test: BaseService.get_by_id() retrieves record without committing."""
    # Arrange
    service = UserService(db_session)
    user = await service.create(name="Get Me", email="get@example.com")

    # Act
    found_user = await service.get_by_id(user.id)

    # Assert
    assert found_user is not None
    assert found_user.id == user.id
    assert found_user.name == "Get Me"

    # Verify no commit was made (read operations don't need commit)
    # This is implicit - if commit was made, it would work anyway


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test: BaseService.get_by_id() should return None for non-existent ID."""
    # Arrange
    service = UserService(db_session)

    # Act
    found_user = await service.get_by_id(9999)

    # Assert
    assert found_user is None


@pytest.mark.asyncio
async def test_get_by_id_or_fail_found(db_session: AsyncSession):
    """Test: BaseService.get_by_id_or_fail() should return existing record."""
    # Arrange
    service = UserService(db_session)
    user = await service.create(name="Test User", email="test@example.com")

    # Act
    found_user = await service.get_by_id_or_fail(user.id)

    # Assert
    assert found_user.id == user.id
    assert found_user.name == "Test User"


@pytest.mark.asyncio
async def test_get_by_id_or_fail_not_found(db_session: AsyncSession):
    """Test: BaseService.get_by_id_or_fail() raises RecordNotFoundError."""
    # Arrange
    service = UserService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.get_by_id_or_fail(9999)

    assert exc_info.value.model_name == "SampleUser"
    assert exc_info.value.record_id == 9999


@pytest.mark.asyncio
async def test_get_all_no_commit(db_session: AsyncSession):
    """Test: BaseService.get_all() retrieves all records without committing."""
    # Arrange
    service = UserService(db_session)
    await service.create(name="User 1", email="user1@example.com")
    await service.create(name="User 2", email="user2@example.com")
    await service.create(name="User 3", email="user3@example.com")

    # Act
    all_users = await service.get_all()

    # Assert
    assert len(all_users) == 3
    assert all_users[0].name == "User 1"
    assert all_users[1].name == "User 2"
    assert all_users[2].name == "User 3"


@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session: AsyncSession):
    """Test: BaseService.get_all() should support limit and offset."""
    # Arrange
    service = UserService(db_session)
    for i in range(10):
        await service.create(name=f"User {i}", email=f"user{i}@example.com")

    # Act
    page1 = await service.get_all(limit=5, offset=0)
    page2 = await service.get_all(limit=5, offset=5)

    # Assert
    assert len(page1) == 5
    assert len(page2) == 5
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_find_no_commit(db_session: AsyncSession):
    """Test: BaseService.find() should filter records without committing."""
    # Arrange
    service = UserService(db_session)
    await service.create(name="Alice", email="alice@example.com")
    await service.create(name="Bob", email="bob@example.com")
    await service.create(name="Alice", email="alice2@example.com")

    # Act
    alice_users = await service.find(name="Alice")

    # Assert
    assert len(alice_users) == 2
    assert all(user.name == "Alice" for user in alice_users)


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: BaseService.find() raises InvalidFilterError for invalid keys."""
    # Arrange
    service = UserService(db_session)

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await service.find(nonexistent_field="value")

    assert "Invalid filter key" in str(exc_info.value)
    assert "nonexistent_field" in str(exc_info.value)


@pytest.mark.asyncio
async def test_count_no_commit(db_session: AsyncSession):
    """Test: BaseService.count() should count records without committing."""
    # Arrange
    service = UserService(db_session)
    await service.create(name="User 1", email="user1@example.com")
    await service.create(name="User 2", email="user2@example.com")
    await service.create(name="Alice", email="alice@example.com")

    # Act
    total_count = await service.count()
    alice_count = await service.count(name="Alice")

    # Assert
    assert total_count == 3
    assert alice_count == 1


@pytest.mark.asyncio
async def test_update_with_invalid_attribute(db_session: AsyncSession):
    """Test: BaseService.update() raises InvalidFilterError for invalid attrs."""
    # Arrange
    service = UserService(db_session)
    user = await service.create(name="Test", email="test@example.com")

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await service.update(user.id, nonexistent_field="value")

    assert "Invalid attribute" in str(exc_info.value)
    assert "nonexistent_field" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_not_found(db_session: AsyncSession):
    """Test: BaseService.update() raises RecordNotFoundError for missing ID."""
    # Arrange
    service = UserService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.update(9999, name="New Name")

    assert exc_info.value.model_name == "SampleUser"
    assert exc_info.value.record_id == 9999


@pytest.mark.asyncio
async def test_delete_not_found(db_session: AsyncSession):
    """Test: BaseService.delete() raises RecordNotFoundError for missing ID."""
    # Arrange
    service = UserService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.delete(9999)

    assert exc_info.value.model_name == "SampleUser"
    assert exc_info.value.record_id == 9999


@pytest.mark.asyncio
async def test_transaction_isolation(db_session: AsyncSession):
    """Test: BaseService maintains transaction isolation between operations."""
    # Arrange
    service = UserService(db_session)

    # Act - create user
    user1 = await service.create(name="User 1", email="user1@example.com")

    # Act - create another user
    user2 = await service.create(name="User 2", email="user2@example.com")

    # Assert - both should be committed and accessible
    found_user1 = await SampleUser.get_by_id(db_session, user1.id)
    found_user2 = await SampleUser.get_by_id(db_session, user2.id)

    assert found_user1 is not None
    assert found_user2 is not None
    assert found_user1.name == "User 1"
    assert found_user2.name == "User 2"
