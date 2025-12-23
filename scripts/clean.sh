#!/bin/bash

# Скрипт для очистки временных файлов и директорий проекта

set -e

# Переход в корневую директорию проекта
cd "$(dirname "$0")/.."

echo "Очистка временных файлов..."

# Удаление всех __pycache__ директорий
find . -type d -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true

# Удаление .coverage файла
if [ -f .coverage ]; then
    rm -f .coverage
    echo "  ✓ Удален .coverage"
fi

# Удаление coverage.xml файла
if [ -f coverage.xml ]; then
    rm -f coverage.xml
    echo "  ✓ Удален coverage.xml"
fi

# Удаление htmlcov директории
if [ -d htmlcov ]; then
    rm -rf htmlcov
    echo "  ✓ Удалена директория htmlcov"
fi

# Удаление pytest cache
if [ -d .pytest_cache ]; then
    rm -rf .pytest_cache
    echo "  ✓ Удалена директория .pytest_cache"
fi

echo "Очистка завершена!"

