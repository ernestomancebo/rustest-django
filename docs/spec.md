# rustest-django v1 spec

Wayfinder map: [ernestomancebo/rustest-django#1](https://github.com/ernestomancebo/rustest-django/issues/1).
This is the destination: every section below is a locked decision, ready for build
sessions. Building the library is a separate effort that starts here.

## Goals and contract

- **Port, not shim or reimplement**: public surface identical to pytest-django;
  internals rewritten on rustest primitives.
- **Compat contract**: a consumer migrates with an import-path swap only
  (`pytest_django` → `rustest_django`, see [Public API § Name
  swap](./spec/api.md#name-swap)). Unsupported features fail loudly, never silently.
- **Supported tier v1**:
  - **T1** (full): settings, setup, `db`, `transactional_db`, `django_db`, `client`,
    `rf`, `admin_*`, `django_user_model`, `settings`, `mailoutbox`,
    `rustest_django.asserts`.
  - **T2** (picks): `django_assert_num_queries`/`max`, `async_client`/`async_rf`,
    multi-database.
  - **T3** (pick): reuse-db as a runner option.
  - Everything else is unsupported in v1 (see [Public API § Unsupported
    names](./spec/api.md#unsupported-names)).

Glossary: [CONTEXT.md](../CONTEXT.md).

## Architecture

rustest's sole extension point is a **fixture module** loaded via `rustest_fixtures =
[...]` in a consumer's `conftest.py`; rustest-django *is* that module. rustest imports it
right after the declaring conftest and before any test module — the only point early
enough to run `django.setup()` before test modules import models (see [Configuration §
When Django is set up](./spec/configuration.md#when-django-is-set-up)). Import-time
errors from a fixture module are silently swallowed by rustest, so rustest-django
re-raises them from a session autouse fixture instead, so every test fails with the same
message rather than the run silently proceeding without Django configured.

Per-test behaviour rests on two pieces built for the whole session:

- **DB blocker**: raises on any database access with no isolation active. Lifted by an
  isolation or an explicit unblock. See [DB isolation § DB blocker](./spec/db-isolation.md#db-blocker).
- **Isolation engine**: reuses Django's own `TestCase`/`TransactionTestCase` internals,
  not a hand-rolled `atomic()` + flush. Full detail and rationale: [DB
  isolation](./spec/db-isolation.md), [ADR
  0001](./adr/0001-db-isolation-on-django-testcase-internals.md).

Markers are read via `request.node.get_closest_marker`, which only reaches
function-level marks under rustest 0.18; class-level marks and `pytestmark` don't
propagate, worked around by the `rustest_django.django_db` class decorator (see
[Upstream relationship](./spec/upstream.md)).

## Public API

Fixture and marker list, name-swap mechanics: [docs/spec/api.md](./spec/api.md).

## Configuration

Settings discovery, `pyproject.toml`/env precedence, failure behaviour:
[docs/spec/configuration.md](./spec/configuration.md).

## DB isolation

Isolation modes, test database lifecycle, private-API boundary:
[docs/spec/db-isolation.md](./spec/db-isolation.md).

## Async support

Native async tests, loop-scope constraint, DB-access caveat:
[docs/spec/async.md](./spec/async.md).

## Unsupported test styles

`unittest`-style Django `TestCase` support (out for v1):
[docs/spec/unittest-support.md](./spec/unittest-support.md).

## Unsupported-feature behaviour

Every unsupported name (fixture, marker, or test style) exists and fails loudly, never
silently — no test reports a false pass. Enforced at three points: the marker/fixture
guard in [Public API § Unsupported names](./spec/api.md#unsupported-names), the config
validation in [Configuration § Failure behaviour](./spec/configuration.md#failure-behaviour),
and the per-method guard in [Unsupported test styles](./spec/unittest-support.md). Exact
message text for all three is deferred (see [Deferred](#deferred) below).

## Example projects and CI

Three parity example projects, the parity oracle, and the CI matrix:
[docs/spec/testing-and-ci.md](./spec/testing-and-ci.md).

## Packaging and versioning

- **Distribution**: standalone repo, PyPI package `rustest-django`, import
  `rustest_django`.
- **Versions**: Python 3.10+; Django 4.2 LTS, 5.x, 6.x (6.x requires Python ≥3.12). Full
  CI matrix: [testing-and-ci.md § CI matrix](./spec/testing-and-ci.md#ci-matrix).
- **rustest version target**: `rustest>=0.18,<1.0`. Detail:
  [docs/spec/upstream.md](./spec/upstream.md).
- **Tooling**: uv, hatchling, ruff, `ty` for type checking.
- **License**: BSD-3-Clause, pytest-django copyright retained.

## Upstream relationship

Gaps reported to rustest, workarounds shipped in the meantime:
[docs/spec/upstream.md](./spec/upstream.md).

## Deferred

Not yet decided; each needs its own follow-up before it can land in a build session, but
none blocks starting on the sections above:

- **`live_server`**: depends on rustest's process/thread model and whether a session
  fixture can own a server thread cleanly. T2 leftover.
- **Exact error-message shapes**: for unsupported fixtures/markers, the unittest guard,
  config validation, and bootstrap failures — today these surface as a stderr traceback
  plus a collection error, not a designed message.
- **Consumer migration guide**: contents. Known must-haves: the `--pytest-compat`
  requirement when tests keep `import pytest`, excluding unittest-style test paths from
  the rustest run.
- **Release process**: PyPI trusted publishing, versioning policy relative to
  pytest-django releases.
