# Make file targets: lint, test, parity-test, pre-commit, install (uv install), build
setup:
	uv sync
	uv run pre-commit install

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

# Parity check (sqlite only, local dev use) for one or all example projects.
# Usage: make parity-test or make parity-test example=multi-db
example ?= minimal-sqlite multi-db async-views
parity-test:
	@for dir in $(example); do \
		echo "=== $$dir ==="; \
		( \
			cd examples/$$dir && \
			uv sync && \
			uv run pytest --junit-xml=pytest.xml tests/ && \
			uv run rustest --pytest-compat --llm tests/ > rustest.jsonl && \
			uv run python ../compare_outcomes.py pytest.xml rustest.jsonl; \
			rc=$$?; \
			rm -f pytest.xml rustest.jsonl; \
			exit $$rc \
		) || exit 1; \
	done
