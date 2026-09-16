# Example projects, parity CI, and library tests

Spec section for rustest-django v1. Decided in wayfinder ticket #14.

## Two kinds of tests

- **`examples/<name>/tests/`**: Django-level tests inside each example project,
  diffed exactly by the parity oracle across both runners. Prove the consumer-facing
  name-swap promise.
- **`tests/`** at the repo root: rustest-django's own unit tests (the `django_db` class
  decorator, config parsing, the unittest-style guard, the blocker), run only under
  rustest. Not part of the parity matrix; there is no pytest-django equivalent to diff
  against.

## Example project layout

`examples/<name>/` at repo root, self-contained: `manage.py`, `conftest.py`,
`pyproject.toml`, `settings.py`, an app package, `tests/`. Three projects:

- **minimal-sqlite**: T1 core end to end.
- **multi-db**: the `databases=` marker kwarg, `django_db_modify_db_settings`, and
  cross-database rollback isolation (a write to a non-default alias is gone after the
  test, same as default).
- **async-views**: `async_client`/`async_rf`, DB access from async tests with the
  documented caveat, and the loop-per-test parity test required by the async decision
  (#11): two async `db` tests observe distinct event loops and clean tables, proving DB
  isolation still holds when tests run concurrently-eligible.

No class-level `@pytest.mark.django_db` test in any example project: real pytest already
propagates it correctly, so a shared test using it would diverge under rustest by
definition, breaking the exact-match parity oracle. The `django_db` class decorator is
rustest-specific and is tested in `tests/` instead, never diffed against pytest.

## Loading the fixture module

One `pyproject.toml` per example, carrying both `[tool.pytest.ini_options]`
(`DJANGO_SETTINGS_MODULE`, `pythonpath`) and `[tool.rustest-django]` (`settings_module`).
One `conftest.py` per example with exactly one line: `rustest_fixtures =
["rustest_django"]`. Nothing pytest-specific is needed beyond `pytest-django` being
installed: its `pytest11` entry point registers itself.

## Test source

Example test files use plain `import pytest` / `@pytest.mark.django_db`, unmodified.
Under pytest they run as any pytest-django suite does; under rustest they run with
`--pytest-compat`. This proves the harder, more valuable claim: existing pytest-django
test files run completely unmodified. The rewritten-imports path (`from rustest import
mark`) is documented in the migration guide with a short standalone snippet, not
re-proven across three whole projects.

## Parity oracle mechanics

For each example project: `pytest --junit-xml=pytest.xml tests/` and `rustest
--pytest-compat --llm tests/ > rustest.jsonl`. A stdlib-only script,
`examples/compare_outcomes.py`, parses both, maps each test id to pass/fail/skip, and
asserts the sets match **exactly** — no exception list. The CI job fails on any
divergence. `--llm` is available in rustest 0.18.0 and emits one JSON object per test
outcome plus a summary line; `--junit-xml` gives pytest's per-test outcome in the same
shape.

## CI matrix

GitHub Actions, `uv` for environment setup. Respects Django 6.1's `>=3.12` floor:

| Python | Django | DB backends |
|---|---|---|
| 3.10, 3.12, 3.13 | 4.2 (LTS) | sqlite, postgres |
| 3.12, 3.13 | 5.2 (LTS) | sqlite, postgres |
| 3.12, 3.13 | 6.1 (latest) | sqlite, postgres |

12 cells × 2 runners (pytest, rustest) × 3 example projects. Postgres via
`testcontainers`, started programmatically from within the test run itself rather than a
GitHub Actions `services:` block, so local development and CI use the exact same code
path. Trimming (e.g. postgres on fewer cells) is a follow-up once the suite is slow
enough to matter, not pre-optimized now.

## Library unit tests (`tests/`)

Run once, under rustest only, no matrix needed beyond the same Python versions. Not
diffed against anything.
