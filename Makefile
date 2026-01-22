.PHONY: help install test test-all lint format sync-version clean build

help:
	@echo "Available commands:"
	@echo "  make install       - Install the package in development mode"
	@echo "  make test          - Run unit tests"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Format code with ruff"
	@echo "  make sync-version  - Sync version across project files"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make build         - Build distribution packages"

install:
	pip install -e ".[dev]"

test:
	pytest -m "not integration" -v

test-all:
	pytest -v

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff format src/ tests/

sync-version:
	python3 scripts/sync_version.py

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: sync-version
	python -m build
