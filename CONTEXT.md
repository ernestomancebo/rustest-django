# Context

Glossary for rustest-django. Terms only; no implementation detail.

## Terms

- **Port**: rustest-django reproduces pytest-django's *public surface* (fixture names, marker names, keyword arguments, behaviour). Internals are rewritten on rustest primitives. Not a fork, not a shim.
- **Name swap**: the only changes a consumer makes to migrate a pytest-django suite: `pytest_django` becomes `rustest_django` in imports and in the conftest plugin line (`rustest_fixtures = ["rustest_django"]`), and tests that keep `import pytest` run with `--pytest-compat`. Anything requiring more than that breaks the compatibility contract.
- **Fixture module**: the sole extension point rustest offers. A Python module listed in a consumer's `conftest.py` via `rustest_fixtures`. rustest-django *is* a fixture module.
- **Runner option**: a knob pytest-django exposes as a CLI flag or ini option (`--reuse-db`, `--ds`, `--no-migrations`, `django_find_project`). rustest has no flag registration, so a runner option is an environment variable (per run) or a `[tool.rustest-django]` key in `pyproject.toml` (project default); the environment wins.
- **Supported tier**: the compatibility promise for v1. **T1** core (settings, setup, `db`, `transactional_db`, `django_db`, `client`, `rf`, `admin_*`, `django_user_model`, `settings`, `mailoutbox`, `asserts`). **T2 picks**: `django_assert_num_queries`, `django_assert_max_num_queries`, `async_client`, `async_rf`, multi-database. **T3 pick**: reuse-db as a runner option. Everything else is unsupported in v1.
- **Unsupported feature**: a pytest-django name outside the supported tier. The name still exists (fixture defined, marker recognised) and requesting it fails loudly with a message, never silently.
- **Unittest-style test**: a test written as a `django.test.SimpleTestCase` subclass (`TestCase`, `TransactionTestCase`, `LiveServerTestCase`). Unsupported in v1; every such method fails loudly because rustest cannot report its outcome. Plain `unittest.TestCase` subclasses are rustest's concern, not ours.
- **DB blocker**: the guard that raises when a test touches the database while no isolation is active. Installed for the whole session; lifted only by an isolation or by an explicit unblock.
- **Isolation**: the per-test wrapper that undoes a test's database changes. Two modes: **rollback** (transaction rolled back after the test) and **flush** (tables emptied after the test). Requested by `db`, `transactional_db`, or the `django_db` marker.
- **Test database lifecycle**: the session-level creation and destruction of the test databases, one per configured alias. Owned by `django_db_setup`; lazy, first DB test triggers it.
- **Marker**: the `django_db(...)` declaration on a test, spelled `@mark.django_db` with rustest's `mark` (the same object as `pytest.mark` under `--pytest-compat`). Semantics and kwargs are pytest-django's.
- **Example project**: a self-contained Django project inside this repo, with `manage.py`, `conftest.py`, and tests. Doubles as the library's test suite. Three planned: minimal-sqlite, multi-db, async-views. Lives under `examples/`; distinct from `tests/` at the repo root, which holds rustest-django's own unit tests and is not part of the parity oracle.
- **Parity oracle**: running each example project's tests under both pytest + pytest-django and rustest + rustest-django. Equal outcomes prove the name-swap contract.
