# Euler RAG

## Overview

This project is designed for students of the Faculty of Mechanics and Mathematics. It solves problems using the exact notations and conventions of the subject and instructor. It utilizes RAG (Retrieval-Augmented Generation) and semantic parsing of LaTeX (PDF) lecture notes.

## Features

- Strict adherence to subject-specific notations
- Integration of RAG for advanced problem-solving
- Semantic parsing of LaTeX (PDF) documents

## Quick Start

_in progress_

## Configuration

Before starting the application, create a `.env` file based on `.env.template`:

```bash
cp .env.template .env
```

Edit `.env` and configure the following variables:
- `DB_USER` - PostgreSQL username (default: `postgres`)
- `DB_PASSWORD` - PostgreSQL password
- `DB_NAME` - Database name (default: `euler_rag`)
- `DB_HOST` - Database host (default: `localhost`)
- `DB_PORT` - Database port (default: `5432`)
- `REDIS_HOST` - Redis host (default: `localhost`)
- `REDIS_PORT` - Redis port (default: `6379`)
- `REDIS_DB` - Redis database number (default: `0`)
- `REDIS_PASSWORD` - Redis password (optional)
- `API_TITLE`, `API_VERSION`, `DEBUG`, `HOST`, `PORT` - Application settings

## Development Tools

### Makefile

```bash
make run         # Start PostgreSQL, Redis and application
make format      # Format code (autoflake, isort, black)
make db-up       # Start PostgreSQL database
make db-down     # Stop PostgreSQL database
make redis-up    # Start Redis
make redis-down  # Stop Redis
make clean       # Remove temporary files
```

### Docker Compose

```bash
docker-compose up -d        # Start services
docker-compose down         # Stop services
docker-compose logs -f      # View logs
```

## Testing

The project uses PostgreSQL for both development and testing to ensure consistency.

### Setup Test Database

Before running tests, setup the test database:

```bash
make test-setup
```

This will:
- Start PostgreSQL via docker-compose if not running
- Create `euler_rag_test` database

### Running Tests

```bash
make test           # Run all tests with test database setup
make test-unit      # Run only unit tests
make test-cov       # Run tests with coverage report
```

Or use pytest directly:

```bash
pytest tests/unit/models/test_base.py -v      # Run specific test file
pytest tests/ -v                               # Run all tests
pytest tests/ -v -k "test_create"             # Run tests matching pattern
```

## Documentation

### Project Architecture

For a detailed explanation of the project architecture, see [docs/architecture.md](docs/architecture.md).

### API Reference

For a description of available API methods, see [docs/api.md](docs/api.md).
