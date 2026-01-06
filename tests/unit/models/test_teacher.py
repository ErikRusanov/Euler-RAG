"""Unit tests for Teacher model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exceptions import InvalidFilterError
from app.models.teacher import Teacher


@pytest.mark.asyncio
async def test_create_teacher_success(db_session: AsyncSession):
    """Test: Teacher.create() should create new teacher with name."""
    # Arrange
    teacher_data = {"name": "Dr. Smith"}

    # Act
    teacher = await Teacher.create(db_session, **teacher_data)
    await db_session.commit()

    # Assert
    assert teacher.id is not None
    assert teacher.name == "Dr. Smith"
    assert teacher.created_at is not None
    assert teacher.updated_at is not None


@pytest.mark.asyncio
async def test_create_teacher_with_long_name(db_session: AsyncSession):
    """Test: Teacher.create() should handle long names correctly."""
    # Arrange
    long_name = "Professor Dr. Alexander von Humboldt III"
    teacher_data = {"name": long_name}

    # Act
    teacher = await Teacher.create(db_session, **teacher_data)
    await db_session.commit()

    # Assert
    assert teacher.id is not None
    assert teacher.name == long_name


@pytest.mark.asyncio
async def test_create_duplicate_teacher_name_allowed(db_session: AsyncSession):
    """Test: Multiple teachers can have the same name (no unique constraint)."""
    # Arrange
    teacher_data = {"name": "Dr. Johnson"}

    # Act
    teacher1 = await Teacher.create(db_session, **teacher_data)
    teacher2 = await Teacher.create(db_session, **teacher_data)
    await db_session.commit()

    # Assert
    assert teacher1.id != teacher2.id
    assert teacher1.name == teacher2.name == "Dr. Johnson"


@pytest.mark.asyncio
async def test_get_teacher_by_id(db_session: AsyncSession):
    """Test: Teacher.get_by_id() should retrieve teacher by primary key."""
    # Arrange
    teacher = await Teacher.create(db_session, name="Dr. Williams")
    await db_session.commit()

    # Act
    retrieved = await Teacher.get_by_id(db_session, teacher.id)

    # Assert
    assert retrieved is not None
    assert retrieved.id == teacher.id
    assert retrieved.name == "Dr. Williams"


@pytest.mark.asyncio
async def test_get_teacher_by_id_not_found(db_session: AsyncSession):
    """Test: Teacher.get_by_id() should return None for non-existent ID."""
    # Act
    retrieved = await Teacher.get_by_id(db_session, 99999)

    # Assert
    assert retrieved is None


@pytest.mark.asyncio
async def test_find_teacher_by_name(db_session: AsyncSession):
    """Test: Teacher.find() should filter teachers by name."""
    # Arrange
    await Teacher.create(db_session, name="Dr. Brown")
    await Teacher.create(db_session, name="Dr. Brown")
    await Teacher.create(db_session, name="Dr. Davis")
    await db_session.commit()

    # Act
    brown_teachers = await Teacher.find(db_session, name="Dr. Brown")

    # Assert
    assert len(brown_teachers) == 2
    assert all(t.name == "Dr. Brown" for t in brown_teachers)


@pytest.mark.asyncio
async def test_find_teacher_with_invalid_filter(db_session: AsyncSession):
    """Test: Teacher.find() should raise InvalidFilterError for invalid attributes."""
    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await Teacher.find(db_session, invalid_field="value")

    assert "Invalid filter key 'invalid_field'" in str(exc_info.value)
    assert "Teacher" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_all_teachers(db_session: AsyncSession):
    """Test: Teacher.get_all() should retrieve all teachers."""
    # Arrange
    await Teacher.create(db_session, name="Teacher One")
    await Teacher.create(db_session, name="Teacher Two")
    await Teacher.create(db_session, name="Teacher Three")
    await db_session.commit()

    # Act
    all_teachers = await Teacher.get_all(db_session)

    # Assert
    assert len(all_teachers) == 3
    assert {t.name for t in all_teachers} == {
        "Teacher One",
        "Teacher Two",
        "Teacher Three",
    }


@pytest.mark.asyncio
async def test_get_all_teachers_with_limit(db_session: AsyncSession):
    """Test: Teacher.get_all() should respect limit parameter."""
    # Arrange
    await Teacher.create(db_session, name="Teacher A")
    await Teacher.create(db_session, name="Teacher B")
    await Teacher.create(db_session, name="Teacher C")
    await db_session.commit()

    # Act
    limited_teachers = await Teacher.get_all(db_session, limit=2)

    # Assert
    assert len(limited_teachers) == 2


@pytest.mark.asyncio
async def test_get_all_teachers_with_offset(db_session: AsyncSession):
    """Test: Teacher.get_all() should respect offset parameter."""
    # Arrange
    await Teacher.create(db_session, name="Teacher X")
    await Teacher.create(db_session, name="Teacher Y")
    await Teacher.create(db_session, name="Teacher Z")
    await db_session.commit()

    # Act
    offset_teachers = await Teacher.get_all(db_session, offset=1, limit=2)

    # Assert
    assert len(offset_teachers) == 2


@pytest.mark.asyncio
async def test_update_teacher_name(db_session: AsyncSession):
    """Test: Teacher.update() should update teacher name."""
    # Arrange
    teacher = await Teacher.create(db_session, name="Old Name")
    await db_session.commit()
    original_created_at = teacher.created_at

    # Act
    await teacher.update(db_session, name="New Name")
    await db_session.commit()

    # Assert
    updated = await Teacher.get_by_id(db_session, teacher.id)
    assert updated.name == "New Name"
    assert updated.created_at == original_created_at
    assert updated.updated_at >= original_created_at


@pytest.mark.asyncio
async def test_update_teacher_with_invalid_attribute(db_session: AsyncSession):
    """Test: Teacher.update() should raise InvalidFilterError for invalid attributes."""
    # Arrange
    teacher = await Teacher.create(db_session, name="Test Teacher")
    await db_session.commit()

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await teacher.update(db_session, invalid_field="value")

    assert "Invalid attribute 'invalid_field'" in str(exc_info.value)
    assert "Teacher" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_teacher(db_session: AsyncSession):
    """Test: Teacher.delete() should remove teacher from database."""
    # Arrange
    teacher = await Teacher.create(db_session, name="Temporary Teacher")
    await db_session.commit()
    teacher_id = teacher.id

    # Act
    await teacher.delete(db_session)
    await db_session.commit()

    # Assert
    deleted_teacher = await Teacher.get_by_id(db_session, teacher_id)
    assert deleted_teacher is None


@pytest.mark.asyncio
async def test_count_teachers(db_session: AsyncSession):
    """Test: Teacher.count() should return correct count of teachers."""
    # Arrange
    await Teacher.create(db_session, name="Teacher Alpha")
    await Teacher.create(db_session, name="Teacher Beta")
    await Teacher.create(db_session, name="Teacher Alpha")
    await db_session.commit()

    # Act
    total_count = await Teacher.count(db_session)
    alpha_count = await Teacher.count(db_session, name="Teacher Alpha")

    # Assert
    assert total_count == 3
    assert alpha_count == 2


@pytest.mark.asyncio
async def test_teacher_to_dict(db_session: AsyncSession):
    """Test: Teacher.to_dict() should return dictionary representation."""
    # Arrange
    teacher = await Teacher.create(db_session, name="Dictionary Test Teacher")
    await db_session.commit()

    # Act
    teacher_dict = teacher.to_dict()

    # Assert
    assert isinstance(teacher_dict, dict)
    assert teacher_dict["name"] == "Dictionary Test Teacher"
    assert "id" in teacher_dict
    assert "created_at" in teacher_dict
    assert "updated_at" in teacher_dict


@pytest.mark.asyncio
async def test_teacher_repr(db_session: AsyncSession):
    """Test: Teacher.__repr__() should return readable string representation."""
    # Arrange
    teacher = await Teacher.create(db_session, name="Repr Test Teacher")
    await db_session.commit()

    # Act
    repr_str = repr(teacher)

    # Assert
    assert "Teacher" in repr_str
    assert "Repr Test Teacher" in repr_str
    assert str(teacher.id) in repr_str


@pytest.mark.asyncio
async def test_create_teacher_empty_name_allowed(db_session: AsyncSession):
    """Test: Teacher can be created with empty name (business logic validation)."""
    # Arrange
    teacher_data = {"name": ""}

    # Act
    teacher = await Teacher.create(db_session, **teacher_data)
    await db_session.commit()

    # Assert
    assert teacher.id is not None
    assert teacher.name == ""
