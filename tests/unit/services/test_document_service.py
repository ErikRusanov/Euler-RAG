"""Unit tests for DocumentService following TDD methodology.

This module contains comprehensive tests for DocumentService including:
- CRUD operations (inherited from BaseService)
- Search by status, subject_id, teacher_id using find()
- Transaction management
- Error handling
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.exceptions import (
    DatabaseConnectionError,
    InvalidFilterError,
    RecordNotFoundError,
)
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_create_document_success(db_session: AsyncSession):
    """Test: DocumentService.create() should create document with auto-commit."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Mathematics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Smith")
    await db_session.commit()

    document_data = {
        "subject_id": subject.id,
        "teacher_id": teacher.id,
        "filename": "calculus.pdf",
        "s3_key": "documents/calculus_2024.pdf",
        "status": DocumentStatus.UPLOADED,
    }

    # Act
    document = await service.create(**document_data)

    # Assert
    assert document.id is not None
    assert document.subject_id == subject.id
    assert document.teacher_id == teacher.id
    assert document.filename == "calculus.pdf"
    assert document.s3_key == "documents/calculus_2024.pdf"
    assert document.status == DocumentStatus.UPLOADED
    assert document.created_at is not None

    # Verify persistence
    found = await Document.get_by_id(db_session, document.id)
    assert found is not None
    assert found.filename == "calculus.pdf"


@pytest.mark.asyncio
async def test_create_document_with_progress(db_session: AsyncSession):
    """Test: DocumentService.create() should handle JSONB progress field."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Physics", semester=2)
    teacher = await Teacher.create(db_session, name="Dr. Johnson")
    await db_session.commit()

    progress_data = {"pages": 10, "chunks": 25}
    document_data = {
        "subject_id": subject.id,
        "teacher_id": teacher.id,
        "filename": "physics.pdf",
        "s3_key": "documents/physics.pdf",
        "status": DocumentStatus.PROCESSING,
        "progress": progress_data,
    }

    # Act
    document = await service.create(**document_data)

    # Assert
    assert document.progress == progress_data
    assert document.progress["pages"] == 10


@pytest.mark.asyncio
async def test_create_document_duplicate_s3_key_fails(db_session: AsyncSession):
    """Test: Creating document with duplicate s3_key raises DatabaseConnectionError."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Chemistry", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Brown")
    await db_session.commit()

    s3_key = "documents/unique_document.pdf"

    # Create first document
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="first.pdf",
        s3_key=s3_key,
        status=DocumentStatus.UPLOADED,
    )

    # Act & Assert - try to create duplicate
    with pytest.raises(DatabaseConnectionError) as exc_info:
        await service.create(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="second.pdf",
            s3_key=s3_key,
            status=DocumentStatus.UPLOADED,
        )

    assert "Integrity constraint violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_by_id_success(db_session: AsyncSession):
    """Test: DocumentService.get_by_id() should retrieve existing document."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Biology", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Williams")
    await db_session.commit()

    created = await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="biology.pdf",
        s3_key="documents/biology.pdf",
        status=DocumentStatus.READY,
    )

    # Act
    found = await service.get_by_id(created.id)

    # Assert
    assert found is not None
    assert found.id == created.id
    assert found.filename == "biology.pdf"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test: DocumentService.get_by_id() should return None for non-existent ID."""
    # Arrange
    service = DocumentService(db_session)

    # Act
    found = await service.get_by_id(99999)

    # Assert
    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_or_fail_success(db_session: AsyncSession):
    """Test: DocumentService.get_by_id_or_fail() should return document if exists."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="History", semester=3)
    teacher = await Teacher.create(db_session, name="Dr. Davis")
    await db_session.commit()

    created = await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="history.pdf",
        s3_key="documents/history.pdf",
        status=DocumentStatus.READY,
    )

    # Act
    found = await service.get_by_id_or_fail(created.id)

    # Assert
    assert found.id == created.id
    assert found.filename == "history.pdf"


@pytest.mark.asyncio
async def test_get_by_id_or_fail_raises_error(db_session: AsyncSession):
    """Test: DocumentService.get_by_id_or_fail() should raise error if not found."""
    # Arrange
    service = DocumentService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.get_by_id_or_fail(99999)

    assert "Document" in str(exc_info.value)
    assert "99999" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_all_documents(db_session: AsyncSession):
    """Test: DocumentService.get_all() should retrieve all documents."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Art", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Taylor")
    await db_session.commit()

    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="art1.pdf",
        s3_key="documents/art1.pdf",
        status=DocumentStatus.READY,
    )
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="art2.pdf",
        s3_key="documents/art2.pdf",
        status=DocumentStatus.READY,
    )

    # Act
    all_documents = await service.get_all()

    # Assert
    assert len(all_documents) == 2
    filenames = {doc.filename for doc in all_documents}
    assert filenames == {"art1.pdf", "art2.pdf"}


@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session: AsyncSession):
    """Test: DocumentService.get_all() should support limit and offset."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Music", semester=2)
    teacher = await Teacher.create(db_session, name="Dr. Anderson")
    await db_session.commit()

    for i in range(5):
        await service.create(
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename=f"music{i}.pdf",
            s3_key=f"documents/music{i}.pdf",
            status=DocumentStatus.READY,
        )

    # Act
    page_1 = await service.get_all(limit=2, offset=0)
    page_2 = await service.get_all(limit=2, offset=2)

    # Assert
    assert len(page_1) == 2
    assert len(page_2) == 2


@pytest.mark.asyncio
async def test_find_by_status(db_session: AsyncSession):
    """Test: DocumentService.find() should filter documents by status."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Geography", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Wilson")
    await db_session.commit()

    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="geo1.pdf",
        s3_key="documents/geo1.pdf",
        status=DocumentStatus.READY,
    )
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="geo2.pdf",
        s3_key="documents/geo2.pdf",
        status=DocumentStatus.PROCESSING,
    )
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="geo3.pdf",
        s3_key="documents/geo3.pdf",
        status=DocumentStatus.READY,
    )

    # Act
    ready_docs = await service.find(status=DocumentStatus.READY)

    # Assert
    assert len(ready_docs) == 2
    assert all(doc.status == DocumentStatus.READY for doc in ready_docs)


@pytest.mark.asyncio
async def test_find_by_subject_id(db_session: AsyncSession):
    """Test: DocumentService.find() should filter by subject_id."""
    # Arrange
    service = DocumentService(db_session)
    subject1 = await Subject.create(db_session, name="Math", semester=1)
    subject2 = await Subject.create(db_session, name="Physics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Lee")
    await db_session.commit()

    await service.create(
        subject_id=subject1.id,
        teacher_id=teacher.id,
        filename="math1.pdf",
        s3_key="documents/math1.pdf",
        status=DocumentStatus.READY,
    )
    await service.create(
        subject_id=subject2.id,
        teacher_id=teacher.id,
        filename="physics1.pdf",
        s3_key="documents/physics1.pdf",
        status=DocumentStatus.READY,
    )

    # Act
    math_docs = await service.find(subject_id=subject1.id)

    # Assert
    assert len(math_docs) == 1
    assert math_docs[0].subject_id == subject1.id


@pytest.mark.asyncio
async def test_find_by_teacher_id(db_session: AsyncSession):
    """Test: DocumentService.find() should filter by teacher_id."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Literature", semester=2)
    teacher1 = await Teacher.create(db_session, name="Dr. Martinez")
    teacher2 = await Teacher.create(db_session, name="Dr. Garcia")
    await db_session.commit()

    await service.create(
        subject_id=subject.id,
        teacher_id=teacher1.id,
        filename="lit1.pdf",
        s3_key="documents/lit1.pdf",
        status=DocumentStatus.READY,
    )
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher2.id,
        filename="lit2.pdf",
        s3_key="documents/lit2.pdf",
        status=DocumentStatus.READY,
    )

    # Act
    teacher1_docs = await service.find(teacher_id=teacher1.id)

    # Assert
    assert len(teacher1_docs) == 1
    assert teacher1_docs[0].teacher_id == teacher1.id


@pytest.mark.asyncio
async def test_find_no_matches(db_session: AsyncSession):
    """Test: DocumentService.find() should return empty list when no matches."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Economics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Robinson")
    await db_session.commit()

    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="econ.pdf",
        s3_key="documents/econ.pdf",
        status=DocumentStatus.READY,
    )

    # Act
    found = await service.find(status=DocumentStatus.ERROR)

    # Assert
    assert found == []


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: DocumentService.find() should raise error for invalid filter."""
    # Arrange
    service = DocumentService(db_session)

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await service.find(invalid_field="value")

    assert "Invalid filter key 'invalid_field'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_count_all_documents(db_session: AsyncSession):
    """Test: DocumentService.count() should return total count."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Philosophy", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Clark")
    await db_session.commit()

    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="phil1.pdf",
        s3_key="documents/phil1.pdf",
        status=DocumentStatus.READY,
    )
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="phil2.pdf",
        s3_key="documents/phil2.pdf",
        status=DocumentStatus.PROCESSING,
    )

    # Act
    count = await service.count()

    # Assert
    assert count == 2


@pytest.mark.asyncio
async def test_count_with_filter(db_session: AsyncSession):
    """Test: DocumentService.count() should count matching records."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Sociology", semester=3)
    teacher = await Teacher.create(db_session, name="Dr. White")
    await db_session.commit()

    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="soc1.pdf",
        s3_key="documents/soc1.pdf",
        status=DocumentStatus.READY,
    )
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="soc2.pdf",
        s3_key="documents/soc2.pdf",
        status=DocumentStatus.READY,
    )
    await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="soc3.pdf",
        s3_key="documents/soc3.pdf",
        status=DocumentStatus.PROCESSING,
    )

    # Act
    ready_count = await service.count(status=DocumentStatus.READY)

    # Assert
    assert ready_count == 2


@pytest.mark.asyncio
async def test_update_document_success(db_session: AsyncSession):
    """Test: DocumentService.update() should update document and commit."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Psychology", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Harris")
    await db_session.commit()

    document = await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="psych.pdf",
        s3_key="documents/psych.pdf",
        status=DocumentStatus.PENDING,
    )

    # Act
    updated = await service.update(document.id, status=DocumentStatus.PROCESSING)

    # Assert
    assert updated.id == document.id
    assert updated.status == DocumentStatus.PROCESSING

    # Verify persistence
    found = await Document.get_by_id(db_session, document.id)
    assert found.status == DocumentStatus.PROCESSING


@pytest.mark.asyncio
async def test_update_document_progress(db_session: AsyncSession):
    """Test: DocumentService.update() should update JSONB progress field."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Astronomy", semester=2)
    teacher = await Teacher.create(db_session, name="Dr. King")
    await db_session.commit()

    document = await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="astro.pdf",
        s3_key="documents/astro.pdf",
        status=DocumentStatus.PROCESSING,
        progress={"step": 1},
    )

    # Act
    new_progress = {"step": 2, "total": 10}
    updated = await service.update(document.id, progress=new_progress)

    # Assert
    assert updated.progress == new_progress


@pytest.mark.asyncio
async def test_update_nonexistent_document(db_session: AsyncSession):
    """Test: DocumentService.update() should raise error for non-existent ID."""
    # Arrange
    service = DocumentService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError):
        await service.update(99999, status=DocumentStatus.READY)


@pytest.mark.asyncio
async def test_update_with_invalid_field(db_session: AsyncSession):
    """Test: DocumentService.update() should raise error for invalid field."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Geology", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Moore")
    await db_session.commit()

    document = await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="geo.pdf",
        s3_key="documents/geo.pdf",
        status=DocumentStatus.UPLOADED,
    )

    # Act & Assert
    with pytest.raises(InvalidFilterError):
        await service.update(document.id, invalid_field="value")


@pytest.mark.asyncio
async def test_delete_document_success(db_session: AsyncSession):
    """Test: DocumentService.delete() should remove document and commit."""
    # Arrange
    service = DocumentService(db_session)
    subject = await Subject.create(db_session, name="Anthropology", semester=2)
    teacher = await Teacher.create(db_session, name="Dr. Young")
    await db_session.commit()

    document = await service.create(
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="temp.pdf",
        s3_key="documents/temp.pdf",
        status=DocumentStatus.UPLOADED,
    )
    document_id = document.id

    # Act
    await service.delete(document_id)

    # Assert - verify deletion
    found = await Document.get_by_id(db_session, document_id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_nonexistent_document(db_session: AsyncSession):
    """Test: DocumentService.delete() should raise error for non-existent ID."""
    # Arrange
    service = DocumentService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError):
        await service.delete(99999)


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_session: AsyncSession):
    """Test: Service should rollback transaction on database error."""
    # Arrange
    service = DocumentService(db_session)

    # Act & Assert
    # Try to create document without required fields
    with pytest.raises(DatabaseConnectionError):
        await service.create(filename="test.pdf")

    # Verify no document was created
    count = await service.count()
    assert count == 0
