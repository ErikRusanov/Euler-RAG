.PHONY: clean format

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

