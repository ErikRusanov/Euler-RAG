#!/bin/bash

# Script for cleaning up temporary files and directories of the project

set -e

# Go to the project's root directory
cd "$(dirname "$0")/.."

echo "Cleaning temporary files..."

# Remove all __pycache__ directories
find . -type d -name "__pycache__" -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true

# Remove .coverage file
if [ -f .coverage ]; then
    rm -f .coverage
    echo "  ✓ Removed .coverage"
fi

# Remove coverage.xml file
if [ -f coverage.xml ]; then
    rm -f coverage.xml
    echo "  ✓ Removed coverage.xml"
fi

# Remove htmlcov directory
if [ -d htmlcov ]; then
    rm -rf htmlcov
    echo "  ✓ Removed htmlcov directory"
fi

# Remove pytest cache
if [ -d .pytest_cache ]; then
    rm -rf .pytest_cache
    echo "  ✓ Removed .pytest_cache directory"
fi

echo "Cleanup completed!"

