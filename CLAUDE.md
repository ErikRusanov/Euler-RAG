# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Euler RAG is a FastAPI-based backend for solving mathematical problems using RAG (Retrieval-Augmented Generation) with subject-specific lecture notes. Built for students of the Faculty of Mechanics and Mathematics to get answers using exact notations and conventions of their courses.

**Tech Stack**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Redis Streams, S3 (MinIO compatible), Pydantic 2.x

## Common Commands

```bash
# Development
make run                # Start PostgreSQL, Redis, and app
make format             # Run autoflake + isort + black
python -m app.main      # Run app directly (after db-up/redis-up)

# Database
make db-up              # Start PostgreSQL
make db-down            # Stop PostgreSQL
alembic upgrade head    # Run migrations
alembic revision --autogenerate -m "description"  # Create migration

# Testing
make test               # Setup test DB and run all tests
make test-unit          # Run unit tests only
pytest tests/unit/models/test_base.py -v         # Single file
pytest tests/ -v -k "test_create"                # Pattern match
```

## Architecture

### Layered Structure

```
API Routes (app/api/) → Services (app/services/) → Models (app/models/)
                                ↓
                    Utils (db, redis, s3, pubsub)
```

- **Dependency Injection**: All DB sessions, Redis, S3 injected via FastAPI's `Depends()`
- **Async-first**: Non-blocking I/O everywhere (asyncpg, aioredis, asyncio.to_thread for S3)
- **Generic Services**: `BaseService[T]` provides CRUD with auto-commit/rollback

### Worker System (Background Tasks)

Located in `app/workers/`:
- **TaskQueue** (`queue.py`): Redis Streams with consumer groups, DLQ, exponential backoff (3 retries)
- **WorkerManager** (`manager.py`): Manages N concurrent workers (default 4), 30s graceful shutdown
- **Handlers** (`handlers/`): Task-specific processors inheriting from `BaseTaskHandler`

Workflow: Upload → S3 → status=UPLOADED → PATCH status=PENDING → enqueue task → Worker processes

### Exception Handling

Custom hierarchy in `app/exceptions.py`:
- `RecordNotFoundError`, `RelatedRecordNotFoundError` → 404
- `InvalidFileTypeError` → 400
- `S3ConnectionError`, `RedisConnectionError` → 503

All mapped to HTTP responses via `app/utils/exception_handlers.py`

### Key Files

- `app/application.py`: App factory with lifespan (startup/shutdown)
- `app/config.py`: Pydantic Settings, env validation
- `app/api/router.py`: Creates public + protected (API key) routers
- `app/services/base.py`: Generic CRUD service base class

## Code Style

- Black formatter (88 line length)
- isort with black profile
- Type hints required on all functions
- SQLAlchemy 2.0 style (`Mapped[]`, `mapped_column()`)
- Pydantic v2 patterns (`model_config`, `field_validator`)
- pytest-asyncio with `asyncio_mode = "auto"`
- **Docstrings required** on all functions using Google style:
  ```python
  def function_name(arg1: str, arg2: int) -> Result:
      """Short description.

      Args:
          arg1: Description of arg1.
          arg2: Description of arg2.

      Returns:
          Description of return value.

      Raises:
          ExceptionType: When this error occurs.
      """
  ```

## Configuration

Copy `.env.template` to `.env`. Key variables:
- `DB_*`: PostgreSQL connection
- `REDIS_*`: Redis connection
- `S3_*`: Object storage (endpoint, keys, bucket)
- `API_KEY`: Required for protected endpoints (min 32 chars in production)
- `WORKER_CONCURRENCY`: Parallel task workers (default 4)
