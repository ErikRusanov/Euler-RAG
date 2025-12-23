.PHONY: clean format db-up db-down db-restart db-logs

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

