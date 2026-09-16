# Make file targets: lint, test, parity-test, pre-commit, install (uv install), build
setup:
	echo "TODO: install dependencies, install pre-commit"

install:
	uv sync --frozen --all-extras

# Lint (ruff only) - usage: make lint or make lint output-format=full
output-format ?= concise
lint:
	uv run ruff check --output-format=$(output-format) src tests
	uv run ruff format --check src tests


test:
	uv run rustest tests

pre-commit:
	uv run pre-commit run --all-files

build:
	rm -rf dist
	uv build
	uvx twine check dist/*
