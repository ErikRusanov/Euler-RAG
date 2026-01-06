"""Unit tests for SolveRequestService following TDD methodology.

This module contains comprehensive tests for SolveRequestService including:
- CRUD operations (inherited from BaseService)
- Search by status, subject_filter, matched_subject_id, used_rag, verified
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
from app.models.solve_request import SolveRequest, SolveRequestStatus
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.services.solve_request_service import SolveRequestService


@pytest.mark.asyncio
async def test_create_solve_request_success(db_session: AsyncSession):
    """Test: SolveRequestService.create() should create request with auto-commit."""
    # Arrange
    service = SolveRequestService(db_session)
    request_data = {
        "question": "What is calculus?",
        "status": SolveRequestStatus.PENDING,
    }

    # Act
    solve_request = await service.create(**request_data)

    # Assert
    assert solve_request.id is not None
    assert solve_request.question == "What is calculus?"
    assert solve_request.status == SolveRequestStatus.PENDING
    assert solve_request.created_at is not None

    # Verify persistence
    found = await SolveRequest.get_by_id(db_session, solve_request.id)
    assert found is not None
    assert found.question == "What is calculus?"


@pytest.mark.asyncio
async def test_create_solve_request_with_all_fields(db_session: AsyncSession):
    """Test: SolveRequestService.create() should handle all optional fields."""
    # Arrange
    service = SolveRequestService(db_session)
    subject = await Subject.create(db_session, name="Mathematics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Smith")
    await db_session.commit()

    chunks_data = [{"chunk_id": "123", "text": "Example"}]
    request_data = {
        "question": "Explain derivatives",
        "subject_filter": "Mathematics",
        "matched_subject_id": subject.id,
        "matched_teacher_id": teacher.id,
        "answer": "A derivative is...",
        "chunks_used": chunks_data,
        "used_rag": True,
        "verified": True,
        "status": SolveRequestStatus.READY,
    }

    # Act
    solve_request = await service.create(**request_data)

    # Assert
    assert solve_request.subject_filter == "Mathematics"
    assert solve_request.matched_subject_id == subject.id
    assert solve_request.answer == "A derivative is..."
    assert solve_request.used_rag is True


@pytest.mark.asyncio
async def test_get_by_id_success(db_session: AsyncSession):
    """Test: SolveRequestService.get_by_id() should retrieve existing request."""
    # Arrange
    service = SolveRequestService(db_session)
    created = await service.create(
        question="Test question?",
        status=SolveRequestStatus.PENDING,
    )

    # Act
    found = await service.get_by_id(created.id)

    # Assert
    assert found is not None
    assert found.id == created.id
    assert found.question == "Test question?"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test: SolveRequestService.get_by_id() should return None for non-existent ID."""
    # Arrange
    service = SolveRequestService(db_session)

    # Act
    found = await service.get_by_id(99999)

    # Assert
    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_or_fail_success(db_session: AsyncSession):
    """Test: SolveRequestService.get_by_id_or_fail() returns request if exists."""
    # Arrange
    service = SolveRequestService(db_session)
    created = await service.create(
        question="Another question?",
        status=SolveRequestStatus.READY,
    )

    # Act
    found = await service.get_by_id_or_fail(created.id)

    # Assert
    assert found.id == created.id


@pytest.mark.asyncio
async def test_get_by_id_or_fail_raises_error(db_session: AsyncSession):
    """Test: SolveRequestService.get_by_id_or_fail() raises error if not found."""
    # Arrange
    service = SolveRequestService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError) as exc_info:
        await service.get_by_id_or_fail(99999)

    assert "SolveRequest" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_all_solve_requests(db_session: AsyncSession):
    """Test: SolveRequestService.get_all() should retrieve all requests."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(question="Q1?", status=SolveRequestStatus.PENDING)
    await service.create(question="Q2?", status=SolveRequestStatus.READY)
    await service.create(question="Q3?", status=SolveRequestStatus.PROCESSING)

    # Act
    all_requests = await service.get_all()

    # Assert
    assert len(all_requests) == 3
    questions = {req.question for req in all_requests}
    assert questions == {"Q1?", "Q2?", "Q3?"}


@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session: AsyncSession):
    """Test: SolveRequestService.get_all() should support limit and offset."""
    # Arrange
    service = SolveRequestService(db_session)
    for i in range(5):
        await service.create(
            question=f"Question {i}?",
            status=SolveRequestStatus.PENDING,
        )

    # Act
    page_1 = await service.get_all(limit=2, offset=0)
    page_2 = await service.get_all(limit=2, offset=2)

    # Assert
    assert len(page_1) == 2
    assert len(page_2) == 2


@pytest.mark.asyncio
async def test_find_by_status(db_session: AsyncSession):
    """Test: SolveRequestService.find() should filter by status."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(question="Q1?", status=SolveRequestStatus.READY)
    await service.create(question="Q2?", status=SolveRequestStatus.PENDING)
    await service.create(question="Q3?", status=SolveRequestStatus.READY)

    # Act
    ready_requests = await service.find(status=SolveRequestStatus.READY)

    # Assert
    assert len(ready_requests) == 2
    assert all(req.status == SolveRequestStatus.READY for req in ready_requests)


@pytest.mark.asyncio
async def test_find_by_subject_filter(db_session: AsyncSession):
    """Test: SolveRequestService.find() should filter by subject_filter."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(
        question="Math Q?",
        subject_filter="Mathematics",
        status=SolveRequestStatus.PENDING,
    )
    await service.create(
        question="Physics Q?",
        subject_filter="Physics",
        status=SolveRequestStatus.PENDING,
    )

    # Act
    math_requests = await service.find(subject_filter="Mathematics")

    # Assert
    assert len(math_requests) == 1
    assert math_requests[0].subject_filter == "Mathematics"


@pytest.mark.asyncio
async def test_find_by_matched_subject_id(db_session: AsyncSession):
    """Test: SolveRequestService.find() should filter by matched_subject_id."""
    # Arrange
    service = SolveRequestService(db_session)
    subject1 = await Subject.create(db_session, name="Math", semester=1)
    subject2 = await Subject.create(db_session, name="Physics", semester=1)
    await db_session.commit()

    await service.create(
        question="Math Q?",
        matched_subject_id=subject1.id,
        status=SolveRequestStatus.READY,
    )
    await service.create(
        question="Physics Q?",
        matched_subject_id=subject2.id,
        status=SolveRequestStatus.READY,
    )

    # Act
    math_requests = await service.find(matched_subject_id=subject1.id)

    # Assert
    assert len(math_requests) == 1
    assert math_requests[0].matched_subject_id == subject1.id


@pytest.mark.asyncio
async def test_find_by_used_rag(db_session: AsyncSession):
    """Test: SolveRequestService.find() should filter by used_rag flag."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(
        question="RAG Q?",
        used_rag=True,
        status=SolveRequestStatus.READY,
    )
    await service.create(
        question="No RAG Q?",
        used_rag=False,
        status=SolveRequestStatus.READY,
    )

    # Act
    rag_requests = await service.find(used_rag=True)

    # Assert
    assert len(rag_requests) == 1
    assert rag_requests[0].used_rag is True


@pytest.mark.asyncio
async def test_find_by_verified(db_session: AsyncSession):
    """Test: SolveRequestService.find() should filter by verified flag."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(
        question="Verified Q?",
        verified=True,
        status=SolveRequestStatus.READY,
    )
    await service.create(
        question="Not verified Q?",
        verified=False,
        status=SolveRequestStatus.READY,
    )

    # Act
    verified_requests = await service.find(verified=True)

    # Assert
    assert len(verified_requests) == 1
    assert verified_requests[0].verified is True


@pytest.mark.asyncio
async def test_find_no_matches(db_session: AsyncSession):
    """Test: SolveRequestService.find() should return empty list when no matches."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(question="Q?", status=SolveRequestStatus.PENDING)

    # Act
    found = await service.find(status=SolveRequestStatus.ERROR)

    # Assert
    assert found == []


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: SolveRequestService.find() should raise error for invalid filter."""
    # Arrange
    service = SolveRequestService(db_session)

    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await service.find(invalid_field="value")

    assert "Invalid filter key 'invalid_field'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_count_all_solve_requests(db_session: AsyncSession):
    """Test: SolveRequestService.count() should return total count."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(question="Q1?", status=SolveRequestStatus.PENDING)
    await service.create(question="Q2?", status=SolveRequestStatus.READY)

    # Act
    count = await service.count()

    # Assert
    assert count == 2


@pytest.mark.asyncio
async def test_count_with_filter(db_session: AsyncSession):
    """Test: SolveRequestService.count() should count matching records."""
    # Arrange
    service = SolveRequestService(db_session)
    await service.create(question="Q1?", status=SolveRequestStatus.READY)
    await service.create(question="Q2?", status=SolveRequestStatus.READY)
    await service.create(question="Q3?", status=SolveRequestStatus.PENDING)

    # Act
    ready_count = await service.count(status=SolveRequestStatus.READY)

    # Assert
    assert ready_count == 2


@pytest.mark.asyncio
async def test_update_solve_request_success(db_session: AsyncSession):
    """Test: SolveRequestService.update() should update request and commit."""
    # Arrange
    service = SolveRequestService(db_session)
    solve_request = await service.create(
        question="Test?",
        status=SolveRequestStatus.PENDING,
    )

    # Act
    updated = await service.update(
        solve_request.id,
        status=SolveRequestStatus.PROCESSING,
    )

    # Assert
    assert updated.status == SolveRequestStatus.PROCESSING

    # Verify persistence
    found = await SolveRequest.get_by_id(db_session, solve_request.id)
    assert found.status == SolveRequestStatus.PROCESSING


@pytest.mark.asyncio
async def test_update_solve_request_with_answer(db_session: AsyncSession):
    """Test: SolveRequestService.update() should update answer and chunks."""
    # Arrange
    service = SolveRequestService(db_session)
    solve_request = await service.create(
        question="What is X?",
        status=SolveRequestStatus.PROCESSING,
    )

    # Act
    chunks = [{"chunk_id": "abc", "text": "X is..."}]
    updated = await service.update(
        solve_request.id,
        answer="X is a variable",
        chunks_used=chunks,
        used_rag=True,
        status=SolveRequestStatus.READY,
    )

    # Assert
    assert updated.answer == "X is a variable"
    assert updated.chunks_used == chunks
    assert updated.used_rag is True


@pytest.mark.asyncio
async def test_update_nonexistent_solve_request(db_session: AsyncSession):
    """Test: SolveRequestService.update() should raise error for non-existent ID."""
    # Arrange
    service = SolveRequestService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError):
        await service.update(99999, status=SolveRequestStatus.READY)


@pytest.mark.asyncio
async def test_update_with_invalid_field(db_session: AsyncSession):
    """Test: SolveRequestService.update() should raise error for invalid field."""
    # Arrange
    service = SolveRequestService(db_session)
    solve_request = await service.create(
        question="Test?",
        status=SolveRequestStatus.PENDING,
    )

    # Act & Assert
    with pytest.raises(InvalidFilterError):
        await service.update(solve_request.id, invalid_field="value")


@pytest.mark.asyncio
async def test_delete_solve_request_success(db_session: AsyncSession):
    """Test: SolveRequestService.delete() should remove request and commit."""
    # Arrange
    service = SolveRequestService(db_session)
    solve_request = await service.create(
        question="Temporary?",
        status=SolveRequestStatus.PENDING,
    )
    request_id = solve_request.id

    # Act
    await service.delete(request_id)

    # Assert - verify deletion
    found = await SolveRequest.get_by_id(db_session, request_id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_nonexistent_solve_request(db_session: AsyncSession):
    """Test: SolveRequestService.delete() should raise error for non-existent ID."""
    # Arrange
    service = SolveRequestService(db_session)

    # Act & Assert
    with pytest.raises(RecordNotFoundError):
        await service.delete(99999)


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_session: AsyncSession):
    """Test: Service should rollback transaction on database error."""
    # Arrange
    service = SolveRequestService(db_session)

    # Act & Assert
    # Try to create request without required fields
    with pytest.raises(DatabaseConnectionError):
        await service.create()

    # Verify no request was created
    count = await service.count()
    assert count == 0
