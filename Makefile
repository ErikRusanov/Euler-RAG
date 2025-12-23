.PHONY: clean format

clean:
	@bash scripts/clean.sh

format:
	@echo "Форматирование Python файлов..."
	@black app/ tests/ --line-length 88
	@echo "Форматирование завершено!"

