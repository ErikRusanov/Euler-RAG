"""Jinja2 template configuration for the application."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
STATIC_DIR = Path(__file__).parent.parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
