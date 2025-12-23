.PHONY: clean format db-up db-down db-restart db-logs

clean:
	@bash scripts/clean.sh

format:
	@echo "Очистка неиспользуемых импортов..."
	@autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive app/ tests/
	@echo "Сортировка импортов..."
	@isort app/ tests/ --profile black
	@echo "Форматирование Python файлов..."
	@black app/ tests/ --line-length 88
	@echo "Форматирование завершено!"

db-up:
	@echo "Запуск PostgreSQL через Docker Compose..."
	@docker-compose up -d postgres
	@echo "Ожидание готовности БД..."
	@docker-compose exec -T postgres pg_isready -U $$(grep DB_USER .env 2>/dev/null | cut -d '=' -f2 || echo "postgres") || sleep 2

db-down:
	@echo "Остановка PostgreSQL..."
	@docker-compose down

db-restart:
	@echo "Перезапуск PostgreSQL..."
	@docker-compose restart postgres

db-logs:
	@docker-compose logs -f postgres

