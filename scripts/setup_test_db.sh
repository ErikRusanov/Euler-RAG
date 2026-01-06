#!/bin/bash
# Setup test database for running tests

set -e

# Load environment variables from .env file if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
TEST_DB_NAME="euler_rag_test"

echo "Setting up test database: $TEST_DB_NAME"

# Check if postgres is running
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
    echo "PostgreSQL is not running. Starting with docker-compose..."
    docker-compose up -d postgres
    
    # Wait for postgres to be ready
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
            echo "PostgreSQL is ready!"
            break
        fi
        sleep 1
    done
fi

# Create test database if it doesn't exist
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -tc "SELECT 1 FROM pg_database WHERE datname = '$TEST_DB_NAME'" | grep -q 1 || \
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "CREATE DATABASE $TEST_DB_NAME;"

echo "Test database '$TEST_DB_NAME' is ready!"
echo ""
echo "You can now run tests with:"
echo "  pytest tests/unit/models/test_base.py -v"

