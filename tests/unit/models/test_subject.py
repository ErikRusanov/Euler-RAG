"""Unit tests for Subject model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exceptions import DatabaseConnectionError
from app.models.subject import Subject


@pytest.mark.asyncio
async def test_create_subject_success(db_session: AsyncSession):
    """Test: Subject.create() should create new subject with name and semester."""
    # Arrange
    subject_data = {"name": "Mathematics", "semester": 1}

    # Act
    subject = await Subject.create(db_session, **subject_data)
    await db_session.commit()

    # Assert
    assert subject.id is not None
    assert subject.name == "Mathematics"
    assert subject.semester == 1
    assert subject.created_at is not None
    assert subject.updated_at is not None


@pytest.mark.asyncio
async def test_create_subject_with_different_semesters(db_session: AsyncSession):
    """Test: Same subject name can exist in different semesters."""
    # Arrange
    subject_data_1 = {"name": "Physics", "semester": 1}
    subject_data_2 = {"name": "Physics", "semester": 2}

    # Act
    subject1 = await Subject.create(db_session, **subject_data_1)
    subject2 = await Subject.create(db_session, **subject_data_2)
    await db_session.commit()

    # Assert
    assert subject1.id != subject2.id
    assert subject1.name == subject2.name == "Physics"
    assert subject1.semester == 1
    assert subject2.semester == 2


@pytest.mark.asyncio
async def test_create_duplicate_subject_fails(db_session: AsyncSession):
    """Test: Creating duplicate (name, semester) raises DatabaseConnectionError."""
    # Arrange
    subject_data = {"name": "Chemistry", "semester": 3}
    await Subject.create(db_session, **subject_data)
    await db_session.commit()

    # Act & Assert
    with pytest.raises(DatabaseConnectionError) as exc_info:
        await Subject.create(db_session, **subject_data)
        await db_session.commit()

    assert "Integrity constraint violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_find_by_name(db_session: AsyncSession):
    """Test: Subject.find() should filter subjects by name."""
    # Arrange
    await Subject.create(db_session, name="Biology", semester=1)
    await Subject.create(db_session, name="Biology", semester=2)
    await Subject.create(db_session, name="History", semester=1)
    await db_session.commit()

    # Act
    biology_subjects = await Subject.find(db_session, name="Biology")

    # Assert
    assert len(biology_subjects) == 2
    assert all(s.name == "Biology" for s in biology_subjects)


@pytest.mark.asyncio
async def test_find_by_semester(db_session: AsyncSession):
    """Test: Subject.find() should filter subjects by semester."""
    # Arrange
    await Subject.create(db_session, name="Art", semester=1)
    await Subject.create(db_session, name="Music", semester=1)
    await Subject.create(db_session, name="Drama", semester=2)
    await db_session.commit()

    # Act
    semester_1_subjects = await Subject.find(db_session, semester=1)

    # Assert
    assert len(semester_1_subjects) == 2
    assert all(s.semester == 1 for s in semester_1_subjects)


@pytest.mark.asyncio
async def test_find_by_name_and_semester(db_session: AsyncSession):
    """Test: Subject.find() should filter by both name and semester."""
    # Arrange
    await Subject.create(db_session, name="Geography", semester=1)
    await Subject.create(db_session, name="Geography", semester=2)
    await Subject.create(db_session, name="Geology", semester=1)
    await db_session.commit()

    # Act
    specific_subject = await Subject.find(db_session, name="Geography", semester=1)

    # Assert
    assert len(specific_subject) == 1
    assert specific_subject[0].name == "Geography"
    assert specific_subject[0].semester == 1


@pytest.mark.asyncio
async def test_update_subject(db_session: AsyncSession):
    """Test: Subject.update() should update subject fields."""
    # Arrange
    subject = await Subject.create(db_session, name="Old Name", semester=1)
    await db_session.commit()

    # Act
    await subject.update(db_session, name="New Name", semester=2)
    await db_session.commit()

    # Assert
    updated = await Subject.get_by_id(db_session, subject.id)
    assert updated.name == "New Name"
    assert updated.semester == 2


@pytest.mark.asyncio
async def test_delete_subject(db_session: AsyncSession):
    """Test: Subject.delete() should remove subject from database."""
    # Arrange
    subject = await Subject.create(db_session, name="Temporary", semester=1)
    await db_session.commit()
    subject_id = subject.id

    # Act
    await subject.delete(db_session)
    await db_session.commit()

    # Assert
    deleted_subject = await Subject.get_by_id(db_session, subject_id)
    assert deleted_subject is None


@pytest.mark.asyncio
async def test_count_subjects(db_session: AsyncSession):
    """Test: Subject.count() should return correct count of subjects."""
    # Arrange
    await Subject.create(db_session, name="Subject A", semester=1)
    await Subject.create(db_session, name="Subject B", semester=1)
    await Subject.create(db_session, name="Subject C", semester=2)
    await db_session.commit()

    # Act
    total_count = await Subject.count(db_session)
    semester_1_count = await Subject.count(db_session, semester=1)

    # Assert
    assert total_count == 3
    assert semester_1_count == 2


@pytest.mark.asyncio
async def test_subject_to_dict(db_session: AsyncSession):
    """Test: Subject.to_dict() should return dictionary representation."""
    # Arrange
    subject = await Subject.create(db_session, name="Dictionary Test", semester=4)
    await db_session.commit()

    # Act
    subject_dict = subject.to_dict()

    # Assert
    assert isinstance(subject_dict, dict)
    assert subject_dict["name"] == "Dictionary Test"
    assert subject_dict["semester"] == 4
    assert "id" in subject_dict
    assert "created_at" in subject_dict
    assert "updated_at" in subject_dict


@pytest.mark.asyncio
async def test_subject_repr(db_session: AsyncSession):
    """Test: Subject.__repr__() should return readable string representation."""
    # Arrange
    subject = await Subject.create(db_session, name="Repr Test", semester=5)
    await db_session.commit()

    # Act
    repr_str = repr(subject)

    # Assert
    assert "Subject" in repr_str
    assert "Repr Test" in repr_str
    assert "5" in repr_str
