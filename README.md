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
- `API_TITLE`, `API_VERSION`, `DEBUG`, `HOST`, `PORT` - Application settings

## Development Tools

### Makefile

```bash
make format      # Format code (autoflake, isort, black)
make db-up       # Start PostgreSQL database
make db-down     # Stop PostgreSQL database
make db-restart  # Restart PostgreSQL database
make db-logs     # View database logs
make clean       # Remove temporary files
```

### Docker Compose

```bash
docker-compose up -d        # Start services
docker-compose down         # Stop services
docker-compose logs -f      # View logs
```

## Documentation

### Project Architecture

For a detailed explanation of the project architecture, see [docs/architecture.md](docs/architecture.md).

### API Reference

For a description of available API methods, see [docs/api.md](docs/api.md).
