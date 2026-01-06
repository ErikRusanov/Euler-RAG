"""Unit tests for SubjectService following TDD methodology.

This module contains comprehensive tests for SubjectService including:
- CRUD operations (inherited from BaseService)
- Search by name and semester using find()
- Data validation
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
from app.models.subject import Subject
from app.services.subject_service import SubjectService


@pytest.mark.asyncio
async def test_create_subject_success(db_session: AsyncSession):
    """Test: SubjectService.create() should create subject with auto-commit."""
    # Arrange
    service = SubjectService(db_session)
    subject_data = {"name": "Linear Algebra", "semester": 3}

    # Act
    subject = await service.create(**subject_data)

    # Assert
    assert subject.id is not None
    assert subject.name == "Linear Algebra"
    assert subject.semester == 3
    assert subject.created_at is not None
    assert subject.updated_at is not None

    # Verify persistence
    found = await Subject.get_by_id(db_session, subject.id)
    assert found is not None
    assert found.name == "Linear Algebra"


@pytest.mark.asyncio
async def test_create_duplicate_subject_fails(db_session: AsyncSession):
    """Test: Creating duplicate (name, semester) raises DatabaseConnectionError."""
    # Arrange
    service = SubjectService(db_session)
    subject_data = {"name": "Calculus", "semester": 1}

    # Create first subject
    await service.create(**subject_data)

    # Act & Assert - try to create duplicate
    with pytest.raises(DatabaseConnectionError) as exc_info:
        await service.create(**subject_data)

    assert "Integrity constraint violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_same_name_different_semester_success(db_session: AsyncSession):
    """Test: Same subject name can exist in different semesters."""
    # Arrange
    service = SubjectService(db_session)

    # Act
    subject1 = await service.create(name="Physics", semester=1)
    subject2 = await service.create(name="Physics", semester=2)

    # Assert
    assert subject1.id != subject2.id
    assert subject1.name == subject2.name == "Physics"
    assert subject1.semester == 1
    assert subject2.semester == 2


@pytest.mark.asyncio
async def test_get_by_id_success(db_session: AsyncSession):
    """Test: SubjectService.get_by_id() should retrieve existing subject."""
    # Arrange
    service = SubjectService(db_session)
    created = await service.create(name="Chemistry", semester=2)

    # Act
    found = await service.get_by_id(created.id)

    # Assert
    assert found is not None
    assert found.id == created.id
    assert found.name == "Chemistry"
    assert found.semester == 2


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test: SubjectService.get_by_id() should return None for non-existent ID."""
    # Arrange
    service = SubjectService(db_session)

    # Act
    found = await service.get_by_id(9999)

    # Assert
    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_or_fail_success(db_session: AsyncSession):
    """Test: SubjectService.get_by_id_or_fail() should return existing subject."""
    # Arrange
    service = SubjectService(db_session)
    created = await service.create(name="Biology", semester=3)

    # Act
    found = await service.get_by_id_or_fail(created.id)

    # Assert
    assert found.id == created.id
    assert found.name == "Biology"


@pytest.mark.asyncio
async def test_get_by_id_or_fail_raises_error(db_session: AsyncSession):
    """Test: SubjectService.get_by_id_or_fail() should raise RecordNotFoundError."""
    # Arrange
    service = SubjectService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.get_by_id_or_fail(9999)

    assert exc_info.value.model_name == "Subject"
    assert exc_info.value.record_id == 9999


@pytest.mark.asyncio
async def test_get_all_subjects(db_session: AsyncSession):
    """Test: SubjectService.get_all() should retrieve all subjects."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Math", semester=1)
    await service.create(name="History", semester=2)
    await service.create(name="Art", semester=1)

    # Act
    all_subjects = await service.get_all()

    # Assert
    assert len(all_subjects) == 3
    names = {s.name for s in all_subjects}
    assert names == {"Math", "History", "Art"}


@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session: AsyncSession):
    """Test: SubjectService.get_all() should support pagination."""
    # Arrange
    service = SubjectService(db_session)
    for i in range(10):
        await service.create(name=f"Subject {i}", semester=1)

    # Act
    page1 = await service.get_all(limit=5, offset=0)
    page2 = await service.get_all(limit=5, offset=5)

    # Assert
    assert len(page1) == 5
    assert len(page2) == 5
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_find_by_name(db_session: AsyncSession):
    """Test: SubjectService.find() should filter subjects by name."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Economics", semester=1)
    await service.create(name="Economics", semester=2)
    await service.create(name="Finance", semester=1)

    # Act
    economics_subjects = await service.find(name="Economics")

    # Assert
    assert len(economics_subjects) == 2
    assert all(s.name == "Economics" for s in economics_subjects)


@pytest.mark.asyncio
async def test_find_by_semester(db_session: AsyncSession):
    """Test: SubjectService.find() should filter subjects by semester."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Subject A", semester=1)
    await service.create(name="Subject B", semester=1)
    await service.create(name="Subject C", semester=2)

    # Act
    semester_1_subjects = await service.find(semester=1)

    # Assert
    assert len(semester_1_subjects) == 2
    assert all(s.semester == 1 for s in semester_1_subjects)


@pytest.mark.asyncio
async def test_find_by_name_and_semester(db_session: AsyncSession):
    """Test: SubjectService.find() should filter by both name and semester."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Programming", semester=1)
    await service.create(name="Programming", semester=2)
    await service.create(name="Algorithms", semester=1)

    # Act
    specific = await service.find(name="Programming", semester=1)

    # Assert
    assert len(specific) == 1
    assert specific[0].name == "Programming"
    assert specific[0].semester == 1


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: SubjectService.find() should raise InvalidFilterError for invalid keys."""
    # Arrange
    service = SubjectService(db_session)

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await service.find(invalid_field="value")

    assert "Invalid filter key" in str(exc_info.value)
    assert "invalid_field" in str(exc_info.value)


@pytest.mark.asyncio
async def test_count_all_subjects(db_session: AsyncSession):
    """Test: SubjectService.count() should count all subjects."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Subject 1", semester=1)
    await service.create(name="Subject 2", semester=2)
    await service.create(name="Subject 3", semester=3)

    # Act
    total = await service.count()

    # Assert
    assert total == 3


@pytest.mark.asyncio
async def test_count_with_filter(db_session: AsyncSession):
    """Test: SubjectService.count() should count subjects matching filter."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Data Science", semester=1)
    await service.create(name="Machine Learning", semester=1)
    await service.create(name="Deep Learning", semester=2)

    # Act
    semester_1_count = await service.count(semester=1)

    # Assert
    assert semester_1_count == 2


@pytest.mark.asyncio
async def test_update_subject_success(db_session: AsyncSession):
    """Test: SubjectService.update() should update subject with auto-commit."""
    # Arrange
    service = SubjectService(db_session)
    subject = await service.create(name="Old Name", semester=1)

    # Act
    updated = await service.update(subject.id, name="New Name", semester=2)

    # Assert
    assert updated.id == subject.id
    assert updated.name == "New Name"
    assert updated.semester == 2

    # Verify persistence
    found = await Subject.get_by_id(db_session, subject.id)
    assert found.name == "New Name"
    assert found.semester == 2


@pytest.mark.asyncio
async def test_update_to_duplicate_fails(db_session: AsyncSession):
    """Test: Updating to duplicate (name, semester) should raise error."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Existing", semester=1)
    subject = await service.create(name="To Update", semester=2)
    subject_id = subject.id  # Save ID before rollback

    # Act & Assert
    with pytest.raises(DatabaseConnectionError) as exc_info:
        await service.update(subject_id, name="Existing", semester=1)

    # Check error mentions constraint violation
    error_message = str(exc_info.value)
    assert "constraint" in error_message.lower()
    assert (
        "uq_subject_name_semester" in error_message or "unique" in error_message.lower()
    )

    # Verify original subject unchanged after rollback
    found = await Subject.get_by_id(db_session, subject_id)
    assert found.name == "To Update"
    assert found.semester == 2


@pytest.mark.asyncio
async def test_update_non_existent_subject(db_session: AsyncSession):
    """Test: Updating non-existent subject should raise RecordNotFoundError."""
    # Arrange
    service = SubjectService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.update(9999, name="New Name")

    assert exc_info.value.model_name == "Subject"
    assert exc_info.value.record_id == 9999


@pytest.mark.asyncio
async def test_update_with_invalid_attribute(db_session: AsyncSession):
    """Test: Updating with invalid attribute should raise InvalidFilterError."""
    # Arrange
    service = SubjectService(db_session)
    subject = await service.create(name="Test", semester=1)

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await service.update(subject.id, invalid_field="value")

    assert "Invalid attribute" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_subject_success(db_session: AsyncSession):
    """Test: SubjectService.delete() should delete subject with auto-commit."""
    # Arrange
    service = SubjectService(db_session)
    subject = await service.create(name="To Delete", semester=1)
    subject_id = subject.id

    # Act
    await service.delete(subject_id)

    # Assert - subject should be deleted
    found = await Subject.get_by_id(db_session, subject_id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_non_existent_subject(db_session: AsyncSession):
    """Test: Deleting non-existent subject should raise RecordNotFoundError."""
    # Arrange
    service = SubjectService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.delete(9999)

    assert exc_info.value.model_name == "Subject"
    assert exc_info.value.record_id == 9999


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_session: AsyncSession):
    """Test: Service should rollback transaction on error."""
    # Arrange
    service = SubjectService(db_session)
    await service.create(name="Existing", semester=1)

    # Act - try to create duplicate
    with pytest.raises(DatabaseConnectionError):
        await service.create(name="Existing", semester=1)

    # Assert - only one subject should exist
    all_subjects = await service.get_all()
    assert len(all_subjects) == 1
