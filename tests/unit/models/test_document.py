"""Unit tests for Document model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.exceptions import DatabaseConnectionError, InvalidFilterError
from app.models.subject import Subject
from app.models.teacher import Teacher


@pytest.mark.asyncio
async def test_create_document_success(db_session: AsyncSession):
    """Test: Document.create() should create document with all required fields."""
    # Arrange
    subject = await Subject.create(db_session, name="Mathematics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Smith")
    await db_session.commit()

    document_data = {
        "subject_id": subject.id,
        "teacher_id": teacher.id,
        "filename": "lecture_notes.pdf",
        "s3_key": "documents/2024/lecture_notes_abc123.pdf",
        "status": DocumentStatus.UPLOADED,
    }

    # Act
    document = await Document.create(db_session, **document_data)
    await db_session.commit()

    # Assert
    assert document.id is not None
    assert document.subject_id == subject.id
    assert document.teacher_id == teacher.id
    assert document.filename == "lecture_notes.pdf"
    assert document.s3_key == "documents/2024/lecture_notes_abc123.pdf"
    assert document.status == DocumentStatus.UPLOADED
    assert document.progress is None
    assert document.error is None
    assert document.created_at is not None
    assert document.processed_at is None


@pytest.mark.asyncio
async def test_create_document_with_progress(db_session: AsyncSession):
    """Test: Document can be created with JSONB progress field."""
    # Arrange
    subject = await Subject.create(db_session, name="Physics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Johnson")
    await db_session.commit()

    progress_data = {
        "pages_processed": 10,
        "total_pages": 50,
        "chunks_created": 25,
    }

    document_data = {
        "subject_id": subject.id,
        "teacher_id": teacher.id,
        "filename": "textbook.pdf",
        "s3_key": "documents/textbook_xyz.pdf",
        "status": DocumentStatus.PROCESSING,
        "progress": progress_data,
    }

    # Act
    document = await Document.create(db_session, **document_data)
    await db_session.commit()

    # Assert
    assert document.progress == progress_data
    assert document.progress["pages_processed"] == 10
    assert document.progress["total_pages"] == 50


@pytest.mark.asyncio
async def test_create_document_with_error(db_session: AsyncSession):
    """Test: Document can store error message."""
    # Arrange
    subject = await Subject.create(db_session, name="Chemistry", semester=2)
    teacher = await Teacher.create(db_session, name="Dr. Williams")
    await db_session.commit()

    document_data = {
        "subject_id": subject.id,
        "teacher_id": teacher.id,
        "filename": "corrupted.pdf",
        "s3_key": "documents/corrupted_file.pdf",
        "status": DocumentStatus.ERROR,
        "error": "Failed to parse PDF: file is corrupted",
    }

    # Act
    document = await Document.create(db_session, **document_data)
    await db_session.commit()

    # Assert
    assert document.status == DocumentStatus.ERROR
    assert document.error == "Failed to parse PDF: file is corrupted"


@pytest.mark.asyncio
async def test_document_status_enum_values(db_session: AsyncSession):
    """Test: All DocumentStatus enum values should work correctly."""
    # Arrange
    subject = await Subject.create(db_session, name="Biology", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Brown")
    await db_session.commit()

    statuses = [
        DocumentStatus.PENDING,
        DocumentStatus.UPLOADED,
        DocumentStatus.PROCESSING,
        DocumentStatus.READY,
        DocumentStatus.ERROR,
    ]

    # Act & Assert
    for idx, status in enumerate(statuses):
        doc = await Document.create(
            db_session,
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename=f"doc_{idx}.pdf",
            s3_key=f"documents/doc_{idx}.pdf",
            status=status,
        )
        await db_session.commit()
        assert doc.status == status


@pytest.mark.asyncio
async def test_s3_key_unique_constraint(db_session: AsyncSession):
    """Test: s3_key must be unique across all documents."""
    # Arrange
    subject = await Subject.create(db_session, name="History", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Davis")
    await db_session.commit()

    s3_key = "documents/unique_file.pdf"

    # Create first document
    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="first.pdf",
        s3_key=s3_key,
        status=DocumentStatus.UPLOADED,
    )
    await db_session.commit()

    # Act & Assert - try to create duplicate
    with pytest.raises(DatabaseConnectionError) as exc_info:
        await Document.create(
            db_session,
            subject_id=subject.id,
            teacher_id=teacher.id,
            filename="second.pdf",
            s3_key=s3_key,
            status=DocumentStatus.UPLOADED,
        )
        await db_session.commit()

    assert "Integrity constraint violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_document_relationships_with_subject(db_session: AsyncSession):
    """Test: Document has proper relationship with Subject."""
    # Arrange
    subject = await Subject.create(db_session, name="Art", semester=3)
    teacher = await Teacher.create(db_session, name="Dr. Taylor")
    await db_session.commit()

    document = await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="art_history.pdf",
        s3_key="documents/art_history.pdf",
        status=DocumentStatus.READY,
    )
    await db_session.commit()

    # Act
    retrieved = await Document.get_by_id(db_session, document.id)

    # Assert
    assert retrieved is not None
    assert retrieved.subject_id == subject.id


@pytest.mark.asyncio
async def test_document_relationships_with_teacher(db_session: AsyncSession):
    """Test: Document has proper relationship with Teacher."""
    # Arrange
    subject = await Subject.create(db_session, name="Music", semester=2)
    teacher = await Teacher.create(db_session, name="Professor Anderson")
    await db_session.commit()

    document = await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="music_theory.pdf",
        s3_key="documents/music_theory.pdf",
        status=DocumentStatus.READY,
    )
    await db_session.commit()

    # Act
    retrieved = await Document.get_by_id(db_session, document.id)

    # Assert
    assert retrieved is not None
    assert retrieved.teacher_id == teacher.id


@pytest.mark.asyncio
async def test_find_documents_by_status(db_session: AsyncSession):
    """Test: Document.find() should filter by status."""
    # Arrange
    subject = await Subject.create(db_session, name="Geography", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Wilson")
    await db_session.commit()

    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="doc1.pdf",
        s3_key="documents/doc1.pdf",
        status=DocumentStatus.READY,
    )
    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="doc2.pdf",
        s3_key="documents/doc2.pdf",
        status=DocumentStatus.READY,
    )
    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="doc3.pdf",
        s3_key="documents/doc3.pdf",
        status=DocumentStatus.PROCESSING,
    )
    await db_session.commit()

    # Act
    ready_docs = await Document.find(db_session, status=DocumentStatus.READY)

    # Assert
    assert len(ready_docs) == 2
    assert all(doc.status == DocumentStatus.READY for doc in ready_docs)


@pytest.mark.asyncio
async def test_find_documents_by_subject(db_session: AsyncSession):
    """Test: Document.find() should filter by subject_id."""
    # Arrange
    subject1 = await Subject.create(db_session, name="Math", semester=1)
    subject2 = await Subject.create(db_session, name="Physics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Lee")
    await db_session.commit()

    await Document.create(
        db_session,
        subject_id=subject1.id,
        teacher_id=teacher.id,
        filename="math_doc.pdf",
        s3_key="documents/math_doc.pdf",
        status=DocumentStatus.READY,
    )
    await Document.create(
        db_session,
        subject_id=subject1.id,
        teacher_id=teacher.id,
        filename="math_doc2.pdf",
        s3_key="documents/math_doc2.pdf",
        status=DocumentStatus.READY,
    )
    await Document.create(
        db_session,
        subject_id=subject2.id,
        teacher_id=teacher.id,
        filename="physics_doc.pdf",
        s3_key="documents/physics_doc.pdf",
        status=DocumentStatus.READY,
    )
    await db_session.commit()

    # Act
    math_docs = await Document.find(db_session, subject_id=subject1.id)

    # Assert
    assert len(math_docs) == 2
    assert all(doc.subject_id == subject1.id for doc in math_docs)


@pytest.mark.asyncio
async def test_find_documents_by_teacher(db_session: AsyncSession):
    """Test: Document.find() should filter by teacher_id."""
    # Arrange
    subject = await Subject.create(db_session, name="Literature", semester=1)
    teacher1 = await Teacher.create(db_session, name="Dr. Martinez")
    teacher2 = await Teacher.create(db_session, name="Dr. Garcia")
    await db_session.commit()

    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher1.id,
        filename="lit1.pdf",
        s3_key="documents/lit1.pdf",
        status=DocumentStatus.READY,
    )
    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher2.id,
        filename="lit2.pdf",
        s3_key="documents/lit2.pdf",
        status=DocumentStatus.READY,
    )
    await db_session.commit()

    # Act
    teacher1_docs = await Document.find(db_session, teacher_id=teacher1.id)

    # Assert
    assert len(teacher1_docs) == 1
    assert teacher1_docs[0].teacher_id == teacher1.id


@pytest.mark.asyncio
async def test_update_document_status(db_session: AsyncSession):
    """Test: Document.update() should update status field."""
    # Arrange
    subject = await Subject.create(db_session, name="Economics", semester=2)
    teacher = await Teacher.create(db_session, name="Dr. Robinson")
    await db_session.commit()

    document = await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="econ.pdf",
        s3_key="documents/econ.pdf",
        status=DocumentStatus.PENDING,
    )
    await db_session.commit()

    # Act
    await document.update(db_session, status=DocumentStatus.PROCESSING)
    await db_session.commit()

    # Assert
    updated = await Document.get_by_id(db_session, document.id)
    assert updated.status == DocumentStatus.PROCESSING


@pytest.mark.asyncio
async def test_update_document_progress(db_session: AsyncSession):
    """Test: Document.update() should update JSONB progress field."""
    # Arrange
    subject = await Subject.create(db_session, name="Philosophy", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Clark")
    await db_session.commit()

    document = await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="philosophy.pdf",
        s3_key="documents/philosophy.pdf",
        status=DocumentStatus.PROCESSING,
        progress={"pages_processed": 5, "total_pages": 100},
    )
    await db_session.commit()

    # Act
    new_progress = {"pages_processed": 50, "total_pages": 100, "percentage": 50}
    await document.update(db_session, progress=new_progress)
    await db_session.commit()

    # Assert
    updated = await Document.get_by_id(db_session, document.id)
    assert updated.progress == new_progress
    assert updated.progress["pages_processed"] == 50


@pytest.mark.asyncio
async def test_delete_document(db_session: AsyncSession):
    """Test: Document.delete() should remove document from database."""
    # Arrange
    subject = await Subject.create(db_session, name="Sociology", semester=3)
    teacher = await Teacher.create(db_session, name="Dr. White")
    await db_session.commit()

    document = await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="temp.pdf",
        s3_key="documents/temp.pdf",
        status=DocumentStatus.UPLOADED,
    )
    await db_session.commit()
    doc_id = document.id

    # Act
    await document.delete(db_session)
    await db_session.commit()

    # Assert
    deleted = await Document.get_by_id(db_session, doc_id)
    assert deleted is None


@pytest.mark.asyncio
async def test_count_documents(db_session: AsyncSession):
    """Test: Document.count() should return correct count."""
    # Arrange
    subject = await Subject.create(db_session, name="Psychology", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Harris")
    await db_session.commit()

    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="doc1.pdf",
        s3_key="documents/psych1.pdf",
        status=DocumentStatus.READY,
    )
    await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="doc2.pdf",
        s3_key="documents/psych2.pdf",
        status=DocumentStatus.PROCESSING,
    )
    await db_session.commit()

    # Act
    total = await Document.count(db_session)
    ready_count = await Document.count(db_session, status=DocumentStatus.READY)

    # Assert
    assert total == 2
    assert ready_count == 1


@pytest.mark.asyncio
async def test_document_to_dict(db_session: AsyncSession):
    """Test: Document.to_dict() should return dictionary representation."""
    # Arrange
    subject = await Subject.create(db_session, name="Astronomy", semester=2)
    teacher = await Teacher.create(db_session, name="Dr. King")
    await db_session.commit()

    progress_data = {"step": 1, "total_steps": 5}
    document = await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="astronomy.pdf",
        s3_key="documents/astronomy.pdf",
        status=DocumentStatus.PROCESSING,
        progress=progress_data,
    )
    await db_session.commit()

    # Act
    doc_dict = document.to_dict()

    # Assert
    assert isinstance(doc_dict, dict)
    assert doc_dict["filename"] == "astronomy.pdf"
    assert doc_dict["s3_key"] == "documents/astronomy.pdf"
    assert doc_dict["status"] == DocumentStatus.PROCESSING
    assert doc_dict["progress"] == progress_data
    assert "id" in doc_dict
    assert "created_at" in doc_dict


@pytest.mark.asyncio
async def test_document_repr(db_session: AsyncSession):
    """Test: Document.__repr__() should return readable string representation."""
    # Arrange
    subject = await Subject.create(db_session, name="Geology", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Moore")
    await db_session.commit()

    document = await Document.create(
        db_session,
        subject_id=subject.id,
        teacher_id=teacher.id,
        filename="geology.pdf",
        s3_key="documents/geology.pdf",
        status=DocumentStatus.READY,
    )
    await db_session.commit()

    # Act
    repr_str = repr(document)

    # Assert
    assert "Document" in repr_str
    assert "geology.pdf" in repr_str
    assert str(document.id) in repr_str


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: Document.find() should raise InvalidFilterError for invalid field."""
    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await Document.find(db_session, invalid_field="value")

    assert "Invalid filter key 'invalid_field'" in str(exc_info.value)
    assert "Document" in str(exc_info.value)
