# rustest-django v1 spec

Wayfinder map: [ernestomancebo/rustest-django#1](https://github.com/ernestomancebo/rustest-django/issues/1).
The map is complete and the supported v1 tier is implemented. The first PyPI release is
[0.0.1](https://pypi.org/project/rustest-django/0.0.1/); "v1" describes the design scope,
not a published 1.0 version. The sections below record the implemented decisions and
the remaining compatibility boundaries.

## Goals and contract

- **Port**: preserve pytest-django's public names within the supported tier, with
  compatibility boundaries documented; internals use rustest primitives.
- **Compat contract**: a consumer migrates with an import-path swap only
  (`pytest_django` → `rustest_django`, see [Public API § Name
  swap](./spec/api.md#name-swap)) within the supported tier. Defined unsupported
  fixtures and guarded markers fail loudly; unhandled marker cases are listed in
  [Public API § Unsupported names](./spec/api.md#unsupported-names).
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

The unsupported fixture stubs, the `urls` and `ignore_template_errors` function-level
markers, and Django unittest-style tests fail loudly. Enforced at three points: the marker/fixture
guard in [Public API § Unsupported names](./spec/api.md#unsupported-names), the config
validation in [Configuration § Failure behaviour](./spec/configuration.md#failure-behaviour),
and the per-method guard in [Unsupported test styles](./spec/unittest-support.md).
Messages use the implemented `rustest-django: ` prefix and include an alternative when
one exists. The `django_isolate_apps` marker is currently unhandled; it does not receive
this guard. See [Unsupported names](./spec/api.md#unsupported-names).

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

These features remain outside the implemented v1 tier. `live_server` has an open
implementation issue; the other additions need a scope decision and their own follow-up.
The user-facing [unsupported-feature inventory](../site-docs/reference/unsupported.md)
describes current behavior and alternatives.

- **`live_server`**: depends on rustest's process/thread model and whether a session
  fixture can own a server thread cleanly. Tracked by
  [#25](https://github.com/ernestomancebo/rustest-django/issues/25), including its
  `--liveserver`-equivalent configuration.
- **Standalone `django_db_serialized_rollback` fixture**: a defined unsupported stub.
  The `django_db` marker's `serialized_rollback` kwarg is already implemented.
- **App-registry isolation**: the `django_isolated_apps` fixture is an unsupported stub;
  the companion `django_isolate_apps` marker is unhandled.
- **`urls`, `ignore_template_errors`, and `--fail-on-template-vars`**: URL overrides
  have a `settings`-fixture alternative; template-variable failure instrumentation has
  no v1 equivalent.
- **django-configurations and database-name suffixing**: `--dc` / `DJANGO_CONFIGURATION`
  integration is excluded. The parallel/tox/xdist suffix fixtures retain their names but
  are no-ops.

The implemented `django_db` marker also has two compatibility gaps: positional values
are ignored, and unknown kwargs are not rejected. Use the supported keyword arguments;
matching pytest-django's positional handling and validation requires a code follow-up.
Configuration also coerces TOML boolean keys without strict type validation; use
actual TOML booleans as described in the [configuration reference](../site-docs/reference/configuration.md#boolean-values).

## Completed follow-ups

The original map deferred these tasks, which are now implemented:

| Task | Implementation |
|---|---|
| Error-message shapes | [Design](plans/2026-09-16-error-messages-design.md) and [PR #30](https://github.com/ernestomancebo/rustest-django/pull/30); shared prefix and alternatives in configuration, bootstrap, fixture, and unittest guards. |
| Consumer migration guide | [Published guide source](../site-docs/migration-guide.md), delivered with [PR #33](https://github.com/ernestomancebo/rustest-django/pull/33). |
| Release process and trusted publishing | [Release design](plans/2026-09-16-release-process-design.md), [PR #29](https://github.com/ernestomancebo/rustest-django/pull/29), and completed [publisher registration #28](https://github.com/ernestomancebo/rustest-django/issues/28); release `v0.0.1` is published. |
| Hosted documentation | [Docs-site design](plans/2026-09-16-docs-site-design.md) and completed [RTD registration #31](https://github.com/ernestomancebo/rustest-django/issues/31); `stable` and `latest` are built. |

Remaining distribution follow-ups are the upstream listing in
[#26](https://github.com/ernestomancebo/rustest-django/issues/26) and the RTD default-version
setting in [#32](https://github.com/ernestomancebo/rustest-django/issues/32). Neither blocks
installing the published package.
