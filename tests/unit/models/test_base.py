"""Unit tests for BaseModel with CRUD operations."""

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseModel
from app.models.exceptions import InvalidFilterError, RecordNotFoundError
from app.utils.db import Base


class SampleUser(BaseModel, Base):
    """Sample model for testing BaseModel CRUD operations."""

    __tablename__ = "test_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)


@pytest.mark.asyncio
async def test_create_model(db_session: AsyncSession):
    """Test: BaseModel.create() should create new record in database."""
    # Arrange
    user_data = {"name": "John Doe", "email": "john@example.com"}

    # Act
    user = await SampleUser.create(db_session, **user_data)
    await db_session.commit()

    # Assert
    assert user.id is not None
    assert user.name == "John Doe"
    assert user.email == "john@example.com"


@pytest.mark.asyncio
async def test_get_by_id_existing(db_session: AsyncSession):
    """Test: BaseModel.get_by_id() should return existing record."""
    # Arrange
    user = await SampleUser.create(
        db_session, name="Jane Doe", email="jane@example.com"
    )
    await db_session.commit()

    # Act
    found_user = await SampleUser.get_by_id(db_session, user.id)

    # Assert
    assert found_user is not None
    assert found_user.id == user.id
    assert found_user.name == "Jane Doe"
    assert found_user.email == "jane@example.com"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test: BaseModel.get_by_id() should return None for non-existent ID."""
    # Act
    found_user = await SampleUser.get_by_id(db_session, 9999)

    # Assert
    assert found_user is None


@pytest.mark.asyncio
async def test_update_model(db_session: AsyncSession):
    """Test: BaseModel.update() should update existing record."""
    # Arrange
    user = await SampleUser.create(db_session, name="Old Name", email="old@example.com")
    await db_session.commit()

    # Act
    updated_user = await user.update(
        db_session, name="New Name", email="new@example.com"
    )
    await db_session.commit()

    # Assert
    assert updated_user.id == user.id
    assert updated_user.name == "New Name"
    assert updated_user.email == "new@example.com"

    # Verify in database
    db_user = await SampleUser.get_by_id(db_session, user.id)
    assert db_user.name == "New Name"


@pytest.mark.asyncio
async def test_delete_model(db_session: AsyncSession):
    """Test: BaseModel.delete() should remove record from database."""
    # Arrange
    user = await SampleUser.create(
        db_session, name="Delete Me", email="delete@example.com"
    )
    await db_session.commit()
    user_id = user.id

    # Act
    await user.delete(db_session)
    await db_session.commit()

    # Assert
    found_user = await SampleUser.get_by_id(db_session, user_id)
    assert found_user is None


@pytest.mark.asyncio
async def test_get_all(db_session: AsyncSession):
    """Test: BaseModel.get_all() should return all records."""
    # Arrange
    await SampleUser.create(db_session, name="User 1", email="user1@example.com")
    await SampleUser.create(db_session, name="User 2", email="user2@example.com")
    await SampleUser.create(db_session, name="User 3", email="user3@example.com")
    await db_session.commit()

    # Act
    all_users = await SampleUser.get_all(db_session)

    # Assert
    assert len(all_users) == 3
    assert all_users[0].name == "User 1"
    assert all_users[1].name == "User 2"
    assert all_users[2].name == "User 3"


@pytest.mark.asyncio
async def test_find_by_filters(db_session: AsyncSession):
    """Test: BaseModel.find() should filter records by criteria."""
    # Arrange
    await SampleUser.create(db_session, name="Alice", email="alice@example.com")
    await SampleUser.create(db_session, name="Bob", email="bob@example.com")
    await SampleUser.create(db_session, name="Alice", email="alice2@example.com")
    await db_session.commit()

    # Act
    alice_users = await SampleUser.find(db_session, name="Alice")

    # Assert
    assert len(alice_users) == 2
    assert all(user.name == "Alice" for user in alice_users)


@pytest.mark.asyncio
async def test_get_by_id_or_fail_existing(db_session: AsyncSession):
    """Test: BaseModel.get_by_id_or_fail() should return existing record."""
    # Arrange
    user = await SampleUser.create(
        db_session, name="Test User", email="test@example.com"
    )
    await db_session.commit()

    # Act
    found_user = await SampleUser.get_by_id_or_fail(db_session, user.id)

    # Assert
    assert found_user.id == user.id
    assert found_user.name == "Test User"


@pytest.mark.asyncio
async def test_get_by_id_or_fail_not_found(db_session: AsyncSession):
    """Test: BaseModel.get_by_id_or_fail() should raise RecordNotFoundError."""
    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await SampleUser.get_by_id_or_fail(db_session, 9999)

    assert exc_info.value.model_name == "SampleUser"
    assert exc_info.value.record_id == 9999
    assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: BaseModel.find() should raise InvalidFilterError for invalid keys."""
    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await SampleUser.find(db_session, nonexistent_field="value")

    assert "Invalid filter key" in str(exc_info.value)
    assert "nonexistent_field" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_with_invalid_attribute(db_session: AsyncSession):
    """Test: BaseModel.update() should raise InvalidFilterError for invalid attributes."""
    # Arrange
    user = await SampleUser.create(db_session, name="Test", email="test@example.com")
    await db_session.commit()

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await user.update(db_session, nonexistent_field="value")

    assert "Invalid attribute" in str(exc_info.value)
    assert "nonexistent_field" in str(exc_info.value)


@pytest.mark.asyncio
async def test_to_dict(db_session: AsyncSession):
    """Test: BaseModel.to_dict() should convert model to dictionary."""
    # Arrange
    user = await SampleUser.create(
        db_session, name="Dict User", email="dict@example.com"
    )
    await db_session.commit()

    # Act
    user_dict = user.to_dict()

    # Assert
    assert isinstance(user_dict, dict)
    assert user_dict["id"] == user.id
    assert user_dict["name"] == "Dict User"
    assert user_dict["email"] == "dict@example.com"
