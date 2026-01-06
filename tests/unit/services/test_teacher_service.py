"""Unit tests for TeacherService following TDD methodology.

This module contains comprehensive tests for TeacherService including:
- CRUD operations (inherited from BaseService)
- Search by name using find()
- Transaction management
- Error handling
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    RecordNotFoundError,
)
from app.models.teacher import Teacher
from app.services.teacher_service import TeacherService


@pytest.mark.asyncio
async def test_create_teacher_success(db_session: AsyncSession):
    """Test: TeacherService.create() should create teacher with auto-commit."""
    # Arrange
    service = TeacherService(db_session)
    teacher_data = {"name": "Dr. Alexander Smith"}

    # Act
    teacher = await service.create(**teacher_data)

    # Assert
    assert teacher.id is not None
    assert teacher.name == "Dr. Alexander Smith"
    assert teacher.created_at is not None
    assert teacher.updated_at is not None

    # Verify persistence
    found = await Teacher.get_by_id(db_session, teacher.id)
    assert found is not None
    assert found.name == "Dr. Alexander Smith"


@pytest.mark.asyncio
async def test_create_duplicate_teacher_name_allowed(db_session: AsyncSession):
    """Test: Multiple teachers can have the same name (no unique constraint)."""
    # Arrange
    service = TeacherService(db_session)
    teacher_data = {"name": "Dr. Johnson"}

    # Act
    teacher1 = await service.create(**teacher_data)
    teacher2 = await service.create(**teacher_data)

    # Assert
    assert teacher1.id != teacher2.id
    assert teacher1.name == teacher2.name == "Dr. Johnson"


@pytest.mark.asyncio
async def test_get_by_id_success(db_session: AsyncSession):
    """Test: TeacherService.get_by_id() should retrieve existing teacher."""
    # Arrange
    service = TeacherService(db_session)
    created = await service.create(name="Dr. Brown")

    # Act
    found = await service.get_by_id(created.id)

    # Assert
    assert found is not None
    assert found.id == created.id
    assert found.name == "Dr. Brown"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test: TeacherService.get_by_id() should return None for non-existent ID."""
    # Arrange
    service = TeacherService(db_session)

    # Act
    found = await service.get_by_id(99999)

    # Assert
    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_or_fail_success(db_session: AsyncSession):
    """Test: TeacherService.get_by_id_or_fail() should return teacher if exists."""
    # Arrange
    service = TeacherService(db_session)
    created = await service.create(name="Dr. Davis")

    # Act
    found = await service.get_by_id_or_fail(created.id)

    # Assert
    assert found.id == created.id
    assert found.name == "Dr. Davis"


@pytest.mark.asyncio
async def test_get_by_id_or_fail_raises_error(db_session: AsyncSession):
    """Test: TeacherService.get_by_id_or_fail() should raise error if not found."""
    # Arrange
    service = TeacherService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.get_by_id_or_fail(99999)

    assert "Teacher" in str(exc_info.value)
    assert "99999" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_all_teachers(db_session: AsyncSession):
    """Test: TeacherService.get_all() should retrieve all teachers."""
    # Arrange
    service = TeacherService(db_session)
    await service.create(name="Teacher Alpha")
    await service.create(name="Teacher Beta")
    await service.create(name="Teacher Gamma")

    # Act
    all_teachers = await service.get_all()

    # Assert
    assert len(all_teachers) == 3
    names = {t.name for t in all_teachers}
    assert names == {"Teacher Alpha", "Teacher Beta", "Teacher Gamma"}


@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session: AsyncSession):
    """Test: TeacherService.get_all() should support limit and offset."""
    # Arrange
    service = TeacherService(db_session)
    await service.create(name="Teacher 1")
    await service.create(name="Teacher 2")
    await service.create(name="Teacher 3")
    await service.create(name="Teacher 4")

    # Act
    page_1 = await service.get_all(limit=2, offset=0)
    page_2 = await service.get_all(limit=2, offset=2)

    # Assert
    assert len(page_1) == 2
    assert len(page_2) == 2


@pytest.mark.asyncio
async def test_find_by_name(db_session: AsyncSession):
    """Test: TeacherService.find() should filter teachers by name."""
    # Arrange
    service = TeacherService(db_session)
    await service.create(name="Professor Smith")
    await service.create(name="Professor Smith")
    await service.create(name="Professor Jones")

    # Act
    smith_teachers = await service.find(name="Professor Smith")

    # Assert
    assert len(smith_teachers) == 2
    assert all(t.name == "Professor Smith" for t in smith_teachers)


@pytest.mark.asyncio
async def test_find_no_matches(db_session: AsyncSession):
    """Test: TeacherService.find() should return empty list when no matches."""
    # Arrange
    service = TeacherService(db_session)
    await service.create(name="Dr. Wilson")

    # Act
    found = await service.find(name="Dr. Nonexistent")

    # Assert
    assert found == []


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: TeacherService.find() should raise error for invalid filter."""
    # Arrange
    service = TeacherService(db_session)

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await service.find(invalid_field="value")

    assert "Invalid filter key 'invalid_field'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_count_all_teachers(db_session: AsyncSession):
    """Test: TeacherService.count() should return total count."""
    # Arrange
    service = TeacherService(db_session)
    await service.create(name="Teacher A")
    await service.create(name="Teacher B")
    await service.create(name="Teacher C")

    # Act
    count = await service.count()

    # Assert
    assert count == 3


@pytest.mark.asyncio
async def test_count_with_filter(db_session: AsyncSession):
    """Test: TeacherService.count() should count matching records."""
    # Arrange
    service = TeacherService(db_session)
    await service.create(name="Dr. Taylor")
    await service.create(name="Dr. Taylor")
    await service.create(name="Dr. Anderson")

    # Act
    taylor_count = await service.count(name="Dr. Taylor")

    # Assert
    assert taylor_count == 2


@pytest.mark.asyncio
async def test_update_teacher_success(db_session: AsyncSession):
    """Test: TeacherService.update() should update teacher and commit."""
    # Arrange
    service = TeacherService(db_session)
    teacher = await service.create(name="Old Name")

    # Act
    updated = await service.update(teacher.id, name="New Name")

    # Assert
    assert updated.id == teacher.id
    assert updated.name == "New Name"

    # Verify persistence
    found = await Teacher.get_by_id(db_session, teacher.id)
    assert found.name == "New Name"


@pytest.mark.asyncio
async def test_update_nonexistent_teacher(db_session: AsyncSession):
    """Test: TeacherService.update() should raise error for non-existent ID."""
    # Arrange
    service = TeacherService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError):
        await service.update(99999, name="New Name")


@pytest.mark.asyncio
async def test_update_with_invalid_field(db_session: AsyncSession):
    """Test: TeacherService.update() should raise error for invalid field."""
    # Arrange
    service = TeacherService(db_session)
    teacher = await service.create(name="Test Teacher")

    # Act & Assert
    with pytest.raises(InvalidFilterError):
        await service.update(teacher.id, invalid_field="value")


@pytest.mark.asyncio
async def test_delete_teacher_success(db_session: AsyncSession):
    """Test: TeacherService.delete() should remove teacher and commit."""
    # Arrange
    service = TeacherService(db_session)
    teacher = await service.create(name="Temporary Teacher")
    teacher_id = teacher.id

    # Act
    await service.delete(teacher_id)

    # Assert - verify deletion
    found = await Teacher.get_by_id(db_session, teacher_id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_nonexistent_teacher(db_session: AsyncSession):
    """Test: TeacherService.delete() should raise error for non-existent ID."""
    # Arrange
    service = TeacherService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError):
        await service.delete(99999)


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_session: AsyncSession):
    """Test: Service should rollback transaction on database error."""
    # Arrange
    service = TeacherService(db_session)

    # Act & Assert
    # Try to create teacher with invalid data (e.g., missing required field)
    with pytest.raises(DatabaseConnectionError):
        # This will fail because name is required
        await service.create()

    # Verify no teacher was created
    count = await service.count()
    assert count == 0
