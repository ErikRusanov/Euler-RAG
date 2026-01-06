"""Unit tests for SolveRequest model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exceptions import InvalidFilterError
from app.models.solve_request import SolveRequest, SolveRequestStatus
from app.models.subject import Subject
from app.models.teacher import Teacher


@pytest.mark.asyncio
async def test_create_solve_request_success(db_session: AsyncSession):
    """Test: SolveRequest.create() should create request with required fields."""
    # Arrange
    request_data = {
        "question": "What is the derivative of x^2?",
        "status": SolveRequestStatus.PENDING,
    }

    # Act
    solve_request = await SolveRequest.create(db_session, **request_data)
    await db_session.commit()

    # Assert
    assert solve_request.id is not None
    assert solve_request.question == "What is the derivative of x^2?"
    assert solve_request.status == SolveRequestStatus.PENDING
    assert solve_request.subject_filter is None
    assert solve_request.matched_subject_id is None
    assert solve_request.matched_teacher_id is None
    assert solve_request.answer is None
    assert solve_request.chunks_used is None
    assert solve_request.used_rag is False
    assert solve_request.verified is False
    assert solve_request.error is None
    assert solve_request.created_at is not None
    assert solve_request.processed_at is None


@pytest.mark.asyncio
async def test_create_solve_request_with_subject_filter(db_session: AsyncSession):
    """Test: SolveRequest can be created with optional subject_filter."""
    # Arrange
    request_data = {
        "question": "Explain Newton's laws",
        "subject_filter": "Physics",
        "status": SolveRequestStatus.PENDING,
    }

    # Act
    solve_request = await SolveRequest.create(db_session, **request_data)
    await db_session.commit()

    # Assert
    assert solve_request.subject_filter == "Physics"


@pytest.mark.asyncio
async def test_create_solve_request_with_matches(db_session: AsyncSession):
    """Test: SolveRequest can store matched subject and teacher."""
    # Arrange
    subject = await Subject.create(db_session, name="Mathematics", semester=1)
    teacher = await Teacher.create(db_session, name="Dr. Smith")
    await db_session.commit()

    request_data = {
        "question": "What is calculus?",
        "matched_subject_id": subject.id,
        "matched_teacher_id": teacher.id,
        "status": SolveRequestStatus.PROCESSING,
    }

    # Act
    solve_request = await SolveRequest.create(db_session, **request_data)
    await db_session.commit()

    # Assert
    assert solve_request.matched_subject_id == subject.id
    assert solve_request.matched_teacher_id == teacher.id


@pytest.mark.asyncio
async def test_create_solve_request_with_answer(db_session: AsyncSession):
    """Test: SolveRequest can store answer and chunks_used."""
    # Arrange
    chunks_data = [
        {"chunk_id": "abc123", "text": "Calculus is...", "score": 0.95},
        {"chunk_id": "def456", "text": "Derivatives are...", "score": 0.89},
    ]

    request_data = {
        "question": "What is calculus?",
        "answer": "Calculus is a branch of mathematics...",
        "chunks_used": chunks_data,
        "used_rag": True,
        "verified": True,
        "status": SolveRequestStatus.READY,
    }

    # Act
    solve_request = await SolveRequest.create(db_session, **request_data)
    await db_session.commit()

    # Assert
    assert solve_request.answer == "Calculus is a branch of mathematics..."
    assert solve_request.chunks_used == chunks_data
    assert solve_request.used_rag is True
    assert solve_request.verified is True
    assert len(solve_request.chunks_used) == 2


@pytest.mark.asyncio
async def test_create_solve_request_with_error(db_session: AsyncSession):
    """Test: SolveRequest can store error message."""
    # Arrange
    request_data = {
        "question": "Invalid question?",
        "status": SolveRequestStatus.ERROR,
        "error": "Failed to find relevant context",
    }

    # Act
    solve_request = await SolveRequest.create(db_session, **request_data)
    await db_session.commit()

    # Assert
    assert solve_request.status == SolveRequestStatus.ERROR
    assert solve_request.error == "Failed to find relevant context"


@pytest.mark.asyncio
async def test_solve_request_status_enum_values(db_session: AsyncSession):
    """Test: All SolveRequestStatus enum values should work correctly."""
    # Arrange
    statuses = [
        SolveRequestStatus.PENDING,
        SolveRequestStatus.PROCESSING,
        SolveRequestStatus.READY,
        SolveRequestStatus.ERROR,
    ]

    # Act & Assert
    for idx, status in enumerate(statuses):
        request = await SolveRequest.create(
            db_session,
            question=f"Question {idx}?",
            status=status,
        )
        await db_session.commit()
        assert request.status == status


@pytest.mark.asyncio
async def test_find_solve_requests_by_status(db_session: AsyncSession):
    """Test: SolveRequest.find() should filter by status."""
    # Arrange
    await SolveRequest.create(
        db_session,
        question="Question 1?",
        status=SolveRequestStatus.READY,
    )
    await SolveRequest.create(
        db_session,
        question="Question 2?",
        status=SolveRequestStatus.READY,
    )
    await SolveRequest.create(
        db_session,
        question="Question 3?",
        status=SolveRequestStatus.PENDING,
    )
    await db_session.commit()

    # Act
    ready_requests = await SolveRequest.find(
        db_session, status=SolveRequestStatus.READY
    )

    # Assert
    assert len(ready_requests) == 2
    assert all(req.status == SolveRequestStatus.READY for req in ready_requests)


@pytest.mark.asyncio
async def test_find_solve_requests_by_subject_filter(db_session: AsyncSession):
    """Test: SolveRequest.find() should filter by subject_filter."""
    # Arrange
    await SolveRequest.create(
        db_session,
        question="Math question?",
        subject_filter="Mathematics",
        status=SolveRequestStatus.PENDING,
    )
    await SolveRequest.create(
        db_session,
        question="Physics question?",
        subject_filter="Physics",
        status=SolveRequestStatus.PENDING,
    )
    await db_session.commit()

    # Act
    math_requests = await SolveRequest.find(db_session, subject_filter="Mathematics")

    # Assert
    assert len(math_requests) == 1
    assert math_requests[0].subject_filter == "Mathematics"


@pytest.mark.asyncio
async def test_find_solve_requests_by_matched_subject(db_session: AsyncSession):
    """Test: SolveRequest.find() should filter by matched_subject_id."""
    # Arrange
    subject1 = await Subject.create(db_session, name="Math", semester=1)
    subject2 = await Subject.create(db_session, name="Physics", semester=1)
    await db_session.commit()

    await SolveRequest.create(
        db_session,
        question="Math question?",
        matched_subject_id=subject1.id,
        status=SolveRequestStatus.READY,
    )
    await SolveRequest.create(
        db_session,
        question="Physics question?",
        matched_subject_id=subject2.id,
        status=SolveRequestStatus.READY,
    )
    await db_session.commit()

    # Act
    math_requests = await SolveRequest.find(db_session, matched_subject_id=subject1.id)

    # Assert
    assert len(math_requests) == 1
    assert math_requests[0].matched_subject_id == subject1.id


@pytest.mark.asyncio
async def test_find_solve_requests_by_used_rag(db_session: AsyncSession):
    """Test: SolveRequest.find() should filter by used_rag flag."""
    # Arrange
    await SolveRequest.create(
        db_session,
        question="Question with RAG?",
        used_rag=True,
        status=SolveRequestStatus.READY,
    )
    await SolveRequest.create(
        db_session,
        question="Question without RAG?",
        used_rag=False,
        status=SolveRequestStatus.READY,
    )
    await db_session.commit()

    # Act
    rag_requests = await SolveRequest.find(db_session, used_rag=True)

    # Assert
    assert len(rag_requests) == 1
    assert rag_requests[0].used_rag is True


@pytest.mark.asyncio
async def test_find_solve_requests_by_verified(db_session: AsyncSession):
    """Test: SolveRequest.find() should filter by verified flag."""
    # Arrange
    await SolveRequest.create(
        db_session,
        question="Verified question?",
        verified=True,
        status=SolveRequestStatus.READY,
    )
    await SolveRequest.create(
        db_session,
        question="Unverified question?",
        verified=False,
        status=SolveRequestStatus.READY,
    )
    await db_session.commit()

    # Act
    verified_requests = await SolveRequest.find(db_session, verified=True)

    # Assert
    assert len(verified_requests) == 1
    assert verified_requests[0].verified is True


@pytest.mark.asyncio
async def test_update_solve_request_status(db_session: AsyncSession):
    """Test: SolveRequest.update() should update status field."""
    # Arrange
    solve_request = await SolveRequest.create(
        db_session,
        question="Test question?",
        status=SolveRequestStatus.PENDING,
    )
    await db_session.commit()

    # Act
    await solve_request.update(db_session, status=SolveRequestStatus.PROCESSING)
    await db_session.commit()

    # Assert
    updated = await SolveRequest.get_by_id(db_session, solve_request.id)
    assert updated.status == SolveRequestStatus.PROCESSING


@pytest.mark.asyncio
async def test_update_solve_request_with_answer(db_session: AsyncSession):
    """Test: SolveRequest.update() should update answer and related fields."""
    # Arrange
    solve_request = await SolveRequest.create(
        db_session,
        question="What is algebra?",
        status=SolveRequestStatus.PROCESSING,
    )
    await db_session.commit()

    # Act
    chunks_data = [{"chunk_id": "xyz", "text": "Algebra is..."}]
    await solve_request.update(
        db_session,
        answer="Algebra is a branch of mathematics",
        chunks_used=chunks_data,
        used_rag=True,
        status=SolveRequestStatus.READY,
    )
    await db_session.commit()

    # Assert
    updated = await SolveRequest.get_by_id(db_session, solve_request.id)
    assert updated.answer == "Algebra is a branch of mathematics"
    assert updated.chunks_used == chunks_data
    assert updated.used_rag is True
    assert updated.status == SolveRequestStatus.READY


@pytest.mark.asyncio
async def test_update_solve_request_verification(db_session: AsyncSession):
    """Test: SolveRequest.update() should update verified flag."""
    # Arrange
    solve_request = await SolveRequest.create(
        db_session,
        question="Test?",
        status=SolveRequestStatus.READY,
        verified=False,
    )
    await db_session.commit()

    # Act
    await solve_request.update(db_session, verified=True)
    await db_session.commit()

    # Assert
    updated = await SolveRequest.get_by_id(db_session, solve_request.id)
    assert updated.verified is True


@pytest.mark.asyncio
async def test_delete_solve_request(db_session: AsyncSession):
    """Test: SolveRequest.delete() should remove request from database."""
    # Arrange
    solve_request = await SolveRequest.create(
        db_session,
        question="Temporary question?",
        status=SolveRequestStatus.PENDING,
    )
    await db_session.commit()
    request_id = solve_request.id

    # Act
    await solve_request.delete(db_session)
    await db_session.commit()

    # Assert
    deleted = await SolveRequest.get_by_id(db_session, request_id)
    assert deleted is None


@pytest.mark.asyncio
async def test_count_solve_requests(db_session: AsyncSession):
    """Test: SolveRequest.count() should return correct count."""
    # Arrange
    await SolveRequest.create(
        db_session,
        question="Q1?",
        status=SolveRequestStatus.READY,
    )
    await SolveRequest.create(
        db_session,
        question="Q2?",
        status=SolveRequestStatus.PENDING,
    )
    await db_session.commit()

    # Act
    total = await SolveRequest.count(db_session)
    ready_count = await SolveRequest.count(db_session, status=SolveRequestStatus.READY)

    # Assert
    assert total == 2
    assert ready_count == 1


@pytest.mark.asyncio
async def test_solve_request_to_dict(db_session: AsyncSession):
    """Test: SolveRequest.to_dict() should return dictionary representation."""
    # Arrange
    chunks_data = [{"chunk_id": "123", "text": "Example"}]
    solve_request = await SolveRequest.create(
        db_session,
        question="What is X?",
        answer="X is...",
        chunks_used=chunks_data,
        used_rag=True,
        verified=True,
        status=SolveRequestStatus.READY,
    )
    await db_session.commit()

    # Act
    request_dict = solve_request.to_dict()

    # Assert
    assert isinstance(request_dict, dict)
    assert request_dict["question"] == "What is X?"
    assert request_dict["answer"] == "X is..."
    assert request_dict["chunks_used"] == chunks_data
    assert request_dict["used_rag"] is True
    assert request_dict["verified"] is True
    assert request_dict["status"] == SolveRequestStatus.READY
    assert "id" in request_dict
    assert "created_at" in request_dict


@pytest.mark.asyncio
async def test_solve_request_repr(db_session: AsyncSession):
    """Test: SolveRequest.__repr__() should return readable representation."""
    # Arrange
    solve_request = await SolveRequest.create(
        db_session,
        question="Test question for repr?",
        status=SolveRequestStatus.PENDING,
    )
    await db_session.commit()

    # Act
    repr_str = repr(solve_request)

    # Assert
    assert "SolveRequest" in repr_str
    assert str(solve_request.id) in repr_str
    assert "pending" in repr_str


@pytest.mark.asyncio
async def test_find_with_invalid_filter(db_session: AsyncSession):
    """Test: SolveRequest.find() raises InvalidFilterError for invalid field."""
    # Act & Assert
    with pytest.raises(InvalidFilterError) as exc_info:
        await SolveRequest.find(db_session, invalid_field="value")

    assert "Invalid filter key 'invalid_field'" in str(exc_info.value)
    assert "SolveRequest" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_all_solve_requests(db_session: AsyncSession):
    """Test: SolveRequest.get_all() should retrieve all requests."""
    # Arrange
    await SolveRequest.create(
        db_session, question="Q1?", status=SolveRequestStatus.PENDING
    )
    await SolveRequest.create(
        db_session, question="Q2?", status=SolveRequestStatus.READY
    )
    await SolveRequest.create(
        db_session, question="Q3?", status=SolveRequestStatus.PROCESSING
    )
    await db_session.commit()

    # Act
    all_requests = await SolveRequest.get_all(db_session)

    # Assert
    assert len(all_requests) == 3
    questions = {req.question for req in all_requests}
    assert questions == {"Q1?", "Q2?", "Q3?"}


@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session: AsyncSession):
    """Test: SolveRequest.get_all() should support limit and offset."""
    # Arrange
    for i in range(5):
        await SolveRequest.create(
            db_session,
            question=f"Question {i}?",
            status=SolveRequestStatus.PENDING,
        )
    await db_session.commit()

    # Act
    page_1 = await SolveRequest.get_all(db_session, limit=2, offset=0)
    page_2 = await SolveRequest.get_all(db_session, limit=2, offset=2)

    # Assert
    assert len(page_1) == 2
    assert len(page_2) == 2
