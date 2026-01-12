.PHONY: clean format db-up db-down db-restart db-logs redis-up redis-down redis-logs run dev run-prod

clean:
	@bash scripts/clean.sh

format:
	@echo "Removing unused imports..."
	@autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive app/ tests/
	@echo "Sorting imports..."
	@isort app/ tests/ --profile black
	@echo "Formatting Python files..."
	@black app/ tests/ --line-length 88
	@echo "Formatting complete!"

db-up:
	@echo "Starting PostgreSQL via Docker Compose..."
	@docker-compose up -d postgres
	@echo "Waiting for the database to become ready..."
	@docker-compose exec -T postgres pg_isready -U $$(grep DB_USER .env 2>/dev/null | cut -d '=' -f2 || echo "postgres") || sleep 2

db-down:
	@echo "Stopping PostgreSQL..."
	@docker-compose down

db-restart:
	@echo "Restarting PostgreSQL..."
	@docker-compose restart postgres

db-logs:
	@docker-compose logs -f postgres

redis-up:
	@echo "Starting Redis via Docker Compose..."
	@docker-compose up -d redis
	@echo "Waiting for Redis to become ready..."
	@docker-compose exec -T redis redis-cli ping || sleep 2

redis-down:
	@echo "Stopping Redis..."
	@docker-compose stop redis

redis-logs:
	@docker-compose logs -f redis

test:
	@echo "Setting up test database..."
	@bash scripts/setup_test_db.sh
	@echo "Running all tests..."
	@pytest tests/ -v

run: db-up redis-up
	@echo "Starting application..."
	@python -m app.main

run-prod:
	@echo "Starting application in production mode..."
	@uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level warning
